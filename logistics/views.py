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
            job.status = 'PICKED_UP'
            job.pickup_time = timezone.now()
            job.save()
            
            order.status = 'SHIPPED'
            order.save()
            
            # Send cargo picked up alerts
            create_alert(
                user=order.buyer,
                notification_type='SMS',
                title='Cargo In Transit',
                content=f"Your cargo for Order #{order.id} has been picked up by transporter {job.transporter.username} and is in transit."
            )
            create_alert(
                user=order.buyer,
                notification_type='EMAIL',
                title=f"Order #{order.id} - Cargo In Transit",
                content=f"Your cargo for Order #{order.id} has been picked up by {job.transporter.username} and is on its way."
            )
            create_alert(
                user=farmer,
                notification_type='SMS',
                title='Cargo Dispatched',
                content=f"Transporter {job.transporter.username} has picked up the cargo for Order #{order.id}."
            )
            
        elif new_status == 'DELIVERED':
            job.status = 'DELIVERED'
            job.delivery_time = timezone.now()
            job.save()
            
            order.status = 'DELIVERED'
            order.save()
            
            # Send cargo delivered alerts
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
