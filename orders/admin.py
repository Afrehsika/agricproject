from decimal import Decimal
from django.contrib import admin, messages
from django.db import transaction
from django.utils.html import format_html
from .models import Order, Dispute
from payments.models import WalletTransaction
from users.notifications import create_alert


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'produce', 'quantity', 'total_price', 'status', 'payment_status', 'delivery_type', 'created_at')
    list_filter = ('status', 'payment_status', 'delivery_type', 'created_at')
    search_fields = ('id', 'buyer__username', 'produce__name')
    ordering = ('-id',)


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'order_link', 'raised_by', 'reason', 'status_badge', 
        'resolution', 'refund_amount', 'release_amount', 'created_at'
    )
    list_filter = ('status', 'reason', 'resolution', 'created_at')
    search_fields = ('id', 'order__id', 'raised_by__username', 'description', 'resolution_notes')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['action_resolve_full_refund', 'action_resolve_release_farmer', 'action_resolve_partial_split_50_50']

    def order_link(self, obj):
        return format_html('<a href="/admin/orders/order/{}/change/">Order #{}</a>', obj.order.id, obj.order.id)
    order_link.short_description = "Order"

    def status_badge(self, obj):
        colors = {
            'OPEN': '#ef4444',
            'UNDER_REVIEW': '#f59e0b',
            'RESOLVED_REFUND': '#8b5cf6',
            'RESOLVED_RELEASE': '#10b981',
            'RESOLVED_PARTIAL': '#0284c7',
            'CANCELLED': '#64748b'
        }
        color = colors.get(obj.status, '#64748b')
        return format_html('<span style="background:{}; color:#fff; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Dispute Status"

    @admin.action(description="⚖️ Mediate: Grant Full Refund to Buyer (100%)")
    def action_resolve_full_refund(self, request, queryset):
        count = 0
        for dispute in queryset:
            if dispute.status in ['RESOLVED_REFUND', 'RESOLVED_RELEASE', 'RESOLVED_PARTIAL', 'CANCELLED']:
                continue
            with transaction.atomic():
                order = dispute.order
                buyer = order.buyer
                produce = order.produce
                job = getattr(order, 'transport_job', None)
                logistics_fee = job.estimated_cost if (job and job.estimated_cost) else Decimal('0.00')

                refund_total = order.total_price
                if job and job.payment_status in ['PAID', 'REQUESTED']:
                    refund_total += logistics_fee

                buyer.wallet_balance += refund_total
                buyer.save()

                WalletTransaction.objects.create(
                    user=buyer,
                    transaction_type='PAYMENT',
                    amount=refund_total,
                    reference=f'AGRI-REFUND-{order.id}-{dispute.id}',
                    description=f'Admin Escrow Refund for Order #{order.id} (Dispute #{dispute.id})'
                )

                produce.quantity_available += order.quantity
                if produce.status == 'SOLD':
                    produce.status = 'AVAILABLE'
                produce.save()

                order.payment_status = 'REFUNDED'
                order.status = 'CANCELLED'
                order.save()

                dispute.status = 'RESOLVED_REFUND'
                dispute.resolution = 'REFUND_BUYER'
                dispute.refund_amount = refund_total
                dispute.resolution_notes = 'Resolved via Admin Panel: 100% refund granted to buyer.'
                dispute.resolved_by = request.user
                dispute.save()

                create_alert(
                    user=buyer,
                    notification_type='SMS',
                    title='Admin Dispute Resolution - Refund Granted',
                    content=f"Dispute #{dispute.id} resolved by Admin. GHS {refund_total:.2f} refunded to your wallet."
                )
                create_alert(
                    user=order.produce.farmer,
                    notification_type='SMS',
                    title='Admin Dispute Resolution',
                    content=f"Dispute #{dispute.id} on Order #{order.id} resolved by Admin (Full Refund to Buyer)."
                )
                count += 1
        self.message_user(request, f"Successfully resolved {count} dispute(s) with Full Refund to Buyer.", messages.SUCCESS)

    @admin.action(description="🌾 Mediate: Release Escrow to Farmer (Dismiss Dispute)")
    def action_resolve_release_farmer(self, request, queryset):
        count = 0
        for dispute in queryset:
            if dispute.status in ['RESOLVED_REFUND', 'RESOLVED_RELEASE', 'RESOLVED_PARTIAL', 'CANCELLED']:
                continue
            with transaction.atomic():
                order = dispute.order
                farmer = order.produce.farmer
                job = getattr(order, 'transport_job', None)
                logistics_fee = job.estimated_cost if (job and job.estimated_cost) else Decimal('0.00')

                farmer.wallet_balance += order.total_price
                farmer.save()

                WalletTransaction.objects.create(
                    user=farmer,
                    transaction_type='PAYOUT',
                    amount=order.total_price,
                    reference=f'AGRI-ESCROW-REL-{order.id}',
                    description=f'Admin Escrow release for Order #{order.id} (Dispute #{dispute.id})'
                )

                if job and job.transporter:
                    job.transporter.wallet_balance += logistics_fee
                    job.transporter.save()
                    WalletTransaction.objects.create(
                        user=job.transporter,
                        transaction_type='PAYOUT',
                        amount=logistics_fee,
                        reference=f'AGRI-TRANSPORT-{job.id}',
                        description=f'Delivery fee released for Order #{order.id}'
                    )

                order.payment_status = 'RELEASED'
                order.status = 'DELIVERED'
                order.save()

                dispute.status = 'RESOLVED_RELEASE'
                dispute.resolution = 'RELEASE_FARMER'
                dispute.release_amount = order.total_price
                dispute.resolution_notes = 'Resolved via Admin Panel: Escrow released to farmer.'
                dispute.resolved_by = request.user
                dispute.save()

                create_alert(
                    user=order.buyer,
                    notification_type='SMS',
                    title='Admin Dispute Resolution',
                    content=f"Dispute #{dispute.id} resolved by Admin. Escrow released to farmer."
                )
                create_alert(
                    user=farmer,
                    notification_type='SMS',
                    title='Admin Dispute Resolution - Escrow Released',
                    content=f"Dispute #{dispute.id} resolved! GHS {order.total_price:.2f} credited to your wallet."
                )
                count += 1
        self.message_user(request, f"Successfully resolved {count} dispute(s) by releasing escrow to farmer.", messages.SUCCESS)

    @admin.action(description="✂️ Mediate: Partial Split 50/50 Refund")
    def action_resolve_partial_split_50_50(self, request, queryset):
        count = 0
        for dispute in queryset:
            if dispute.status in ['RESOLVED_REFUND', 'RESOLVED_RELEASE', 'RESOLVED_PARTIAL', 'CANCELLED']:
                continue
            with transaction.atomic():
                order = dispute.order
                buyer = order.buyer
                farmer = order.produce.farmer
                job = getattr(order, 'transport_job', None)
                logistics_fee = job.estimated_cost if (job and job.estimated_cost) else Decimal('0.00')

                half_amount = round(order.total_price / Decimal('2.0'), 2)

                buyer.wallet_balance += half_amount
                buyer.save()
                WalletTransaction.objects.create(
                    user=buyer,
                    transaction_type='PAYMENT',
                    amount=half_amount,
                    reference=f'AGRI-PARTIAL-REFUND-{order.id}',
                    description=f'Admin 50% Partial Refund for Order #{order.id}'
                )

                farmer.wallet_balance += half_amount
                farmer.save()
                WalletTransaction.objects.create(
                    user=farmer,
                    transaction_type='PAYOUT',
                    amount=half_amount,
                    reference=f'AGRI-PARTIAL-REL-{order.id}',
                    description=f'Admin 50% Partial Escrow Release for Order #{order.id}'
                )

                if job and job.transporter:
                    job.transporter.wallet_balance += logistics_fee
                    job.transporter.save()
                    WalletTransaction.objects.create(
                        user=job.transporter,
                        transaction_type='PAYOUT',
                        amount=logistics_fee,
                        reference=f'AGRI-TRANSPORT-{job.id}',
                        description=f'Delivery fee for Order #{order.id}'
                    )

                order.payment_status = 'PARTIALLY_REFUNDED'
                order.status = 'DELIVERED'
                order.save()

                dispute.status = 'RESOLVED_PARTIAL'
                dispute.resolution = 'PARTIAL_SPLIT'
                dispute.refund_amount = half_amount
                dispute.release_amount = half_amount
                dispute.resolution_notes = 'Resolved via Admin Panel: 50% split refund applied.'
                dispute.resolved_by = request.user
                dispute.save()

                count += 1
        self.message_user(request, f"Successfully resolved {count} dispute(s) with 50/50 partial split.", messages.SUCCESS)


