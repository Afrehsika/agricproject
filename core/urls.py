from django.urls import path
from . import views
from . import ussd

urlpatterns = [
    # Frontend Page
    path('', views.index_view, name='index'),
    path('simulator/', views.simulator_view, name='simulator'),
    
    # Seed Utility
    path('api/seed/', views.SeedDataView.as_view(), name='api-seed'),
    
    # USSD Webhook
    path('api/ussd/', ussd.USSDWebhookView.as_view(), name='api-ussd'),
]
