from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from produce.models import Produce


class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid (Held in Escrow)'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    )
    
    PAYMENT_CHOICES = (
        ('UNPAID', 'Unpaid'),
        ('HELD_IN_ESCROW', 'Held in Escrow'),
        ('RELEASED', 'Released to Farmer'),
        ('REFUNDED', 'Refunded to Buyer'),
    )
    
    DELIVERY_CHOICES = (
        ('SELF_PICKUP', 'Self Pickup'),
        ('PLATFORM_DELIVERY', 'Platform Organized Delivery'),
    )
    
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    produce = models.ForeignKey(Produce, on_delete=models.CASCADE, related_name='orders')
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='UNPAID')
    delivery_type = models.CharField(max_length=25, choices=DELIVERY_CHOICES, default='PLATFORM_DELIVERY')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.produce.name} for {self.buyer.username}"


class CartItem(models.Model):
    """Shopping cart - buyer adds items here before wallet checkout."""
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart_items')
    produce = models.ForeignKey(Produce, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('buyer', 'produce')

    def __str__(self):
        return f"Cart: {self.buyer.username} - {self.produce.name} x{self.quantity}"
