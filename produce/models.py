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

    DEMAND_CHOICES = (
        ('HIGH', 'High Demand'),
        ('MEDIUM', 'Medium Demand'),
        ('LOW', 'Low Demand'),
    )

    RECOMMENDATION_STATUS_CHOICES = (
        ('NONE', 'No Recommendation Needed'),
        ('PENDING_FARMER_DECISION', 'Pending Farmer Decision'),
        ('ACCEPTED', 'Accepted by Farmer'),
        ('REJECTED', 'Rejected by Farmer'),
    )
    
    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='produces')
    storage_facility = models.ForeignKey(StorageFacility, on_delete=models.SET_NULL, null=True, blank=True, related_name='stored_produces')
    name = models.CharField(max_length=50, choices=CROP_CHOICES)
    variety = models.CharField(max_length=100, blank=True, default='')
    quantity_available = models.IntegerField(validators=[MinValueValidator(1)])
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='Crates')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    original_listing_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Market Demand & Recommendation Tracking
    demand_level = models.CharField(max_length=20, choices=DEMAND_CHOICES, default='MEDIUM')
    recommended_discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_recommendation_status = models.CharField(max_length=30, choices=RECOMMENDATION_STATUS_CHOICES, default='NONE')

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
        # Store original listing price on first save
        if not self.original_listing_price:
            self.original_listing_price = self.price_per_unit

        # Determine average shelf life for the selected crop
        base_shelf_life = self.SHELF_LIVES.get(self.name, 7)
        
        # Shelf life multiplier based on verified storage facility badge
        has_approved_storage = bool(self.storage_facility and self.storage_facility.status == 'APPROVED')
        multiplier = 1.0
        if has_approved_storage:
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

        # Dynamic Demand & Storage Recommendation Rules:
        # Rule A: High Demand OR Gold Cold-Chain Storage -> Nothing happens to initial price!
        is_gold_cold_chain = has_approved_storage and self.storage_facility.badge == 'GOLD_COLD_CHAIN'
        if self.demand_level == 'HIGH' or is_gold_cold_chain:
            if self.discount_recommendation_status != 'ACCEPTED':
                self.recommended_discount_price = None
                self.discount_recommendation_status = 'NONE'
        else:
            # Rule B: Low/Medium Demand AND No/Low Cold Storage AND Freshness Dropping (< 85% or Low Demand)
            if self.freshness_score < 85 or self.demand_level == 'LOW':
                discount_rate = 0.15 if self.freshness_score >= 60 else (0.30 if self.freshness_score >= 35 else 0.45)
                base_ref_price = float(self.original_listing_price or self.price_per_unit)
                suggested_val = round(base_ref_price * (1.0 - discount_rate), 2)

                if self.discount_recommendation_status not in ['ACCEPTED', 'REJECTED']:
                    self.recommended_discount_price = suggested_val
                    self.discount_recommendation_status = 'PENDING_FARMER_DECISION'

        
        super().save(*args, **kwargs)

    @property
    def calculated_recommendation_price(self):
        """On-the-fly calculation for crops losing freshness"""
        if self.recommended_discount_price:
            return float(self.recommended_discount_price)
        if self.freshness_score < 85 and self.demand_level != 'HIGH':
            discount_rate = 0.15 if self.freshness_score >= 60 else (0.30 if self.freshness_score >= 35 else 0.45)
            base_ref = float(self.original_listing_price or self.price_per_unit)
            return round(base_ref * (1.0 - discount_rate), 2)
        return None

    @property
    def suggested_price(self):
        """Returns recommended discount price if pending/accepted, or price_per_unit"""
        if self.recommended_discount_price:
            return float(self.recommended_discount_price)
        return float(self.price_per_unit)

    def __str__(self):
        return f"{self.variety or self.name} - {self.quantity_available} {self.unit} by {self.farmer.username}"



