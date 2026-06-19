from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'role', 'phone_number', 'wallet_balance', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('AgriConnect Fields', {'fields': ('role', 'phone_number', 'region', 'district', 'latitude', 'longitude', 'wallet_balance')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('AgriConnect Fields', {'fields': ('role', 'phone_number', 'region', 'district', 'latitude', 'longitude', 'wallet_balance')}),
    )


admin.site.register(CustomUser, CustomUserAdmin)
