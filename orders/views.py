import math
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Order, CartItem, Dispute
from .serializers import OrderSerializer, CartItemSerializer, DisputeSerializer
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
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        if request.user.role == 'BUYER':
            orders = Order.objects.filter(buyer=request.user).order_by('-id')
        elif request.user.role == 'FARMER':
            orders = Order.objects.filter(produce__farmer=request.user).order_by('-id')
        elif request.user.role == 'TRANSPORTER':
            orders = Order.objects.filter(transport_job__transporter=request.user).order_by('-id')
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
    permission_classes = [permissions.IsAuthenticated]
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
    permission_classes = [permissions.IsAuthenticated]
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
    permission_classes = [permissions.IsAuthenticated]
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
    permission_classes = [permissions.IsAuthenticated]
    """DELETE /api/cart/<id>/"""
    def delete(self, request, pk):
        try:
            item = CartItem.objects.get(id=pk, buyer=request.user)
        except CartItem.DoesNotExist:
            return Response({'detail': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartCheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
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
    permission_classes = [permissions.IsAuthenticated]
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


def _ensure_dispute_table_schema():
    """Auto-verifies that PostgreSQL has orders_dispute table and all columns, dropping constraints on legacy columns."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders_dispute (
                    id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    order_id bigint NOT NULL REFERENCES orders_order(id) ON DELETE CASCADE,
                    raised_by_id bigint NOT NULL REFERENCES users_customuser(id) ON DELETE CASCADE,
                    reason varchar(30) NOT NULL DEFAULT 'SPOILED_ROTTEN',
                    description text NOT NULL DEFAULT '',
                    evidence_url varchar(500) NOT NULL DEFAULT '',
                    status varchar(25) NOT NULL DEFAULT 'OPEN',
                    resolution varchar(25) NOT NULL DEFAULT '',
                    refund_amount numeric(10, 2) NOT NULL DEFAULT 0.00,
                    release_amount numeric(10, 2) NOT NULL DEFAULT 0.00,
                    resolution_notes text NOT NULL DEFAULT '',
                    resolved_by_id bigint NULL REFERENCES users_customuser(id) ON DELETE SET NULL,
                    created_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cols = [
                ("raised_by_id", "bigint REFERENCES users_customuser(id) ON DELETE CASCADE"),
                ("reason", "varchar(30) DEFAULT 'SPOILED_ROTTEN'"),
                ("description", "text DEFAULT ''"),
                ("evidence_url", "varchar(500) DEFAULT ''"),
                ("status", "varchar(25) DEFAULT 'OPEN'"),
                ("resolution", "varchar(25) DEFAULT ''"),
                ("refund_amount", "numeric(10, 2) DEFAULT 0.00"),
                ("release_amount", "numeric(10, 2) DEFAULT 0.00"),
                ("resolution_notes", "text DEFAULT ''"),
                ("resolved_by_id", "bigint REFERENCES users_customuser(id) ON DELETE SET NULL"),
                ("created_at", "timestamp with time zone DEFAULT CURRENT_TIMESTAMP"),
                ("updated_at", "timestamp with time zone DEFAULT CURRENT_TIMESTAMP"),
            ]
            for col_name, col_type in cols:
                try:
                    cursor.execute(f"ALTER TABLE orders_dispute ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
                except Exception:
                    pass

            # Dynamically query information_schema for all columns in orders_dispute
            active_fields = {
                'id', 'order_id', 'raised_by_id', 'reason', 'description',
                'evidence_url', 'status', 'resolution', 'refund_amount',
                'release_amount', 'resolution_notes', 'resolved_by_id',
                'created_at', 'updated_at'
            }
            try:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'orders_dispute';
                """)
                db_cols = [row[0] for row in cursor.fetchall()]
                for db_col in db_cols:
                    if db_col not in active_fields:
                        try:
                            cursor.execute(f'ALTER TABLE orders_dispute ALTER COLUMN "{db_col}" DROP NOT NULL;')
                            cursor.execute(f'ALTER TABLE orders_dispute ALTER COLUMN "{db_col}" SET DEFAULT \'\';')
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass


# Run schema check on view module load
_ensure_dispute_table_schema()


class OrderRejectView(APIView):
    """
    POST /api/orders/<int:pk>/reject/
    Allows the buyer to reject produce delivered or in transit, locking escrow and opening a dispute.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _ensure_dispute_table_schema()
        try:
            order = Order.objects.get(id=pk, buyer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found or not owned by you'}, status=status.HTTP_404_NOT_FOUND)

        if order.payment_status not in ['HELD_IN_ESCROW', 'UNPAID']:
            return Response({'detail': f'Cannot reject order with payment status {order.payment_status}'}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', 'SPOILED_ROTTEN')
        description = request.data.get('description', '')
        evidence_url = request.data.get('evidence_url', '')

        if not description:
            return Response({'detail': 'Description is required for rejecting cargo'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Create open dispute
            dispute = Dispute.objects.create(
                order=order,
                raised_by=request.user,
                reason=reason,
                description=description,
                evidence_url=evidence_url,
                status='OPEN'
            )


            # Transition order state
            order.status = 'REJECTED'
            order.payment_status = 'DISPUTED'
            order.save()

        # Send alert notifications to all relevant stakeholders
        farmer = order.produce.farmer
        create_alert(
            user=request.user,
            notification_type='SMS',
            title='Order Rejected & Dispute Filed',
            content=f"You rejected Order #{order.id}. Dispute #{dispute.id} has been opened for admin review. Escrow funds remain locked."
        )
        create_alert(
            user=farmer,
            notification_type='SMS',
            title='Buyer Rejected Shipment',
            content=f"Buyer {request.user.username} rejected Order #{order.id} for {order.produce.name} ({dispute.get_reason_display()}). Dispute #{dispute.id} opened."
        )
        create_alert(
            user=farmer,
            notification_type='EMAIL',
            title=f"Dispute Filed for Order #{order.id}",
            content=f"Buyer {request.user.username} rejected the shipment for Order #{order.id}.\nReason: {dispute.get_reason_display()}\nDescription: {description}\nEscrow funds will remain locked pending resolution."
        )

        try:
            job = order.transport_job
            if job.transporter:
                create_alert(
                    user=job.transporter,
                    notification_type='SMS',
                    title='Logistics Delivery Disputed',
                    content=f"Delivery for Order #{order.id} has been rejected by buyer. Dispute #{dispute.id} initiated."
                )
        except TransportJob.DoesNotExist:
            pass

        return Response({
            'message': 'Order rejected and dispute raised successfully',
            'order': OrderSerializer(order).data,
            'dispute': DisputeSerializer(dispute).data
        }, status=status.HTTP_201_CREATED)


class OrderDisputeView(APIView):
    """
    POST /api/orders/<int:pk>/dispute/
    Allows buyer or farmer to open a formal dispute on an order.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _ensure_dispute_table_schema()
        try:
            order = Order.objects.get(id=pk)

        except Order.DoesNotExist:
            return Response({'detail': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.user != order.buyer and request.user != order.produce.farmer:
            return Response({'detail': 'Only the buyer or farmer of this order can raise a dispute'}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get('reason', 'OTHER')
        description = request.data.get('description', '')
        evidence_url = request.data.get('evidence_url', '')

        if not description:
            return Response({'detail': 'Description is required'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            dispute = Dispute.objects.create(
                order=order,
                raised_by=request.user,
                reason=reason,
                description=description,
                evidence_url=evidence_url,
                status='OPEN'
            )

            order.status = 'DISPUTED'
            order.payment_status = 'DISPUTED'
            order.save()

        # Send notifications
        other_user = order.produce.farmer if request.user == order.buyer else order.buyer
        create_alert(
            user=request.user,
            notification_type='SMS',
            title='Dispute Created',
            content=f"Dispute #{dispute.id} opened for Order #{order.id}. Our mediation engine will review."
        )
        create_alert(
            user=other_user,
            notification_type='SMS',
            title='Dispute Filed on Order',
            content=f"{request.user.username} raised a dispute on Order #{order.id} ({dispute.get_reason_display()})."
        )

        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)


class DisputeListView(APIView):
    """
    GET /api/disputes/
    Lists disputes related to the current user (buyer, farmer, transporter, or staff).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            if user.is_staff or user.is_superuser:
                disputes = Dispute.objects.all()
            elif user.role == 'BUYER':
                disputes = Dispute.objects.filter(order__buyer=user)
            elif user.role == 'FARMER':
                disputes = Dispute.objects.filter(order__produce__farmer=user)
            elif user.role == 'TRANSPORTER':
                disputes = Dispute.objects.filter(order__transport_job__transporter=user)
            else:
                disputes = Dispute.objects.filter(raised_by=user)

            serializer = DisputeSerializer(disputes.distinct(), many=True)
            return Response(serializer.data)
        except Exception:
            return Response([])



class DisputeDetailView(APIView):
    """
    GET /api/disputes/<int:pk>/
    Retrieve detail of a single dispute.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            dispute = Dispute.objects.get(id=pk)
        except Dispute.DoesNotExist:
            return Response({'detail': 'Dispute not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check permission
        user = request.user
        is_party = (dispute.raised_by == user or
                    dispute.order.buyer == user or
                    dispute.order.produce.farmer == user or
                    (hasattr(dispute.order, 'transport_job') and dispute.order.transport_job.transporter == user) or
                    user.is_staff)

        if not is_party:
            return Response({'detail': 'Not authorized to view this dispute'}, status=status.HTTP_403_FORBIDDEN)

        return Response(DisputeSerializer(dispute).data)


class DisputeResolveView(APIView):
    """
    POST /api/disputes/<int:pk>/resolve/
    Resolves a dispute with full refund to buyer, escrow release to farmer, or partial split.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        _ensure_dispute_table_schema()

        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'detail': 'Only platform administrators can resolve disputes'}, status=status.HTTP_403_FORBIDDEN)

        try:
            dispute = Dispute.objects.get(id=pk)
        except Dispute.DoesNotExist:
            return Response({'detail': 'Dispute not found'}, status=status.HTTP_404_NOT_FOUND)

        if dispute.status in ['RESOLVED_REFUND', 'RESOLVED_RELEASE', 'RESOLVED_PARTIAL', 'CANCELLED']:
            return Response({'detail': 'This dispute is already resolved or closed'}, status=status.HTTP_400_BAD_REQUEST)

        # Only staff can resolve
        order = dispute.order

        resolution = request.data.get('resolution')  # 'REFUND_BUYER', 'RELEASE_FARMER', 'PARTIAL_SPLIT', 'DISMISS'
        notes = request.data.get('notes', 'Resolved via platform escrow mediation')
        restock = request.data.get('restock_inventory', False)
        
        if resolution not in ['REFUND_BUYER', 'RELEASE_FARMER', 'PARTIAL_SPLIT', 'DISMISS']:
            return Response({'detail': 'Invalid resolution choice'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            buyer = order.buyer
            farmer = order.produce.farmer
            produce = order.produce
            job = getattr(order, 'transport_job', None)
            logistics_fee = job.estimated_cost if (job and job.estimated_cost) else Decimal('0.00')

            if resolution == 'REFUND_BUYER':
                # Full refund of produce price (and logistics if applicable) to Buyer wallet
                refund_total = order.total_price
                if job and job.payment_status in ['PAID', 'REQUESTED']:
                    refund_total += logistics_fee

                buyer.wallet_balance += refund_total
                buyer.save()

                WalletTransaction.objects.create(
                    user=buyer,
                    transaction_type='PAYMENT',
                    amount=refund_total,
                    reference=f'AGRI-REFUND-{order.id}-{dispute.id}',
                    description=f'Escrow Refund for Order #{order.id} (Dispute #{dispute.id})'
                )

                if restock:
                    produce.quantity_available += order.quantity
                    if produce.status == 'SOLD':
                        produce.status = 'AVAILABLE'
                    produce.save()

                order.payment_status = 'REFUNDED'
                order.status = 'CANCELLED'
                dispute.status = 'RESOLVED_REFUND'
                dispute.refund_amount = refund_total
                dispute.resolution = 'REFUND_BUYER'

            elif resolution in ['RELEASE_FARMER', 'DISMISS']:
                # Full release of escrow to Farmer & Transporter
                farmer.wallet_balance += order.total_price
                farmer.save()

                WalletTransaction.objects.create(
                    user=farmer,
                    transaction_type='PAYOUT',
                    amount=order.total_price,
                    reference=f'AGRI-ESCROW-REL-{order.id}',
                    description=f'Escrow released after dispute resolution for Order #{order.id}'
                )

                if job and job.transporter:
                    job.transporter.wallet_balance += logistics_fee
                    job.transporter.save()
                    WalletTransaction.objects.create(
                        user=job.transporter,
                        transaction_type='PAYOUT',
                        amount=logistics_fee,
                        reference=f'AGRI-TRANSPORT-{job.id}',
                        description=f'Delivery fee released for Order #{order.id}'
                    )

                order.payment_status = 'RELEASED'
                order.status = 'DELIVERED'
                dispute.status = 'RESOLVED_RELEASE'
                dispute.release_amount = order.total_price
                dispute.resolution = 'RELEASE_FARMER' if resolution == 'RELEASE_FARMER' else 'DISMISS'

            elif resolution == 'PARTIAL_SPLIT':
                # Split escrow between buyer and farmer
                custom_refund = Decimal(str(request.data.get('refund_amount', float(order.total_price) / 2)))
                custom_release = Decimal(str(request.data.get('release_amount', float(order.total_price) - float(custom_refund))))

                # Cap refund at order price
                if custom_refund > order.total_price:
                    custom_refund = order.total_price
                    custom_release = Decimal('0.00')

                # Refund buyer portion
                if custom_refund > 0:
                    buyer.wallet_balance += custom_refund
                    buyer.save()
                    WalletTransaction.objects.create(
                        user=buyer,
                        transaction_type='PAYMENT',
                        amount=custom_refund,
                        reference=f'AGRI-PARTIAL-REFUND-{order.id}',
                        description=f'Partial Escrow Refund for Order #{order.id}'
                    )

                # Release farmer portion
                if custom_release > 0:
                    farmer.wallet_balance += custom_release
                    farmer.save()
                    WalletTransaction.objects.create(
                        user=farmer,
                        transaction_type='PAYOUT',
                        amount=custom_release,
                        reference=f'AGRI-PARTIAL-REL-{order.id}',
                        description=f'Partial Escrow Release for Order #{order.id}'
                    )

                # Transporter receives logistics fee if job completed
                if job and job.transporter:
                    job.transporter.wallet_balance += logistics_fee
                    job.transporter.save()
                    WalletTransaction.objects.create(
                        user=job.transporter,
                        transaction_type='PAYOUT',
                        amount=logistics_fee,
                        reference=f'AGRI-TRANSPORT-{job.id}',
                        description=f'Delivery fee for Order #{order.id}'
                    )

                order.payment_status = 'PARTIALLY_REFUNDED'
                order.status = 'DELIVERED'
                dispute.status = 'RESOLVED_PARTIAL'
                dispute.refund_amount = custom_refund
                dispute.release_amount = custom_release
                dispute.resolution = 'PARTIAL_SPLIT'

            order.save()
            dispute.resolution_notes = notes
            dispute.resolved_by = request.user
            dispute.save()

        # Alert stakeholders
        create_alert(
            user=buyer,
            notification_type='SMS',
            title='Dispute Resolved',
            content=f"Dispute #{dispute.id} on Order #{order.id} resolved ({dispute.get_resolution_display()}). Check your wallet balance."
        )
        create_alert(
            user=farmer,
            notification_type='SMS',
            title='Dispute Resolved',
            content=f"Dispute #{dispute.id} on Order #{order.id} resolved ({dispute.get_resolution_display()})."
        )

        return Response({
            'message': 'Dispute resolved successfully',
            'dispute': DisputeSerializer(dispute).data,
            'order': OrderSerializer(order).data
        })

