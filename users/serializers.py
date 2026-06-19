from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Connection, Message, Notification

User = get_user_model()



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'role', 'phone_number', 
                  'region', 'district', 'latitude', 'longitude', 'wallet_balance')
        read_only_fields = ('id', 'wallet_balance')


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'email', 'role', 'phone_number', 
                  'region', 'district', 'latitude', 'longitude')
        write_only_fields = ('password',)

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role=validated_data.get('role', 'FARMER'),
            phone_number=validated_data.get('phone_number', ''),
            region=validated_data.get('region', 'Bono East'),
            district=validated_data.get('district', 'Techiman Municipal'),
            latitude=validated_data.get('latitude', 7.5848),
            longitude=validated_data.get('longitude', -1.9392)
        )
        return user


class ConnectionSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    sender_role = serializers.CharField(source='sender.role', read_only=True)
    receiver_username = serializers.CharField(source='receiver.username', read_only=True)
    receiver_role = serializers.CharField(source='receiver.role', read_only=True)

    class Meta:
        model = Connection
        fields = ('id', 'sender', 'sender_username', 'sender_role', 
                  'receiver', 'receiver_username', 'receiver_role', 
                  'status', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    receiver_username = serializers.CharField(source='receiver.username', read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'sender', 'sender_username', 'receiver', 'receiver_username', 
                  'content', 'created_at', 'is_read')
        read_only_fields = ('id', 'created_at')


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'user', 'notification_type', 'title', 'content', 'created_at', 'is_read')
        read_only_fields = ('id', 'created_at')


