from decimal import Decimal
from django.contrib import admin, messages
from django.db import transaction
from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html
from .models import Order, Dispute
from payments.models import WalletTransaction
from users.notifications import create_alert


class DisputeInline(admin.StackedInline):
    model = Dispute
    extra = 0
    readonly_fields = ('raised_by', 'reason', 'description', 'evidence_url', 'status', 'resolution', 'refund_amount', 'release_amount', 'resolution_notes', 'resolved_by', 'created_at')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'produce', 'quantity', 'total_price', 'status', 'payment_status', 'delivery_type', 'created_at')
    list_filter = ('status', 'payment_status', 'delivery_type', 'created_at')
    search_fields = ('id', 'buyer__username', 'produce__name')
    ordering = ('-id',)
    readonly_fields = ('admin_dispute_mediation_banner',)
    inlines = [DisputeInline]

    fields = (
        'admin_dispute_mediation_banner',
        'buyer', 'produce', 'quantity', 'total_price', 'status', 'payment_status', 'delivery_type'
    )

    def admin_dispute_mediation_banner(self, obj):
        if not obj or not obj.id:
            return ""
        dispute = obj.disputes.order_by('-created_at').first()
        if not dispute:
            return format_html('<span style="color: #64748b; font-size: 12px;">No disputes raised for this order.</span>')
        
        if dispute.status in ['RESOLVED_REFUND', 'RESOLVED_RELEASE', 'RESOLVED_PARTIAL', 'CANCELLED']:
            return format_html(
                '<div style="padding: 12px 16px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; color: #065f46; margin-bottom: 10px;">'
                '<strong>✅ Dispute #{} Resolved ({})</strong><br>Resolution Notes: {}'
                '</div>',
                dispute.id, dispute.get_status_display(), dispute.resolution_notes or 'No notes provided.'
            )

        return format_html(
            '<div style="padding: 16px; background: #fff1f2; border: 2px solid #f43f5e; border-radius: 8px; margin-bottom: 15px;">'
            '<h4 style="margin: 0 0 6px 0; color: #be123c; font-size: 15px;">⚠️ Active Dispute #{} - {}</h4>'
            '<p style="margin: 0 0 10px 0; font-size: 12px; color: #881337;"><strong>Reason:</strong> {} | <strong>Raised by:</strong> {}<br><strong>Details:</strong> {}</p>'
            '<p style="margin: 0 0 12px 0; font-size: 12px; color: #475569;">Select an arbitration action to resolve this dispute and execute escrow wallet transfers immediately:</p>'
            '<div style="display: flex; gap: 10px; flex-wrap: wrap;">'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.style.opacity=\'0.6\'; this.innerHTML=\'⏳ Processing Refund...\';" style="background: #7c3aed; color: #fff !important; border: none; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-block;" href="/admin/orders/dispute/{}/resolve-action/full-refund/">⚖️ Grant Full Refund (100%)</a>'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.style.opacity=\'0.6\'; this.innerHTML=\'⏳ Processing Release...\';" style="background: #059669; color: #fff !important; border: none; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-block;" href="/admin/orders/dispute/{}/resolve-action/release-farmer/">🌾 Release Escrow to Farmer</a>'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.style.opacity=\'0.6\'; this.innerHTML=\'⏳ Processing Split...\';" style="background: #0284c7; color: #fff !important; border: none; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-block;" href="/admin/orders/dispute/{}/resolve-action/partial-split/">✂️ Partial Split 50/50</a>'
            '</div>'
            '</div>',

            dispute.id, dispute.get_status_display(), dispute.get_reason_display(), dispute.raised_by.username, dispute.description,
            dispute.id, dispute.id, dispute.id
        )
    admin_dispute_mediation_banner.short_description = "Dispute Mediation Panel"



