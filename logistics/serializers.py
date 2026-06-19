from rest_framework import serializers
from orders.serializers import OrderSerializer
from .models import TransportJob


class TransportJobSerializer(serializers.ModelSerializer):
    order_details = OrderSerializer(source='order', read_only=True)
    transporter_name = serializers.CharField(source='transporter.username', read_only=True)
    transporter_phone = serializers.CharField(source='transporter.phone_number', read_only=True)

    class Meta:
        model = TransportJob
        fields = ('id', 'order', 'order_details', 'transporter', 'transporter_name', 
                  'transporter_phone', 'vehicle_type', 'estimated_cost', 'status', 
                  'pickup_time', 'delivery_time')
        read_only_fields = ('id', 'estimated_cost')
