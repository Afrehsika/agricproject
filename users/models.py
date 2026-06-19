from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('FARMER', 'Farmer'),
        ('BUYER', 'Buyer'),
        ('TRANSPORTER', 'Transporter / Logistics Provider'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='FARMER')
    phone_number = models.CharField(max_length=20, blank=True, default='')
    region = models.CharField(max_length=100, default='Bono East')
    district = models.CharField(max_length=100, default='Techiman Municipal')
    
    # Coordinates for Techiman region map by default
    latitude = models.FloatField(default=7.5848)
    longitude = models.FloatField(default=-1.9392)
    
    # Wallet balance for Escrow payment releases
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Connection(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_connections')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_connections')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"Connection: {self.sender.username} -> {self.receiver.username} ({self.status})"


class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Msg: {self.sender.username} -> {self.receiver.username} at {self.created_at}"


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = (
        ('SMS', 'SMS Alert'),
        ('EMAIL', 'Email Alert'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.notification_type} Alert for {self.user.username} - {self.title} at {self.created_at}"


