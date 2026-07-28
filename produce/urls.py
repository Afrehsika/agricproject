from django.urls import path
from . import views

urlpatterns = [
    path('api/produce/', views.ProduceListView.as_view(), name='api-produce-list'),
    path('api/produce/create/', views.ProduceCreateView.as_view(), name='api-produce-create'),
    path('api/storage/facilities/', views.StorageFacilityListCreateView.as_view(), name='api-storage-facility-list-create'),
    path('api/storage/facilities/<int:pk>/inspect/', views.StorageFacilityInspectView.as_view(), name='api-storage-facility-inspect'),
]

