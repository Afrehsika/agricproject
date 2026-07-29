import math
from rest_framework import serializers
from produce.serializers import ProduceSerializer
from .models import Order, CartItem, Dispute


class DisputeSerializer(serializers.ModelSerializer):
    raised_by_name = serializers.CharField(source='raised_by.username', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.username', read_only=True, allow_null=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Dispute
        fields = ('id', 'order', 'raised_by', 'raised_by_name', 'reason', 'reason_display',
                  'description', 'evidence_url', 'status', 'status_display', 'resolution',
                  'refund_amount', 'release_amount', 'resolution_notes', 'resolved_by',
                  'resolved_by_name', 'created_at', 'updated_at')
        read_only_fields = ('id', 'raised_by', 'created_at', 'updated_at')


class OrderSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source='buyer.username', read_only=True)
    buyer_phone = serializers.CharField(source='buyer.phone_number', read_only=True)
    produce_details = ProduceSerializer(source='produce', read_only=True)
    transporter_details = serializers.SerializerMethodField(read_only=True)
    latest_dispute = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'buyer', 'buyer_name', 'buyer_phone', 'produce', 'produce_details',
                  'quantity', 'total_price', 'status', 'payment_status', 'delivery_type',
                  'created_at', 'transporter_details', 'latest_dispute')
        read_only_fields = ('id', 'buyer', 'total_price')

    def get_transporter_details(self, obj):
        from logistics.models import TransportJob
        try:
            job = obj.transport_job
            if job.transporter:
                return {
                    'id': job.transporter.id,
                    'job_id': job.id,
                    'username': job.transporter.username,
                    'phone_number': job.transporter.phone_number,
                    'status': job.status,
                    'vehicle_type': job.vehicle_type,
                    'estimated_cost': float(job.estimated_cost),
                    'payment_status': job.payment_status
                }
            return {
                'job_id': job.id,
                'status': job.status,
                'vehicle_type': job.vehicle_type,
                'estimated_cost': float(job.estimated_cost),
                'payment_status': job.payment_status
            }
        except TransportJob.DoesNotExist:
            return None

    def get_latest_dispute(self, obj):
        try:
            dispute = obj.disputes.order_by('-created_at').first()
            if dispute:
                return DisputeSerializer(dispute).data
        except Exception:
            return None
        return None




class CartItemSerializer(serializers.ModelSerializer):
    produce_details = ProduceSerializer(source='produce', read_only=True)
    subtotal = serializers.SerializerMethodField()
    estimated_logistics = serializers.SerializerMethodField()
    total_with_logistics = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ('id', 'produce', 'produce_details', 'quantity', 'subtotal',
                  'estimated_logistics', 'total_with_logistics', 'created_at')
        read_only_fields = ('id', 'created_at')

    def _calc_logistics(self, obj):
        """Haversine estimate: same formula as OrderCreateView."""
        buyer = self.context.get('buyer')
        if not buyer:
            return 0.0
        try:
            lat1, lon1 = float(buyer.latitude), float(buyer.longitude)
            lat2, lon2 = float(obj.produce.farmer.latitude), float(obj.produce.farmer.longitude)
            distance = math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) * 111.0
            if distance < 1:
                distance = 1.0
            return round(10.0 + (distance * 2.5) + (obj.quantity * 1.0), 2)
        except Exception:
            return 0.0

    def get_subtotal(self, obj):
        return float(obj.produce.price_per_unit * obj.quantity)

    def get_estimated_logistics(self, obj):
        return self._calc_logistics(obj)

    def get_total_with_logistics(self, obj):
        return round(self.get_subtotal(obj) + self._calc_logistics(obj), 2)
