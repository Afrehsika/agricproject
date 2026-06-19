from django.urls import path
from . import views

urlpatterns = [
    path('api/produce/', views.ProduceListView.as_view(), name='api-produce-list'),
    path('api/produce/create/', views.ProduceCreateView.as_view(), name='api-produce-create'),
]
