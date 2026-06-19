import math
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Order, CartItem
from .serializers import OrderSerializer, CartItemSerializer
from produce.models import Produce
from logistics.models import TransportJob
from payments.models import WalletTransaction


from users.notifications import create_alert


def _estimate_logistics(buyer, produce, quantity):
    """Haversine-style distance estimate; returns GHS cost."""
    try:
        lat1, lon1 = float(buyer.latitude), float(buyer.longitude)
        lat2, lon2 = float(produce.farmer.latitude), float(produce.farmer.longitude)
        distance = math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) * 111.0
        if distance < 1:
            distance = 1.0
        return round(10.0 + (distance * 2.5) + (quantity * 1.0), 2)
    except Exception:
        return 15.0  # safe fallback


class OrderCreateView(APIView):
    def get(self, request):
        if request.user.role == 'BUYER':
            orders = Order.objects.filter(buyer=request.user).order_by('-id')
        elif request.user.role == 'FARMER':
            orders = Order.objects.filter(produce__farmer=request.user).order_by('-id')
        else:
            orders = Order.objects.all().order_by('-id')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request):
        if request.user.role != 'BUYER':
            return Response({'detail': 'Only buyers can create orders'}, status=status.HTTP_403_FORBIDDEN)

        produce_id = request.data.get('produce')
        quantity = int(request.data.get('quantity', 1))
        delivery_type = request.data.get('delivery_type', 'PLATFORM_DELIVERY')

        try:
            produce = Produce.objects.get(id=produce_id, status='AVAILABLE')
        except Produce.DoesNotExist:
            return Response({'detail': 'Produce not available or sold out'}, status=status.HTTP_404_NOT_FOUND)

        # Enforce Circle connection (accepted connection between buyer and farmer)
        from users.models import Connection
        from django.db import models as db_models
        is_connected = Connection.objects.filter(
            (db_models.Q(sender=request.user, receiver=produce.farmer) |
             db_models.Q(sender=produce.farmer, receiver=request.user)),
            status='ACCEPTED'
        ).exists()
        if not is_connected:
            return Response({
                'detail': f'You must be connected to farmer {produce.farmer.username} to transact. Please connect with them first.',
                'not_connected': True,
                'farmer_id': produce.farmer.id
            }, status=status.HTTP_403_FORBIDDEN)

        if produce.quantity_available < quantity:
            return Response({'detail': 'Insufficient quantity available'}, status=status.HTTP_400_BAD_REQUEST)

        total_price = produce.price_per_unit * quantity

        with transaction.atomic():
            # Create Order
            order = Order.objects.create(
                buyer=request.user,
                produce=produce,
                quantity=quantity,
                total_price=total_price,
                status='PENDING',
                payment_status='UNPAID',
                delivery_type=delivery_type
            )

            # Deduct quantity from inventory
            produce.quantity_available -= quantity
            if produce.quantity_available == 0:
                produce.status = 'SOLD'
            produce.save()

            # If platform coordinates delivery, calculate geodistance cost and create TransportJob
            est_cost = Decimal('0.00')
            if delivery_type == 'PLATFORM_DELIVERY':
                est_cost = Decimal(str(_estimate_logistics(request.user, produce, quantity)))

                TransportJob.objects.create(
                    order=order,
                    vehicle_type='Aboboyaa Tricycle' if est_cost < 30 else 'KIA Bongo 1.5 Ton',
                    estimated_cost=est_cost,
                    status='PENDING_MATCH'
                )

        # Send Notifications for Order placement
        total_charge = order.total_price + est_cost
        create_alert(
            user=request.user,
            notification_type='SMS',
            title='Order Placed Successfully',
            content=f"Order placed successfully! Order #{order.id} for {order.quantity} {order.produce.unit} of {order.produce.name}. Total: GHS {total_charge:.2f}. Please fund your wallet to complete payment."
        )
        create_alert(
            user=request.user,
            notification_type='EMAIL',
            title=f"Invoice for Order #{order.id}",
            content=f"Thank you for your order!\n\nOrder Details:\nProduce: {order.produce.name}\nQuantity: {order.quantity} {order.produce.unit}\nProduce Price: GHS {order.total_price:.2f}\nLogistics Fee: GHS {est_cost:.2f}\nTotal Invoice Amount: GHS {total_charge:.2f}\n\nStatus: Pending Payment."
        )
        create_alert(
            user=produce.farmer,
            notification_type='SMS',
            title='New Order Received',
            content=f"New order received! Buyer {request.user.username} has ordered {order.quantity} {order.produce.unit} of {order.produce.name}. Once paid, you will be notified."
        )

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrderPayView(APIView):
    """Pay for a pending order using the buyer's platform wallet (pre-funded via Paystack)."""
    def post(self, request, pk):
        try:
            order = Order.objects.get(id=pk, buyer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        if order.status == 'CANCELLED' or order.payment_status != 'UNPAID':
            return Response({'detail': 'Order is already paid or cancelled'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if there is an associated TransportJob
        try:
            job = order.transport_job
            logistics_fee = job.estimated_cost
        except TransportJob.DoesNotExist:
            job = None
            logistics_fee = Decimal('0.00')

        total_charge = order.total_price + logistics_fee

        if request.user.wallet_balance < total_charge:
            return Response({
                'detail': f'Insufficient wallet balance. You need GHS {total_charge:.2f} but have GHS {request.user.wallet_balance:.2f}.',
                'needs_topup': True,
                'shortfall': float(total_charge) - float(request.user.wallet_balance),
            }, status=status.HTTP_402_PAYMENT_REQUIRED)

        ref = f'AGRI-PAY-{order.id}-{request.user.id}'

        with transaction.atomic():
            buyer = request.user
            
            # Debit produce price
            buyer.wallet_balance -= order.total_price
            buyer.save()
            WalletTransaction.objects.create(
                user=buyer,
                transaction_type='PAYMENT',
                amount=order.total_price,
                reference=ref,
                description=f'Order #{order.id} - {order.produce.name} placed in escrow'
            )

            # Debit logistics fee if any
            if logistics_fee > 0:
                buyer.wallet_balance -= logistics_fee
                buyer.save()
                WalletTransaction.objects.create(
                    user=buyer,
                    transaction_type='PAYMENT',
                    amount=logistics_fee,
                    reference=f'AGRI-LOGISTICS-{job.id}',
                    description=f'Logistics reserve for Order #{order.id}'
                )

            # If order is already DELIVERED (recovery flow for direct dispatches completed before payment)
            if order.status == 'DELIVERED':
                # Release produce payment to Farmer immediately
                farmer = order.produce.farmer
                farmer.wallet_balance += order.total_price
                farmer.save()
                WalletTransaction.objects.create(
                    user=farmer,
                    transaction_type='PAYOUT',
                    amount=order.total_price,
                    reference=f'AGRI-ESCROW-REL-{order.id}',
                    description=f'Escrow released for Order #{order.id}'
                )

                # Release logistics fee to Transporter immediately
                if job and job.transporter:
                    transporter = job.transporter
                    transporter.wallet_balance += logistics_fee
                    transporter.save()
                    WalletTransaction.objects.create(
                        user=transporter,
                        transaction_type='PAYOUT',
                        amount=logistics_fee,
                        reference=f'AGRI-TRANSPORT-{job.id}',
                        description=f'Delivery fee for Order #{order.id}'
                    )
                order.payment_status = 'RELEASED'
            else:
                order.payment_status = 'HELD_IN_ESCROW'
                if order.status == 'PENDING':
                    # If a driver is already pre-assigned (matched), transition to SHIPPED immediately
                    if job and job.transporter:
                        order.status = 'SHIPPED'
                    else:
                        order.status = 'PAID'
            
            order.save()

        # Send Notifications for Order Payment
        if order.payment_status == 'RELEASED':
            create_alert(
                user=order.produce.farmer,
                notification_type='SMS',
                title='Escrow Released Immediately',
                content=f"Funds released! GHS {order.total_price:.2f} has been credited to your wallet for Order #{order.id}."
            )
            if job and job.transporter:
                create_alert(
                    user=job.transporter,
                    notification_type='SMS',
                    title='Logistics Fee Released',
                    content=f"Delivery fee of GHS {logistics_fee:.2f} has been released to your wallet for Order #{order.id}."
                )
        else:
            create_alert(
                user=buyer,
                notification_type='SMS',
                title='Payment Successful (Held in Escrow)',
                content=f"Payment successful! GHS {total_charge:.2f} has been deducted and held in escrow for Order #{order.id}."
            )
            create_alert(
                user=order.produce.farmer,
                notification_type='SMS',
                title='Order Paid (Escrow Funded)',
                content=f"Order #{order.id} is paid! Escrow is funded. You can now prepare the produce for pickup/delivery."
            )

        return Response(OrderSerializer(order).data)


class OrderConfirmDeliveryView(APIView):
    def post(self, request, pk):
        try:
            order = Order.objects.get(id=pk, buyer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        if order.payment_status != 'HELD_IN_ESCROW':
            return Response({'detail': 'Payment is not in Escrow'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Release escrow funds to Farmer
            farmer = order.produce.farmer
            farmer.wallet_balance += order.total_price
            farmer.save()

            WalletTransaction.objects.create(
                user=farmer,
                transaction_type='PAYOUT',
                amount=order.total_price,
                reference=f'AGRI-ESCROW-REL-{order.id}',
                description=f'Escrow released for Order #{order.id}'
            )

            # Update order payment state to RELEASED
            order.payment_status = 'RELEASED'
            order.status = 'DELIVERED'
            order.save()

            # Credit transporter if a matched job exists
            try:
                job = order.transport_job
                job.status = 'DELIVERED'
                job.delivery_time = timezone.now()
                job.save()

                if job.transporter:
                    transport_fee = job.estimated_cost
                    transporter = job.transporter
                    transporter.wallet_balance += transport_fee
                    transporter.save()

                    WalletTransaction.objects.create(
                        user=transporter,
                        transaction_type='PAYOUT',
                        amount=transport_fee,
                        reference=f'AGRI-TRANSPORT-{job.id}',
                        description=f'Delivery fee for Order #{order.id}'
                    )
            except TransportJob.DoesNotExist:
                pass

        # Send Notifications for Confirm Delivery & Escrow Release
        farmer = order.produce.farmer
        create_alert(
            user=request.user,
            notification_type='SMS',
            title='Escrow Released to Farmer',
            content=f"Order #{order.id} confirmed! GHS {order.total_price:.2f} released to farmer {farmer.username}."
        )
        create_alert(
            user=farmer,
            notification_type='SMS',
            title='Escrow Funds Received',
            content=f"Funds released! GHS {order.total_price:.2f} has been credited to your wallet for Order #{order.id}."
        )
        
        try:
            job = order.transport_job
            if job.transporter:
                create_alert(
                    user=job.transporter,
                    notification_type='SMS',
                    title='Logistics Fee Released',
                    content=f"Delivery fee of GHS {job.estimated_cost:.2f} has been released to your wallet for Order #{order.id}."
                )
        except TransportJob.DoesNotExist:
            pass

        return Response(OrderSerializer(order).data)


# ------------------------------------------------------------------
# CART VIEWS
# ------------------------------------------------------------------

class CartView(APIView):
    """GET (list cart), POST (add/update item)"""
    def get(self, request):
        if request.user.role != 'BUYER':
            return Response({'detail': 'Only buyers have a cart'}, status=status.HTTP_403_FORBIDDEN)
        items = CartItem.objects.filter(buyer=request.user).select_related('produce', 'produce__farmer')
        serializer = CartItemSerializer(items, many=True, context={'buyer': request.user})
        return Response(serializer.data)

    def post(self, request):
        if request.user.role != 'BUYER':
            return Response({'detail': 'Only buyers can add to cart'}, status=status.HTTP_403_FORBIDDEN)

        produce_id = request.data.get('produce')
        quantity = request.data.get('quantity', 1)

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            produce = Produce.objects.get(id=produce_id, status='AVAILABLE')
        except Produce.DoesNotExist:
            return Response({'detail': 'Produce not available'}, status=status.HTTP_404_NOT_FOUND)

        # Enforce Circle connection (accepted connection between buyer and farmer)
        from users.models import Connection
        from django.db import models as db_models
        is_connected = Connection.objects.filter(
            (db_models.Q(sender=request.user, receiver=produce.farmer) |
             db_models.Q(sender=produce.farmer, receiver=request.user)),
            status='ACCEPTED'
        ).exists()
        if not is_connected:
            return Response({
                'detail': f'You must be connected to farmer {produce.farmer.username} to transact. Please connect with them in the My Circle tab first.',
                'not_connected': True,
                'farmer_id': produce.farmer.id
            }, status=status.HTTP_403_FORBIDDEN)

        if produce.quantity_available < quantity:
            return Response({'detail': f'Only {produce.quantity_available} {produce.unit} available'}, status=status.HTTP_400_BAD_REQUEST)

        item, created = CartItem.objects.get_or_create(
            buyer=request.user,
            produce=produce,
            defaults={'quantity': quantity}
        )
        if not created:
            item.quantity = quantity
            item.save()

        serializer = CartItemSerializer(item, context={'buyer': request.user})
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CartItemDeleteView(APIView):
    """DELETE /api/cart/<id>/"""
    def delete(self, request, pk):
        try:
            item = CartItem.objects.get(id=pk, buyer=request.user)
        except CartItem.DoesNotExist:
            return Response({'detail': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartCheckoutView(APIView):
    """
    POST /api/cart/checkout/
    Converts all cart items to orders, debiting wallet for each.
    Requires sufficient wallet balance.
    """
    def post(self, request):
        if request.user.role != 'BUYER':
            return Response({'detail': 'Only buyers can checkout'}, status=status.HTTP_403_FORBIDDEN)

        cart_items = CartItem.objects.filter(buyer=request.user).select_related('produce', 'produce__farmer')
        if not cart_items.exists():
            return Response({'detail': 'Your cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce Circle connection check on checkout
        from users.models import Connection
        from django.db import models as db_models
        for item in cart_items:
            is_connected = Connection.objects.filter(
                (db_models.Q(sender=request.user, receiver=item.produce.farmer) |
                 db_models.Q(sender=item.produce.farmer, receiver=request.user)),
                status='ACCEPTED'
            ).exists()
            if not is_connected:
                return Response({
                    'detail': f'You are not connected to farmer {item.produce.farmer.username}. You must be connected to transact.',
                    'not_connected': True,
                    'farmer_id': item.produce.farmer.id
                }, status=status.HTTP_403_FORBIDDEN)

        # Compute total
        total_cost = 0.0
        for item in cart_items:
            total_cost += float(item.produce.price_per_unit * item.quantity)
            # Also include logistics
            total_cost += _estimate_logistics(request.user, item.produce, item.quantity)

        if float(request.user.wallet_balance) < total_cost:
            shortfall = total_cost - float(request.user.wallet_balance)
            return Response({
                'detail': f'Insufficient wallet balance. Cart total GHS {total_cost:.2f}, balance GHS {request.user.wallet_balance:.2f}.',
                'needs_topup': True,
                'shortfall': round(shortfall, 2),
            }, status=status.HTTP_402_PAYMENT_REQUIRED)

        created_orders = []

        with transaction.atomic():
            buyer = request.user

            for item in cart_items:
                produce = item.produce
                quantity = item.quantity

                if produce.quantity_available < quantity:
                    # Skip items that became unavailable
                    item.delete()
                    continue

                total_price = produce.price_per_unit * quantity
                logistics_cost = _estimate_logistics(buyer, produce, quantity)

                # Create Order
                order = Order.objects.create(
                    buyer=buyer,
                    produce=produce,
                    quantity=quantity,
                    total_price=total_price,
                    status='PAID',
                    payment_status='HELD_IN_ESCROW',
                    delivery_type='PLATFORM_DELIVERY'
                )

                # Deduct inventory
                produce.quantity_available -= quantity
                if produce.quantity_available == 0:
                    produce.status = 'SOLD'
                produce.save()

                # Debit buyer wallet for produce
                buyer.wallet_balance -= total_price
                buyer.save()

                WalletTransaction.objects.create(
                    user=buyer,
                    transaction_type='PAYMENT',
                    amount=total_price,
                    reference=f'AGRI-CART-{order.id}',
                    description=f'Cart checkout Order #{order.id} - {produce.name} in escrow'
                )

                # Create TransportJob and debit logistics cost
                est_cost = logistics_cost
                job = TransportJob.objects.create(
                    order=order,
                    vehicle_type='Aboboyaa Tricycle' if est_cost < 30 else 'KIA Bongo 1.5 Ton',
                    estimated_cost=est_cost,
                    status='PENDING_MATCH'
                )

                buyer.wallet_balance -= Decimal(str(logistics_cost))
                buyer.save()

                WalletTransaction.objects.create(
                    user=buyer,
                    transaction_type='PAYMENT',
                    amount=logistics_cost,
                    reference=f'AGRI-LOGISTICS-{job.id}',
                    description=f'Logistics reserve for Order #{order.id}'
                )

                # Credit farmer immediately (escrow release on delivery separately)
                # Note: This credits produce cost to farmer - delivery payment released on confirm
                farmer = produce.farmer
                farmer.wallet_balance += total_price
                farmer.save()

                WalletTransaction.objects.create(
                    user=farmer,
                    transaction_type='PAYOUT',
                    amount=total_price,
                    reference=f'AGRI-FARMER-{order.id}',
                    description=f'Cart checkout payment for Order #{order.id}'
                )

                # Remove item from cart
                item.delete()
                
                # Send Alerts for Cart checkout order
                total_charge = order.total_price + Decimal(str(est_cost))
                create_alert(
                    user=buyer,
                    notification_type='SMS',
                    title='Cart Checkout Order Placed',
                    content=f"Cart checkout: Order #{order.id} placed! GHS {order.total_price:.2f} paid. Logistics reserve of GHS {est_cost:.2f} held in escrow."
                )
                create_alert(
                    user=buyer,
                    notification_type='EMAIL',
                    title=f"Invoice for Order #{order.id}",
                    content=f"Thank you for your cart checkout!\n\nOrder Details:\nProduce: {produce.name}\nQuantity: {order.quantity}\nProduce Price: GHS {order.total_price:.2f} (Paid)\nLogistics Fee: GHS {est_cost:.2f} (Held in Escrow)\nTotal charged: GHS {total_charge:.2f}"
                )
                create_alert(
                    user=farmer,
                    notification_type='SMS',
                    title='New Order Received & Paid',
                    content=f"New order #{order.id} received! GHS {order.total_price:.2f} credited to your wallet for {order.quantity} {produce.unit} of {produce.name}."
                )
                
                created_orders.append(OrderSerializer(order).data)

        return Response({
            'message': f'{len(created_orders)} order(s) created successfully',
            'orders': created_orders,
            'new_balance': float(buyer.wallet_balance),
        }, status=status.HTTP_201_CREATED)


class OrderDispatchView(APIView):
    """
    POST /api/orders/dispatch/
    Let farmers create a direct dispatch order for a client/buyer.
    Creates both the Order and a TransportJob.
    """
    def post(self, request):
        if request.user.role != 'FARMER':
            return Response({'detail': 'Only farmers can initiate dispatch'}, status=status.HTTP_403_FORBIDDEN)
            
        produce_id = request.data.get('produce')
        buyer_id = request.data.get('buyer')
        quantity = request.data.get('quantity')
        driver_id = request.data.get('driver') # Optional
        
        if not produce_id or not buyer_id or not quantity:
            return Response({'detail': 'produce, buyer, and quantity are required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)
            
        if quantity < 1:
            return Response({'detail': 'Quantity must be at least 1'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            produce = Produce.objects.get(id=produce_id, farmer=request.user, status='AVAILABLE')
        except Produce.DoesNotExist:
            return Response({'detail': 'Produce not found, not owned by you, or sold out'}, status=status.HTTP_404_NOT_FOUND)
            
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            buyer = User.objects.get(id=buyer_id, role='BUYER')
        except User.DoesNotExist:
            return Response({'detail': 'Buyer / Client not found'}, status=status.HTTP_404_NOT_FOUND)

        # Enforce Circle connection check for direct dispatch
        from users.models import Connection
        from django.db import models as db_models
        is_connected = Connection.objects.filter(
            (db_models.Q(sender=request.user, receiver=buyer) |
             db_models.Q(sender=buyer, receiver=request.user)),
            status='ACCEPTED'
        ).exists()
        if not is_connected:
            return Response({
                'detail': f'You must be connected to buyer {buyer.username} to dispatch goods.',
                'not_connected': True,
                'buyer_id': buyer.id
            }, status=status.HTTP_403_FORBIDDEN)
            
        if produce.quantity_available < quantity:
            return Response({'detail': f'Insufficient quantity. Only {produce.quantity_available} left.'}, status=status.HTTP_400_BAD_REQUEST)
            
        with transaction.atomic():
            total_price = produce.price_per_unit * quantity
            
            # Create Order
            order = Order.objects.create(
                buyer=buyer,
                produce=produce,
                quantity=quantity,
                total_price=total_price,
                status='PENDING',
                payment_status='UNPAID',
                delivery_type='PLATFORM_DELIVERY'
            )
            
            # Deduct from inventory
            produce.quantity_available -= quantity
            if produce.quantity_available == 0:
                produce.status = 'SOLD'
            produce.save()
            
            # Estimate logistics fee
            est_cost = _estimate_logistics(buyer, produce, quantity)
            
            # Create TransportJob
            job = TransportJob.objects.create(
                order=order,
                vehicle_type='Aboboyaa Tricycle' if est_cost < 30 else 'KIA Bongo 1.5 Ton',
                estimated_cost=est_cost,
                status='PENDING_MATCH'
            )
            
            # If driver specified, assign it immediately
            driver_assigned = False
            if driver_id:
                try:
                    driver = User.objects.get(id=driver_id, role='TRANSPORTER')
                    job.transporter = driver
                    job.status = 'MATCHED'
                    job.save()
                    # Do not set order status to SHIPPED yet; it should remain PENDING until paid!
                    driver_assigned = True
                except User.DoesNotExist:
                    pass
                    
        # Send dispatch alerts
        create_alert(
            user=buyer,
            notification_type='SMS',
            title='Direct Produce Dispatch',
            content=f"Farmer {request.user.username} has dispatched a direct order #{order.id} for you. Please pay GHS {order.total_price:.2f} + logistics GHS {est_cost:.2f} to accept."
        )
        create_alert(
            user=buyer,
            notification_type='EMAIL',
            title=f"Direct Dispatch Invoice - Order #{order.id}",
            content=f"Farmer {request.user.username} has dispatched produce directly to you.\n\nOrder Details:\nProduce: {produce.name}\nQuantity: {quantity} {produce.unit}\nPrice: GHS {order.total_price:.2f}\nLogistics Fee: GHS {est_cost:.2f}\nTotal to pay: GHS {order.total_price + Decimal(str(est_cost)):.2f}"
        )
        create_alert(
            user=request.user,
            notification_type='SMS',
            title='Direct Dispatch Initiated',
            content=f"Direct dispatch order #{order.id} created for buyer {buyer.username}. Awaiting buyer payment."
        )
        if driver_assigned:
            create_alert(
                user=driver,
                notification_type='SMS',
                title='Logistics Delivery Assigned',
                content=f"Farmer {request.user.username} has assigned you to delivery job for Order #{order.id}."
            )
            
        return Response({
            'message': 'Dispatch order created successfully.',
            'order_id': order.id,
            'job_id': job.id,
            'transporter_assigned': driver_assigned
        }, status=status.HTTP_201_CREATED)
