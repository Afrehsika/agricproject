from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Produce, StorageFacility


@admin.register(StorageFacility)
class StorageFacilityAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'farmer', 'facility_type', 'capacity', 
        'location', 'status_badge', 'badge_badge', 'created_at'
    )
    list_filter = ('status', 'badge', 'facility_type', 'created_at')
    search_fields = ('id', 'name', 'farmer__username', 'location', 'admin_notes')
    readonly_fields = ('created_at', 'updated_at', 'inspected_at', 'inspected_by', 'admin_inspection_panel')
    fields = (
        'admin_inspection_panel',
        'farmer', 'name', 'facility_type', 'capacity', 'location',
        'temperature_humidity', 'photo_url', 'status', 'badge',
        'admin_notes', 'inspected_by', 'inspected_at',
        'created_at', 'updated_at'
    )
    actions = ['approve_gold_badge', 'approve_silver_badge', 'approve_bronze_badge', 'reject_inspection']

    def status_badge(self, obj):
        colors = {'PENDING': '#f59e0b', 'APPROVED': '#10b981', 'REJECTED': '#ef4444'}
        color = colors.get(obj.status, '#64748b')
        return format_html('<span style="background:{}; color:#fff; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def badge_badge(self, obj):
        colors = {'GOLD_COLD_CHAIN': '#7c3aed', 'SILVER_COOL_ROOM': '#059669', 'BRONZE_VENTILATED': '#0284c7', 'NONE': '#64748b'}
        color = colors.get(obj.badge, '#64748b')
        return format_html('<span style="background:{}; color:#fff; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">{}</span>', color, obj.get_badge_display())
    badge_badge.short_description = "Inspection Badge"

    def admin_inspection_panel(self, obj):
        if not obj or not obj.id:
            return "Save storage facility record first to enable admin inspection panel."

        if obj.status == 'APPROVED':
            return format_html(
                '<div style="padding: 12px 16px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; color: #065f46;">'
                '<strong>✅ Storage Facility Approved & Verified ({})</strong><br>Inspected By: {} | Notes: {}'
                '</div>',
                obj.get_badge_display(), obj.inspected_by.username if obj.inspected_by else 'Admin', obj.admin_notes or 'Passed inspection.'
            )

        return format_html(
            '<div style="padding: 16px; background: #fefce8; border: 2px solid #eab308; border-radius: 8px; margin-bottom: 10px;">'
            '<h4 style="margin: 0 0 8px 0; color: #854d0e; font-size: 15px;">🏭 Storage Facility Quality Inspection & Certification Engine</h4>'
            '<p style="margin: 0 0 12px 0; font-size: 12px; color: #713f12;">Review facility capacity, temperature/humidity control, and assign a certified inspection badge to assure crop freshness on the marketplace:</p>'
            '<div style="display: flex; gap: 10px; flex-wrap: wrap;">'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.innerHTML=\'⏳ Inspecting...\';" style="background: #7c3aed; color: #fff !important; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none;" href="/admin/produce/storagefacility/{}/change/?inspect_action=gold">❄️ Approve Gold Cold-Chain Badge (2.5x Freshness)</a>'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.innerHTML=\'⏳ Inspecting...\';" style="background: #059669; color: #fff !important; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none;" href="/admin/produce/storagefacility/{}/change/?inspect_action=silver">🌿 Approve Silver Solar-Cool Badge (1.8x Freshness)</a>'
            '<a class="button" onclick="this.style.pointerEvents=\'none\'; this.innerHTML=\'⏳ Inspecting...\';" style="background: #0284c7; color: #fff !important; padding: 10px 16px; border-radius: 6px; font-weight: bold; text-decoration: none;" href="/admin/produce/storagefacility/{}/change/?inspect_action=bronze">📦 Approve Bronze Storage Badge (1.3x Freshness)</a>'
            '</div>'
            '</div>',
            obj.id, obj.id, obj.id
        )
    admin_inspection_panel.short_description = "Admin Quality Inspection"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        inspect_action = request.GET.get('inspect_action')
        if inspect_action and request.user.is_staff:
            facility = self.get_object(request, object_id)
            if facility:
                if inspect_action == 'gold':
                    facility.status = 'APPROVED'
                    facility.badge = 'GOLD_COLD_CHAIN'
                    facility.admin_notes = 'Passed full cold-chain refrigerated inspection.'
                elif inspect_action == 'silver':
                    facility.status = 'APPROVED'
                    facility.badge = 'SILVER_COOL_ROOM'
                    facility.admin_notes = 'Passed solar-powered evaporative cooling inspection.'
                elif inspect_action == 'bronze':
                    facility.status = 'APPROVED'
                    facility.badge = 'BRONZE_VENTILATED'
                    facility.admin_notes = 'Passed ventilated dry warehouse inspection.'
                facility.inspected_by = request.user
                facility.inspected_at = timezone.now()
                facility.save()
                for p in facility.stored_produces.all():
                    p.save()
                self.message_user(request, f"Storage Facility #{facility.id} approved with {facility.get_badge_display()}!")
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(f"/admin/produce/storagefacility/{object_id}/change/")
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.action(description="❄️ Approve Gold Cold-Chain Badge (2.5x Freshness Guarantee)")
    def approve_gold_badge(self, request, queryset):
        for f in queryset:
            f.status = 'APPROVED'
            f.badge = 'GOLD_COLD_CHAIN'
            f.admin_notes = 'Approved via admin bulk action.'
            f.inspected_by = request.user
            f.inspected_at = timezone.now()
            f.save()
            for p in f.stored_produces.all():
                p.save()
        self.message_user(request, f"{queryset.count()} facilities approved with Gold Cold-Chain status!")

    @admin.action(description="🌿 Approve Silver Solar-Cool Badge (1.8x Freshness)")
    def approve_silver_badge(self, request, queryset):
        for f in queryset:
            f.status = 'APPROVED'
            f.badge = 'SILVER_COOL_ROOM'
            f.admin_notes = 'Approved via admin bulk action.'
            f.inspected_by = request.user
            f.inspected_at = timezone.now()
            f.save()
            for p in f.stored_produces.all():
                p.save()
        self.message_user(request, f"{queryset.count()} facilities approved with Silver Solar-Cool status!")

    @admin.action(description="📦 Approve Bronze Inspected Storage Badge (1.3x Freshness)")
    def approve_bronze_badge(self, request, queryset):
        for f in queryset:
            f.status = 'APPROVED'
            f.badge = 'BRONZE_VENTILATED'
            f.admin_notes = 'Approved via admin bulk action.'
            f.inspected_by = request.user
            f.inspected_at = timezone.now()
            f.save()
            for p in f.stored_produces.all():
                p.save()
        self.message_user(request, f"{queryset.count()} facilities approved with Bronze Storage status!")

    @admin.action(description="❌ Reject Facility Inspection")
    def reject_inspection(self, request, queryset):
        queryset.update(status='REJECTED', badge='NONE', inspected_by=request.user, inspected_at=timezone.now())
        self.message_user(request, f"{queryset.count()} facility inspections rejected.")


@admin.register(Produce)
class ProduceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'variety', 'farmer', 'quantity_available', 'unit', 'price_per_unit', 'freshness_score', 'storage_facility', 'status')
    list_filter = ('name', 'status', 'harvest_date')
    search_fields = ('id', 'name', 'variety', 'farmer__username', 'description')

