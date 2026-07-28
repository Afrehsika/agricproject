import datetime
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class StorageFacility(models.Model):
    FACILITY_TYPES = (
        ('SOLAR_COLD_ROOM', 'Solar-Powered Cold Room (4°C - 12°C)'),
        ('EVAPORATIVE_COOLER', 'Evaporative Cooling Chamber (14°C - 18°C)'),
        ('REFRIGERATED_WAREHOUSE', 'Refrigerated Cold Chain Warehouse'),
        ('VENTILATED_BARN', 'Inspected Ventilated Dry Storage'),
    )

    INSPECTION_STATUS = (
        ('PENDING', 'Pending Admin Inspection'),
        ('APPROVED', 'Approved & Verified'),
        ('REJECTED', 'Inspection Rejected'),
    )

    BADGE_TYPES = (
        ('GOLD_COLD_CHAIN', '❄️ Gold Cold-Chain Verified'),
        ('SILVER_COOL_ROOM', '🌿 Silver Solar-Cool Certified'),
        ('BRONZE_VENTILATED', '📦 Bronze Inspected Storage'),
        ('NONE', 'No Badge'),
    )

    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='storage_facilities')
    name = models.CharField(max_length=150)
    facility_type = models.CharField(max_length=50, choices=FACILITY_TYPES, default='SOLAR_COLD_ROOM')
    capacity = models.CharField(max_length=100, default='500 Crates / 10 Tonnes')
    location = models.CharField(max_length=200, default='Techiman Central Storage Hub')
    temperature_humidity = models.CharField(max_length=100, blank=True, default='8°C - 12°C / 85% RH')
    photo_url = models.CharField(max_length=255, blank=True, default='')

    # Verification & Admin Inspection
    status = models.CharField(max_length=30, choices=INSPECTION_STATUS, default='PENDING')
    badge = models.CharField(max_length=30, choices=BADGE_TYPES, default='NONE')
    admin_notes = models.TextField(blank=True, default='')
    inspected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='inspected_facilities')
    inspected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_badge_display()}) - {self.farmer.username}"


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
    storage_facility = models.ForeignKey(StorageFacility, on_delete=models.SET_NULL, null=True, blank=True, related_name='stored_produces')
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
        base_shelf_life = self.SHELF_LIVES.get(self.name, 7)
        
        # Shelf life multiplier based on verified storage facility badge
        multiplier = 1.0
        if self.storage_facility and self.storage_facility.status == 'APPROVED':
            badge_multipliers = {
                'GOLD_COLD_CHAIN': 2.5,
                'SILVER_COOL_ROOM': 1.8,
                'BRONZE_VENTILATED': 1.3,
            }
            multiplier = badge_multipliers.get(self.storage_facility.badge, 1.2)

        shelf_life_days = int(base_shelf_life * multiplier)

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

