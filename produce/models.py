import datetime
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Produce(models.Model):
    CROP_CHOICES = (
        ('Tomatoes', 'Tomatoes'),
        ('Habanero Peppers', 'Habanero Peppers'),
        ('Garden Eggs', 'Garden Eggs'),
        ('Okra', 'Okra'),
        ('Leafy Greens', 'Leafy Greens'),
    )
    
    UNIT_CHOICES = (
        ('Crates', 'Crates'),
        ('Sacks', 'Sacks'),
        ('Baskets', 'Baskets'),
        ('Boxes', 'Boxes'),
    )
    
    STATUS_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved'),
        ('SOLD', 'Sold'),
    )
    
    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='produces')
    name = models.CharField(max_length=50, choices=CROP_CHOICES)
    variety = models.CharField(max_length=100, blank=True, default='')
    quantity_available = models.IntegerField(validators=[MinValueValidator(1)])
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='Crates')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    
    harvest_date = models.DateField()
    posting_date = models.DateField(default=datetime.date.today)
    predicted_rot_date = models.DateField(blank=True, null=True)
    freshness_score = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    image_url = models.CharField(max_length=255, blank=True, default='')

    # Average shelf lives in days for crops under typical Ghanaian climate (unrefrigerated)
    SHELF_LIVES = {
        'Tomatoes': 7,
        'Habanero Peppers': 12,
        'Garden Eggs': 10,
        'Okra': 4,
        'Leafy Greens': 3,
    }

    def save(self, *args, **kwargs):
        # Determine average shelf life for the selected crop
        shelf_life_days = self.SHELF_LIVES.get(self.name, 7)
        
        # Calculate predicted rot date based on harvest_date
        if not self.predicted_rot_date or self.harvest_date:
            self.predicted_rot_date = self.harvest_date + datetime.timedelta(days=shelf_life_days)
        
        # Calculate freshness score based on time elapsed between harvest and posting
        elapsed_days = (self.posting_date - self.harvest_date).days
        if elapsed_days < 0:
            elapsed_days = 0
            
        freshness = int((1.0 - (elapsed_days / shelf_life_days)) * 100)
        self.freshness_score = max(0, min(100, freshness))
        
        super().save(*args, **kwargs)

    @property
    def suggested_price(self):
        """AI pricing engine suggesting discounts based on freshness and urgency"""
        base_price = float(self.price_per_unit)
        if self.freshness_score >= 80:
            return round(base_price, 2)  # Full value
        elif self.freshness_score >= 50:
            return round(base_price * 0.85, 2)  # 15% discount (moderate urgency)
        elif self.freshness_score >= 20:
            return round(base_price * 0.60, 2)  # 40% discount (high urgency)
        else:
            return round(base_price * 0.30, 2)  # 70% discount (clearance/flash sale)

    def __str__(self):
        return f"{self.variety or self.name} - {self.quantity_available} {self.unit} by {self.farmer.username}"
