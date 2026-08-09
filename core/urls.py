from django.urls import path
from . import views
from . import ussd

urlpatterns = [
    # Frontend Pages (MPA)
    path('', views.index_view, name='index'), # Landing page
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('marketplace/', views.marketplace_view, name='marketplace'),
    path('farmer-listings/', views.farmer_listings_view, name='farmer-listings'),
    path('orders/', views.orders_view, name='orders'),
    path('logistics/', views.logistics_view, name='logistics'),
    path('disease-scanner/', views.disease_scanner_view, name='disease-scanner'),
    path('network/', views.network_view, name='network'),
    path('messages/', views.messages_view, name='messages'),
    path('analytics/', views.analytics_view, name='analytics'),
    
    path('simulator/', views.simulator_view, name='simulator'),
    
    # Seed Utility
    path('api/seed/', views.SeedDataView.as_view(), name='api-seed'),
    
    # USSD Webhook
    path('api/ussd/', ussd.USSDWebhookView.as_view(), name='api-ussd'),
]
