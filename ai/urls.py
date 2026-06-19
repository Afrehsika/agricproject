from django.urls import path
from . import views

urlpatterns = [
    path('api/disease-scanner/', views.CropDiseaseScannerView.as_view(), name='api-disease-scanner'),
    path('api/agribot/', views.AgriBotView.as_view(), name='api-agribot'),
]
