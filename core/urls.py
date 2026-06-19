from django.urls import path
from . import views

urlpatterns = [
    # Frontend Page
    path('', views.index_view, name='index'),
    
    # Seed Utility
    path('api/seed/', views.SeedDataView.as_view(), name='api-seed'),
]