@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'order_link', 'raised_by', 'reason', 'status_badge', 
        'resolution', 'refund_amount', 'release_amount', 'created_at'
    )
    list_filter = ('status', 'reason', 'resolution', 'created_at')
    search_fields = ('id', 'order__id', 'raised_by__username', 'description', 'resolution_notes')
    readonly_fields = ('created_at', 'updated_at', 'admin_mediation_panel')
    fields = (
        'admin_mediation_panel',
        'order', 'raised_by', 'reason', 'description', 'evidence_url',
        'status', 'resolution', 'refund_amount', 'release_amount', 'resolution_notes', 'resolved_by',
        'created_at', 'updated_at'
    )
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

    def admin_mediation_panel(self, obj):
        if not obj or not obj.id:
            return "Save dispute first to enable mediation actions."
        if obj.status in ['RESOLVED_REFUND', 'RESOLVED_RELEASE', 'RESOLVED_PARTIAL', 'CANCELLED']:
            return format_html(
                '<div style="padding: 12px 16px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; color: #065f46;">'
                '<strong>✅ Dispute Resolved ({})</strong><br>Resolution Notes: {}'
                '</div>',
                obj.get_status_display(), obj.resolution_notes or 'No notes provided.'
            )
        
        return format_html(
            '<div style="padding: 16px; background: #f8fafc; border: 2px solid #6366f1; border-radius: 8px; margin-bottom: 10px;">'
            '<h4 style="margin: 0 0 8px 0; color: #4338ca; font-size: 15px;">⚖️ Administrative Dispute Mediation Engine</h4>'
            '<p style="margin: 0 0 14px 0; font-size: 12px; color: #475569;">Select an arbitration resolution below to execute escrow wallet transfers and update order state:</p>'
            '<div style="display: flex; gap: 10px; flex-wrap: wrap;">'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.style.opacity=\'0.6\'; this.innerHTML=\'⏳ Processing Refund...\';" style="background: #7c3aed; color: #fff !important; border: none; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-block;" href="/admin/orders/dispute/{}/resolve-action/full-refund/">⚖️ Grant Full Refund (100%)</a>'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.style.opacity=\'0.6\'; this.innerHTML=\'⏳ Processing Release...\';" style="background: #059669; color: #fff !important; border: none; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-block;" href="/admin/orders/dispute/{}/resolve-action/release-farmer/">🌾 Release Escrow to Farmer</a>'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.style.opacity=\'0.6\'; this.innerHTML=\'⏳ Processing Split...\';" style="background: #0284c7; color: #fff !important; border: none; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none; display: inline-block;" href="/admin/orders/dispute/{}/resolve-action/partial-split/">✂️ Partial Split 50/50</a>'
            '</div>'
            '</div>',

            obj.id, obj.id, obj.id
        )
    admin_mediation_panel.short_description = "Admin Mediation Actions"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/resolve-action/<str:action_type>/', self.admin_site.admin_view(self.process_resolve_action), name='dispute-resolve-action'),
        ]
        return custom_urls + urls

    def process_resolve_action(self, request, object_id, action_type):
        try:
            dispute = Dispute.objects.get(pk=object_id)
        except Dispute.DoesNotExist:
            self.message_user(request, "Dispute not found", level=messages.ERROR)
            return redirect('/admin/orders/dispute/')

        if dispute.status in ['RESOLVED_REFUND', 'RESOLVED_RELEASE', 'RESOLVED_PARTIAL', 'CANCELLED']:
            self.message_user(request, "This dispute is already resolved.", level=messages.WARNING)
            return redirect(f'/admin/orders/dispute/{object_id}/change/')

        queryset = Dispute.objects.filter(pk=object_id)
        if action_type == 'full-refund':
            self.action_resolve_full_refund(request, queryset)
        elif action_type == 'release-farmer':
            self.action_resolve_release_farmer(request, queryset)
        elif action_type == 'partial-split':
            self.action_resolve_partial_split_50_50(request, queryset)
        
        return redirect(f'/admin/orders/dispute/{object_id}/change/')

    @admin.action(description="⚖️ Mediate: Grant Full Refund to Buyer (100%%)")
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



