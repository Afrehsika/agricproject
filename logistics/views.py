from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import TransportJob
from .serializers import TransportJobSerializer
from users.notifications import create_alert


from django.db import transaction

class TransportJobListView(APIView):
    def get(self, request):
        if request.user.role == 'TRANSPORTER':
            claimed = request.query_params.get('claimed')
            if claimed == 'true':
                jobs = TransportJob.objects.filter(transporter=request.user).order_by('-id')
            else:
                jobs = TransportJob.objects.filter(status='PENDING_MATCH', order__payment_status='HELD_IN_ESCROW')
                search = request.query_params.get('search')
                if search:
                    jobs = jobs.filter(order__produce__name__icontains=search)
                jobs = jobs.order_by('-id')
        elif request.user.role == 'FARMER':
            jobs = TransportJob.objects.filter(order__produce__farmer=request.user).order_by('-id')
        elif request.user.role == 'BUYER':
            jobs = TransportJob.objects.filter(order__buyer=request.user).order_by('-id')
        else:
            return Response({'detail': 'Role not allowed'}, status=status.HTTP_403_FORBIDDEN)
            
        serializer = TransportJobSerializer(jobs, many=True)
        return Response(serializer.data)


class TransportJobClaimView(APIView):
    def post(self, request, pk):
        if request.user.role != 'TRANSPORTER':
            return Response({'detail': 'Only transporters can claim jobs'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            job = TransportJob.objects.get(id=pk, status='PENDING_MATCH')
        except TransportJob.DoesNotExist:
            return Response({'detail': 'Logistics job is already claimed or not found'}, status=status.HTTP_404_NOT_FOUND)
            
        if job.order.payment_status != 'HELD_IN_ESCROW':
            return Response({'detail': 'Logistics job cannot be claimed until the buyer has funded the escrow (paid for the order)'}, status=status.HTTP_400_BAD_REQUEST)
            
        job.transporter = request.user
        job.status = 'PENDING_APPROVAL'
        job.save()
        
        order = job.order
        
        # Trigger Alerts for Transporter and Buyer
        create_alert(
            user=request.user,
            notification_type='SMS',
            title='Logistics Claim Awaiting Approval',
            content=f"You have claimed the logistics contract for Order #{order.id}. Awaiting Buyer approval."
        )
        create_alert(
            user=order.buyer,
            notification_type='SMS',
            title='Logistics Claimed by Transporter',
            content=f"Logistics matched! Transporter {request.user.username} has claimed the logistics job for Order #{order.id}. Please approve/reject."
        )
        create_alert(
            user=order.buyer,
            notification_type='EMAIL',
            title=f"Logistics Match Approval Required for Order #{order.id}",
            content=f"Transporter {request.user.username} has claimed the delivery for your Order #{order.id}. Please review and approve/reject."
        )
        
        return Response(TransportJobSerializer(job).data)


class TransportJobStatusUpdateView(APIView):
    def post(self, request, pk):
        if request.user.role != 'TRANSPORTER':
            return Response({'detail': 'Only transporters can update logistics jobs'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            job = TransportJob.objects.get(id=pk, transporter=request.user)
        except TransportJob.DoesNotExist:
            return Response({'detail': 'Logistics job not found or not assigned to you'}, status=status.HTTP_404_NOT_FOUND)
            
        if job.status == 'PENDING_APPROVAL':
            return Response({'detail': 'This logistics contract is pending buyer approval.'}, status=status.HTTP_400_BAD_REQUEST)
            
        if job.order.payment_status != 'HELD_IN_ESCROW':
            return Response({'detail': 'Logistics job cannot be processed until the buyer has funded the escrow (paid for the order)'}, status=status.HTTP_400_BAD_REQUEST)
            
        new_status = request.data.get('status')
        if new_status not in ['PICKED_UP', 'DELIVERED']:
            return Response({'detail': 'Invalid status update'}, status=status.HTTP_400_BAD_REQUEST)

        order = job.order
        farmer = order.produce.farmer

        if new_status == 'PICKED_UP':
            # Require the driver to propose a final price before pickup is confirmed.
            # This starts the negotiation flow instead of immediately marking as picked up.
            proposed_price = request.data.get('proposed_price')
            if proposed_price is None:
                return Response({'detail': 'A proposed_price is required to initiate cargo pickup.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                proposed_price = float(proposed_price)
                if proposed_price <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                return Response({'detail': 'proposed_price must be a positive number.'}, status=status.HTTP_400_BAD_REQUEST)

            job.proposed_price = proposed_price
            job.negotiation_status = 'PENDING_BUYER_APPROVAL'
            job.save()

            estimated = float(job.estimated_cost)
            diff = proposed_price - estimated
            diff_msg = (
                f"GHS {abs(diff):.2f} MORE than the estimated GHS {estimated:.2f}." if diff > 0
                else f"GHS {abs(diff):.2f} LESS than the estimated GHS {estimated:.2f} (you will be refunded the difference)."
                if diff < 0 else f"the same as the estimated GHS {estimated:.2f}."
            )

            create_alert(
                user=order.buyer,
                notification_type='SMS',
                title=f'Price Review Required — Order #{order.id}',
                content=(
                    f"Transporter {job.transporter.username} has proposed a final logistics fee of "
                    f"GHS {proposed_price:.2f} for Order #{order.id}, which is {diff_msg} "
                    f"Please review and accept, counter, or reject in your Orders dashboard."
                )
            )
            create_alert(
                user=order.buyer,
                notification_type='EMAIL',
                title=f'Order #{order.id} — Logistics Price Review Required',
                content=(
                    f"Transporter {job.transporter.username} is at the pickup location and has proposed "
                    f"a final fee of GHS {proposed_price:.2f} (Estimated: GHS {estimated:.2f}). "
                    f"Please log in to accept, counter-offer, or reject."
                )
            )

        elif new_status == 'DELIVERED':
            if job.negotiation_status not in ('NONE', 'ACCEPTED'):
                return Response({'detail': 'Cannot mark as delivered while price negotiation is still open.'}, status=status.HTTP_400_BAD_REQUEST)

            job.status = 'DELIVERED'
            job.delivery_time = timezone.now()
            job.save()

            order.status = 'DELIVERED'
            order.save()

            create_alert(
                user=order.buyer,
                notification_type='SMS',
                title='Cargo Delivered',
                content=f"Your cargo for Order #{order.id} has been delivered by transporter {job.transporter.username}. Please confirm delivery in the dashboard to release escrow payment."
            )
            create_alert(
                user=order.buyer,
                notification_type='EMAIL',
                title=f"Order #{order.id} - Cargo Delivered",
                content=f"Your cargo for Order #{order.id} was successfully delivered by {job.transporter.username}. Please verify and confirm release of funds."
            )
            create_alert(
                user=farmer,
                notification_type='SMS',
                title='Cargo Delivered',
                content=f"Your produce for Order #{order.id} has been delivered. Once the buyer confirms, escrow payment will be released."
            )

        return Response(TransportJobSerializer(job).data)


class TransportJobNegotiationView(APIView):
    """
    POST /api/logistics/jobs/<pk>/negotiate/
    Handles the price negotiation ping-pong between the buyer and the driver.

    Actions (sent in request body as `action`):
      - 'accept'  — Buyer accepts the proposed price. Wallet is adjusted, cargo is marked picked up.
      - 'counter' — Either party counters with a new proposed_price. Flips negotiation_status.
      - 'reject'  — Buyer rejects and ends the contract. Refunds estimated_cost, resets job.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            job = TransportJob.objects.select_related('order', 'order__buyer', 'order__produce__farmer', 'transporter').get(id=pk)
        except TransportJob.DoesNotExist:
            return Response({'detail': 'Logistics job not found.'}, status=status.HTTP_404_NOT_FOUND)

        order = job.order
        buyer = order.buyer
        transporter = job.transporter
        farmer = order.produce.farmer
        action = request.data.get('action')

        if action not in ('accept', 'counter', 'reject'):
            return Response({'detail': "action must be 'accept', 'counter', or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

        # --- ACCEPT ---
        if action == 'accept':
            if request.user != buyer:
                return Response({'detail': 'Only the buyer can accept a price proposal.'}, status=status.HTTP_403_FORBIDDEN)
            if job.negotiation_status != 'PENDING_BUYER_APPROVAL':
                return Response({'detail': 'No pending price proposal for you to accept.'}, status=status.HTTP_400_BAD_REQUEST)

            from decimal import Decimal
            proposed = job.proposed_price if job.proposed_price is not None else Decimal('0.00')
            estimated = job.estimated_cost if job.estimated_cost is not None else Decimal('0.00')
            difference = proposed - estimated  # positive = buyer owes more, negative = refund

            with transaction.atomic():
                if difference > 0:
                    # Driver wants more than estimated — deduct shortfall from buyer's wallet
                    if buyer.wallet_balance < difference:
                        return Response(
                            {'detail': f'Insufficient wallet balance. You need GHS {difference:.2f} more to accept this price. Please top up your wallet.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    buyer.wallet_balance -= difference
                    buyer.save()
                elif difference < 0:
                    # Driver accepted less — refund the excess to the buyer's wallet
                    buyer.wallet_balance += abs(difference)
                    buyer.save()

                job.final_price = proposed
                job.negotiation_status = 'NONE'
                job.status = 'PICKED_UP'
                job.pickup_time = timezone.now()
                job.save()

                order.status = 'SHIPPED'
                order.save()

            # Alerts
            create_alert(
                user=transporter,
                notification_type='SMS',
                title=f'Price Accepted — Order #{order.id}',
                content=f'The buyer has accepted your price of GHS {proposed:.2f} for Order #{order.id}. Cargo is now officially in transit.'
            )
            create_alert(
                user=buyer,
                notification_type='SMS',
                title=f'Price Accepted — Cargo In Transit (Order #{order.id})',
                content=(
                    f'You accepted the logistics fee of GHS {proposed:.2f}. '
                    + (f'GHS {difference:.2f} was deducted from your wallet.' if difference > 0
                       else f'GHS {abs(difference):.2f} was refunded to your wallet.' if difference < 0
                       else 'No wallet change was needed.')
                    + f' Order #{order.id} is now in transit.'
                )
            )
            create_alert(
                user=farmer,
                notification_type='SMS',
                title='Cargo Dispatched',
                content=f'Transporter {transporter.username} has picked up the cargo for Order #{order.id}.'
            )
            return Response(TransportJobSerializer(job).data)

        # --- COUNTER ---
        if action == 'counter':
            # Determine whose turn it is
            if job.negotiation_status == 'PENDING_BUYER_APPROVAL' and request.user != buyer:
                return Response({'detail': 'It is the buyer\'s turn to respond.'}, status=status.HTTP_403_FORBIDDEN)
            if job.negotiation_status == 'PENDING_DRIVER_APPROVAL' and request.user != transporter:
                return Response({'detail': 'It is the driver\'s turn to respond.'}, status=status.HTTP_403_FORBIDDEN)
            if job.negotiation_status not in ('PENDING_BUYER_APPROVAL', 'PENDING_DRIVER_APPROVAL'):
                return Response({'detail': 'No active negotiation to counter.'}, status=status.HTTP_400_BAD_REQUEST)

            new_price = request.data.get('proposed_price')
            try:
                new_price = float(new_price)
                if new_price <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                return Response({'detail': 'A valid positive proposed_price is required to counter.'}, status=status.HTTP_400_BAD_REQUEST)

            # Flip the ball to the other party
            if request.user == buyer:
                job.negotiation_status = 'PENDING_DRIVER_APPROVAL'
                notify_user = transporter
                notify_title = f'Counter-Offer Received — Order #{order.id}'
                notify_content = f'Buyer {buyer.username} has countered with GHS {new_price:.2f} for Order #{order.id}. Please accept or counter back in your Logistics dashboard.'
            else:
                job.negotiation_status = 'PENDING_BUYER_APPROVAL'
                notify_user = buyer
                notify_title = f'Counter-Offer Received — Order #{order.id}'
                notify_content = f'Driver {transporter.username} has countered with GHS {new_price:.2f} for Order #{order.id}. Please review in your Orders dashboard.'

            job.proposed_price = new_price
            job.save()

            create_alert(user=notify_user, notification_type='SMS', title=notify_title, content=notify_content)
            return Response(TransportJobSerializer(job).data)

        # --- REJECT ---
        if action == 'reject':
            if request.user != buyer:
                return Response({'detail': 'Only the buyer can reject and end the logistics contract.'}, status=status.HTTP_403_FORBIDDEN)
            if job.negotiation_status not in ('PENDING_BUYER_APPROVAL', 'PENDING_DRIVER_APPROVAL'):
                return Response({'detail': 'No active negotiation to reject.'}, status=status.HTTP_400_BAD_REQUEST)

            estimated = float(job.estimated_cost)
            rejected_transporter = transporter

            with transaction.atomic():
                # Refund the estimated_cost back to the buyer since they're ending the contract
                buyer.wallet_balance += estimated
                buyer.save()

                # Unassign driver and reset job to open market
                job.transporter = None
                job.status = 'PENDING_MATCH'
                job.negotiation_status = 'NONE'
                job.proposed_price = None
                job.final_price = None
                job.save()

            create_alert(
                user=rejected_transporter,
                notification_type='SMS',
                title=f'Logistics Contract Ended — Order #{order.id}',
                content=f'The buyer has rejected your final price for Order #{order.id} and ended the contract. The job is now available for other drivers.'
            )
            create_alert(
                user=buyer,
                notification_type='SMS',
                title=f'Logistics Contract Cancelled — Order #{order.id}',
                content=f'You have ended the logistics contract for Order #{order.id}. GHS {estimated:.2f} has been refunded to your wallet. The job is now open for new drivers.'
            )
            return Response(TransportJobSerializer(job).data)


class TransportJobAssignView(APIView):

    """
    POST /api/logistics/<int:pk>/assign/
    Allows a farmer or buyer to directly assign/hire a driver for a transport job.
    """
    def post(self, request, pk):
        if request.user.role not in ['FARMER', 'BUYER']:
            return Response({'detail': 'Only farmers or buyers can assign drivers'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            if request.user.role == 'FARMER':
                job = TransportJob.objects.get(id=pk, order__produce__farmer=request.user)
            else:
                job = TransportJob.objects.get(id=pk, order__buyer=request.user)
        except TransportJob.DoesNotExist:
            return Response({'detail': 'Logistics job not found'}, status=status.HTTP_404_NOT_FOUND)
            
        driver_id = request.data.get('driver')
        paid_by = request.data.get('paid_by', 'UNSET')
        
        if request.user.role == 'BUYER':
            paid_by = 'BUYER'
            
        if not driver_id:
            return Response({'detail': 'driver ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            driver = User.objects.get(id=driver_id, role='TRANSPORTER')
        except User.DoesNotExist:
            return Response({'detail': 'Driver not found'}, status=status.HTTP_404_NOT_FOUND)
            
        if paid_by == 'FARMER':
            with transaction.atomic():
                farmer = request.user
                if farmer.wallet_balance < job.estimated_cost:
                    return Response({'detail': 'Insufficient wallet balance for logistics fee'}, status=status.HTTP_400_BAD_REQUEST)
                farmer.wallet_balance -= job.estimated_cost
                farmer.save()
                job.paid_by = 'FARMER'
                job.payment_status = 'PAID'
        else:
            job.paid_by = 'BUYER'
            job.payment_status = 'REQUESTED'
            
        job.transporter = driver
        job.status = 'MATCHED'
        job.save()
        
        order = job.order
        order.status = 'SHIPPED'
        order.save()
        
        create_alert(
            user=driver,
            notification_type='SMS',
            title='Logistics Contract Assigned',
            content=f"{request.user.username} has assigned you to delivery job for Order #{order.id}."
        )
        if request.user.role == 'FARMER':
            create_alert(
                user=order.buyer,
                notification_type='SMS',
                title='Logistics Transporter Assigned',
                content=f"Farmer assigned driver {driver.username} to Order #{order.id}."
            )
        
        return Response(TransportJobSerializer(job).data)


class TransportJobApproveView(APIView):
    """
    POST /api/logistics/jobs/<int:pk>/approve/
    Allows the order buyer to send action: 'approve' or 'reject' for transporter claims.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            job = TransportJob.objects.get(id=pk, status='PENDING_APPROVAL')
        except TransportJob.DoesNotExist:
            return Response({'detail': 'Logistics job is not pending approval or not found'}, status=status.HTTP_404_NOT_FOUND)
            
        order = job.order
        if order.buyer != request.user:
            return Response({'detail': 'Only the order buyer can approve or reject the logistics claim'}, status=status.HTTP_403_FORBIDDEN)
            
        action = request.data.get('action')
        if action not in ['approve', 'reject']:
            return Response({'detail': "Invalid action. Must be 'approve' or 'reject'"}, status=status.HTTP_400_BAD_REQUEST)
            
        transporter = job.transporter
        if action == 'approve':
            job.status = 'MATCHED'
            job.save()
            
            order.status = 'SHIPPED'
            order.save()
            
            # Send approval alerts
            create_alert(
                user=transporter,
                notification_type='SMS',
                title='Logistics Claim Approved',
                content=f"Your claim for logistics contract Order #{order.id} has been approved by the buyer! You can now pick up the cargo."
            )
            create_alert(
                user=request.user,
                notification_type='SMS',
                title='Transporter Match Approved',
                content=f"You approved transporter {transporter.username} for Order #{order.id}."
            )
            create_alert(
                user=request.user,
                notification_type='EMAIL',
                title=f"Order #{order.id} - Transporter Match Approved",
                content=f"You have approved the transporter match of {transporter.username} for Order #{order.id}."
            )
            
        elif action == 'reject':
            job.transporter = None
            job.status = 'PENDING_MATCH'
            job.save()
            
            # Send rejection alerts
            create_alert(
                user=transporter,
                notification_type='SMS',
                title='Logistics Claim Rejected',
                content=f"Your claim for logistics contract Order #{order.id} has been rejected by the buyer."
            )
            create_alert(
                user=request.user,
                notification_type='SMS',
                title='Transporter Match Rejected',
                content=f"You rejected the transporter claim for Order #{order.id}."
            )
            create_alert(
                user=request.user,
                notification_type='EMAIL',
                title=f"Order #{order.id} - Transporter Match Rejected",
                content=f"You have rejected the transporter match for Order #{order.id}. The job is now open for other transporters."
            )
            
        return Response(TransportJobSerializer(job).data)


class TransportJobPaymentRequestView(APIView):
    def post(self, request, pk):
        if request.user.role != 'TRANSPORTER':
            return Response({'detail': 'Only transporters can request payment'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            job = TransportJob.objects.get(id=pk, transporter=request.user)
        except TransportJob.DoesNotExist:
            return Response({'detail': 'Logistics job not found'}, status=status.HTTP_404_NOT_FOUND)
            
        if job.paid_by != 'BUYER':
            return Response({'detail': 'This job is not to be paid by the buyer'}, status=status.HTTP_400_BAD_REQUEST)
            
        job.payment_status = 'REQUESTED'
        job.save()
        
        create_alert(
            user=job.order.buyer,
            notification_type='SMS',
            title='Logistics Payment Requested',
            content=f"Transporter {request.user.username} has requested payment for logistics for Order #{job.order.id}."
        )
        
        return Response(TransportJobSerializer(job).data)


class TransportJobClientApproveView(APIView):
    def post(self, request, pk):
        if request.user.role != 'BUYER':
            return Response({'detail': 'Only buyers can approve logistics payments'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            job = TransportJob.objects.get(id=pk, order__buyer=request.user, payment_status='REQUESTED')
        except TransportJob.DoesNotExist:
            return Response({'detail': 'Pending payment request not found'}, status=status.HTTP_404_NOT_FOUND)
            
        with transaction.atomic():
            buyer = request.user
            if buyer.wallet_balance < job.estimated_cost:
                return Response({'detail': 'Insufficient wallet balance for logistics fee'}, status=status.HTTP_400_BAD_REQUEST)
            buyer.wallet_balance -= job.estimated_cost
            buyer.save()
            job.payment_status = 'PAID'
            job.save()
            
        create_alert(
            user=job.transporter,
            notification_type='SMS',
            title='Logistics Payment Approved',
            content=f"Buyer has paid the logistics fee for Order #{job.order.id}."
        )
        
        return Response(TransportJobSerializer(job).data)
