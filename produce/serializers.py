from rest_framework import serializers
from .models import Produce


class ProduceSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.username', read_only=True)
    farmer_phone = serializers.CharField(source='farmer.phone_number', read_only=True)
    farmer_lat = serializers.FloatField(source='farmer.latitude', read_only=True)
    farmer_lng = serializers.FloatField(source='farmer.longitude', read_only=True)
    suggested_price = serializers.FloatField(read_only=True)

    class Meta:
        model = Produce
        fields = ('id', 'farmer', 'farmer_name', 'farmer_phone', 'farmer_lat', 'farmer_lng',
                  'name', 'variety', 'quantity_available', 'unit', 'price_per_unit', 
                  'harvest_date', 'posting_date', 'predicted_rot_date', 'freshness_score', 
                  'suggested_price', 'description', 'status', 'image_url')
        read_only_fields = ('id', 'farmer', 'predicted_rot_date', 'freshness_score', 'suggested_price')
