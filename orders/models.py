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
        ('REJECTED', 'Rejected by Buyer'),
        ('DISPUTED', 'In Dispute'),
        ('CANCELLED', 'Cancelled'),
    )
    
    PAYMENT_CHOICES = (
        ('UNPAID', 'Unpaid'),
        ('HELD_IN_ESCROW', 'Held in Escrow'),
        ('RELEASED', 'Released to Farmer'),
        ('REFUNDED', 'Refunded to Buyer'),
        ('DISPUTED', 'Disputed'),
        ('PARTIALLY_REFUNDED', 'Partially Refunded'),
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


class Dispute(models.Model):
    """Tracks buyer rejections, quality claims, damage issues, and escrow resolution."""
    REASON_CHOICES = (
        ('SPOILED_ROTTEN', 'Spoiled or Rotten Produce'),
        ('WRONG_VARIETY_QUALITY', 'Wrong Variety or Substandard Quality'),
        ('QUANTITY_SHORTAGE', 'Quantity Shortage / Missing Items'),
        ('DAMAGED_IN_TRANSIT', 'Cargo Damaged in Transit'),
        ('OTHER', 'Other Reason'),
    )

    STATUS_CHOICES = (
        ('OPEN', 'Open Dispute'),
        ('UNDER_REVIEW', 'Under Review'),
        ('RESOLVED_REFUND', 'Resolved (Full Refund to Buyer)'),
        ('RESOLVED_RELEASE', 'Resolved (Escrow Released to Farmer)'),
        ('RESOLVED_PARTIAL', 'Resolved (Partial Refund / Split)'),
        ('CANCELLED', 'Dispute Cancelled'),
    )

    RESOLUTION_CHOICES = (
        ('REFUND_BUYER', 'Full Refund to Buyer'),
        ('RELEASE_FARMER', 'Full Escrow Release to Farmer'),
        ('PARTIAL_SPLIT', 'Partial Split Refund'),
        ('DISMISS', 'Disputed Claim Dismissed'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='disputes')
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='disputes_raised')
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default='SPOILED_ROTTEN')
    description = models.TextField()
    evidence_url = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='OPEN')
    resolution = models.CharField(max_length=25, choices=RESOLUTION_CHOICES, blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    release_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_disputes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dispute #{self.id} on Order #{self.order.id} ({self.get_status_display()})"


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

