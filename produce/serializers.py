from rest_framework import serializers
from .models import Produce, StorageFacility


class StorageFacilitySerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.username', read_only=True)
    badge_display = serializers.CharField(source='get_badge_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = StorageFacility
        fields = ('id', 'farmer', 'farmer_name', 'name', 'facility_type', 'capacity',
                  'location', 'temperature_humidity', 'photo_url', 'status', 'status_display',
                  'badge', 'badge_display', 'admin_notes', 'inspected_at', 'created_at')
        read_only_fields = ('id', 'farmer', 'status', 'badge', 'admin_notes', 'inspected_at', 'created_at')


class ProduceSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.username', read_only=True)
    farmer_phone = serializers.CharField(source='farmer.phone_number', read_only=True)
    farmer_lat = serializers.FloatField(source='farmer.latitude', read_only=True)
    farmer_lng = serializers.FloatField(source='farmer.longitude', read_only=True)
    farmer_district = serializers.CharField(source='farmer.district', read_only=True)
    farmer_region = serializers.CharField(source='farmer.region', read_only=True)
    suggested_price = serializers.FloatField(read_only=True)
    calculated_recommendation_price = serializers.FloatField(read_only=True)
    storage_facility_details = StorageFacilitySerializer(source='storage_facility', read_only=True)

    class Meta:
        model = Produce
        fields = ('id', 'farmer', 'farmer_name', 'farmer_phone', 'farmer_lat', 'farmer_lng',
                  'farmer_district', 'farmer_region', 'storage_facility', 'storage_facility_details',
                  'name', 'variety', 'quantity_available', 'unit', 'price_per_unit', 'original_listing_price',
                  'demand_level', 'recommended_discount_price', 'discount_recommendation_status',
                  'calculated_recommendation_price',
                  'harvest_date', 'posting_date', 'predicted_rot_date', 'freshness_score', 
                  'suggested_price', 'description', 'status', 'image_url')
        read_only_fields = ('id', 'farmer', 'predicted_rot_date', 'freshness_score', 'suggested_price', 'calculated_recommendation_price')



