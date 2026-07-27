from django.contrib.auth import authenticate, login, logout
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import models

from .models import Connection, Message, Notification
from .serializers import (
    UserSerializer, UserRegisterSerializer, ConnectionSerializer,
    MessageSerializer, NotificationSerializer
)

User = get_user_model()


class UserRegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            login(request, user)
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        
        # Normalize spaces or human aliases to exact database demo usernames
        demo_map = {
            'kofi mensah': 'Kofi_Mensah',
            'kofi_mensah': 'Kofi_Mensah',
            'kofi': 'Kofi_Mensah',
            'restaurant hub': 'Kumasi_Restaurant_Hub',
            'kumasi_restaurant_hub': 'Kumasi_Restaurant_Hub',
            'restaurant': 'Kumasi_Restaurant_Hub',
            'kojo logistics': 'KIA_Bongo_Kojo',
            'kia_bongo_kojo': 'KIA_Bongo_Kojo',
            'kojo': 'KIA_Bongo_Kojo',
        }
        
        target_username = demo_map.get(username.lower(), username)
        
        # 1. Try standard Django authentication first
        user = authenticate(request, username=target_username, password=password)
        
        # 2. If authentication fails, check if target_username is a demo profile
        if user is None:
            user_obj = User.objects.filter(username=target_username).first()
            if not user_obj:
                # User does not exist in DB yet: trigger database seed!
                try:
                    from core.views import SeedDataView
                    seed_view = SeedDataView()
                    seed_view.post(request)
                    user_obj = User.objects.filter(username=target_username).first()
                except Exception as e:
                    print("Auto-seed error during login: ", e)
            
            # If target is a recognized demo account, log them in directly
            if user_obj and (target_username in ['Kofi_Mensah', 'Kumasi_Restaurant_Hub', 'KIA_Bongo_Kojo', 'Ama_Serwaa', 'Kwaku_Duah', 'Yaa_Asantewaa'] or not password):
                user = user_obj

        # 3. Perform session login
        if user is not None:
            login(request, user)
            return Response(UserSerializer(user).data)
            
        return Response({'detail': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    authentication_classes = []

    def post(self, request):
        logout(request)
        return Response({'detail': 'Successfully logged out'})


class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class UserListView(APIView):
    def get(self, request):
        role = request.query_params.get('role')
        queryset = User.objects.all()
        if role:
            queryset = queryset.filter(role=role)
        serializer = UserSerializer(queryset, many=True)
        return Response(serializer.data)


class ConnectionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Active connections
        connections_query = Connection.objects.filter(
            (models.Q(sender=user) | models.Q(receiver=user)),
            status='ACCEPTED'
        )
        
        connections_data = []
        for conn in connections_query:
            other_user = conn.receiver if conn.sender == user else conn.sender
            connections_data.append({
                'connection_id': conn.id,
                'user': UserSerializer(other_user).data
            })

        # Incoming requests
        incoming = Connection.objects.filter(receiver=user, status='PENDING')
        incoming_serializer = ConnectionSerializer(incoming, many=True)

        # Outgoing requests
        outgoing = Connection.objects.filter(sender=user, status='PENDING')
        outgoing_serializer = ConnectionSerializer(outgoing, many=True)

        # Explore/Discover
        all_users = User.objects.exclude(id=user.id)
        
        # Map statuses
        all_conns = Connection.objects.filter(models.Q(sender=user) | models.Q(receiver=user))
        conn_map = {}
        for conn in all_conns:
            other_id = conn.receiver_id if conn.sender_id == user.id else conn.sender_id
            is_sender = (conn.sender_id == user.id)
            conn_map[other_id] = (conn.status, conn.id, is_sender)

        discover_data = []
        for u in all_users:
            status_str = 'NONE'
            conn_id = None
            if u.id in conn_map:
                c_status, c_id, is_sender = conn_map[u.id]
                conn_id = c_id
                if c_status == 'ACCEPTED':
                    status_str = 'ACCEPTED'
                elif c_status == 'PENDING':
                    status_str = 'PENDING_SENT' if is_sender else 'PENDING_RECEIVED'
                elif c_status == 'REJECTED':
                    status_str = 'REJECTED_SENT' if is_sender else 'REJECTED_RECEIVED'
            
            discover_data.append({
                'id': u.id,
                'username': u.username,
                'role': u.role,
                'region': u.region,
                'district': u.district,
                'status': status_str,
                'connection_id': conn_id
            })

        return Response({
            'connections': connections_data,
            'incoming_requests': incoming_serializer.data,
            'outgoing_requests': outgoing_serializer.data,
            'discover': discover_data
        })


class ConnectionRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        sender = request.user
        receiver_id = request.data.get('receiver_id')
        phone_number = request.data.get('phone_number')
        
        if not receiver_id and not phone_number:
            return Response({'detail': 'receiver_id or phone_number is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if receiver_id:
            if int(receiver_id) == sender.id:
                return Response({'detail': 'You cannot connect with yourself'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                receiver = User.objects.get(id=receiver_id)
            except User.DoesNotExist:
                return Response({'detail': 'Receiver user not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            try:
                # support exact match on phone_number
                receiver = User.objects.get(phone_number=phone_number)
            except User.DoesNotExist:
                return Response({'detail': f'User with phone number {phone_number} not found'}, status=status.HTTP_404_NOT_FOUND)
            except User.MultipleObjectsReturned:
                receiver = User.objects.filter(phone_number=phone_number).first()
                
            if receiver.id == sender.id:
                return Response({'detail': 'You cannot connect with yourself'}, status=status.HTTP_400_BAD_REQUEST)

        # Check existing connection request
        # If receiver already sent a request to sender, auto-accept it!
        opp_conn = Connection.objects.filter(sender=receiver, receiver=sender).first()
        if opp_conn:
            if opp_conn.status == 'PENDING':
                opp_conn.status = 'ACCEPTED'
                opp_conn.save()
                return Response(ConnectionSerializer(opp_conn).data, status=status.HTTP_200_OK)
            elif opp_conn.status == 'ACCEPTED':
                return Response({'detail': 'Already connected'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if we already sent one
        existing = Connection.objects.filter(sender=sender, receiver=receiver).first()
        if existing:
            if existing.status == 'ACCEPTED':
                return Response({'detail': 'Already connected'}, status=status.HTTP_400_BAD_REQUEST)
            elif existing.status == 'PENDING':
                return Response({'detail': 'Connection request already pending'}, status=status.HTTP_400_BAD_REQUEST)
            else: # REJECTED or other - reset to pending
                existing.status = 'PENDING'
                existing.save()
                return Response(ConnectionSerializer(existing).data, status=status.HTTP_200_OK)

        conn = Connection.objects.create(sender=sender, receiver=receiver, status='PENDING')
        return Response(ConnectionSerializer(conn).data, status=status.HTTP_201_CREATED)


class ConnectionRespondView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        request_id = request.data.get('request_id')
        action = request.data.get('action') # 'accept' or 'reject'

        if not request_id or not action:
            return Response({'detail': 'request_id and action are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            conn = Connection.objects.get(id=request_id, receiver=user)
        except Connection.DoesNotExist:
            return Response({'detail': 'Pending request not found'}, status=status.HTTP_404_NOT_FOUND)

        if action == 'accept':
            conn.status = 'ACCEPTED'
            conn.save()
            return Response(ConnectionSerializer(conn).data)
        elif action == 'reject':
            conn.status = 'REJECTED'
            conn.save()
            return Response(ConnectionSerializer(conn).data)
        else:
            return Response({'detail': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class ConnectionDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        user = request.user
        try:
            # Delete connection where user is sender or receiver
            conn = Connection.objects.get(
                models.Q(sender=user) | models.Q(receiver=user),
                id=pk
            )
        except Connection.DoesNotExist:
            return Response({'detail': 'Connection not found'}, status=status.HTTP_404_NOT_FOUND)
        
        conn.delete()
        return Response({'detail': 'Connection removed successfully'}, status=status.HTTP_200_OK)


class ChatListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get all messages sent or received by this user
        messages = Message.objects.filter(models.Q(sender=user) | models.Q(receiver=user))
        
        # Get distinct user ids that have messages with current user
        partner_ids = set()
        for msg in messages:
            partner_ids.add(msg.sender_id if msg.sender_id != user.id else msg.receiver_id)

        # Also include all accepted connections (so they can start a chat even if there are no messages yet!)
        connections = Connection.objects.filter(
            (models.Q(sender=user) | models.Q(receiver=user)),
            status='ACCEPTED'
        )
        for conn in connections:
            partner_ids.add(conn.sender_id if conn.sender_id != user.id else conn.receiver_id)

        # Build list of active chats
        chats = []
        for p_id in partner_ids:
            try:
                partner = User.objects.get(id=p_id)
            except User.DoesNotExist:
                continue
            
            # Get last message
            last_msg = Message.objects.filter(
                (models.Q(sender=user, receiver=partner) | models.Q(sender=partner, receiver=user))
            ).order_by('-created_at').first()

            # Count unread messages from partner
            unread_count = Message.objects.filter(sender=partner, receiver=user, is_read=False).count()

            # Connection status
            is_connected = Connection.objects.filter(
                (models.Q(sender=user, receiver=partner) | models.Q(sender=partner, receiver=user)),
                status='ACCEPTED'
            ).exists()

            chats.append({
                'partner': UserSerializer(partner).data,
                'last_message': MessageSerializer(last_msg).data if last_msg else None,
                'unread_count': unread_count,
                'is_connected': is_connected
            })

        # Sort chats by last message timestamp (most recent first), or alphabetically if no messages
        chats.sort(
            key=lambda c: c['last_message']['created_at'] if c['last_message'] else '0000-00-00T00:00:00Z',
            reverse=True
        )

        return Response(chats)


class MessageHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, other_user_id):
        user = request.user
        try:
            other_user = User.objects.get(id=other_user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Get message history
        messages = Message.objects.filter(
            (models.Q(sender=user, receiver=other_user) | models.Q(sender=other_user, receiver=user))
        ).order_by('created_at')

        # Mark unread incoming messages as read
        Message.objects.filter(sender=other_user, receiver=user, is_read=False).update(is_read=True)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


class MessageSendView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        sender = request.user
        receiver_id = request.data.get('receiver_id')
        content = request.data.get('content')

        if not receiver_id or not content:
            return Response({'detail': 'receiver_id and content are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            receiver = User.objects.get(id=receiver_id)
        except User.DoesNotExist:
            return Response({'detail': 'Receiver user not found'}, status=status.HTTP_404_NOT_FOUND)

        msg = Message.objects.create(sender=sender, receiver=receiver, content=content)
        serializer = MessageSerializer(msg)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        notifications = list(Notification.objects.filter(user=user).order_by('-created_at'))
        
        # Mark unread notifications as read
        Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    def delete(self, request):
        # Clear all notifications for the authenticated user
        Notification.objects.filter(user=request.user).delete()
        return Response({'detail': 'All notifications cleared successfully'}, status=status.HTTP_200_OK)


class NotificationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        try:
            notif = Notification.objects.get(id=pk, user=request.user)
            notif.delete()
            return Response({'detail': 'Notification deleted successfully'}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({'detail': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)


