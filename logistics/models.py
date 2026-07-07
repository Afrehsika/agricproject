from django.db import models
from django.conf import settings
from orders.models import Order


class TransportJob(models.Model):
    STATUS_CHOICES = (
        ('PENDING_MATCH', 'Pending Transporter Match'),
        ('PENDING_APPROVAL', 'Pending Buyer Approval'),
        ('MATCHED', 'Transporter Matched'),
        ('PICKED_UP', 'Picked Up / In Transit'),
        ('DELIVERED', 'Delivered'),
    )
    
    VEHICLE_CHOICES = (
        ('Aboboyaa Tricycle', 'Aboboyaa Tricycle'),
        ('KIA Bongo 1.5 Ton', 'KIA Bongo 1.5 Ton'),
        ('Cargo Truck', 'Cargo Truck'),
    )
    
    PAID_BY_CHOICES = (
        ('FARMER', 'Farmer'),
        ('BUYER', 'Buyer'),
        ('UNSET', 'Unset'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('REQUESTED', 'Requested'),
        ('PAID', 'Paid'),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='transport_job')
    transporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='transport_jobs')
    vehicle_type = models.CharField(max_length=30, choices=VEHICLE_CHOICES, default='Aboboyaa Tricycle')
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING_MATCH')
    
    paid_by = models.CharField(max_length=10, choices=PAID_BY_CHOICES, default='UNSET')
    payment_status = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    
    pickup_time = models.DateTimeField(null=True, blank=True)
    delivery_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Logistics #{self.id} for Order #{self.order.id} (Status: {self.status})"
