from django.urls import path
from . import views

urlpatterns = [
    path('api/logistics/jobs/', views.TransportJobListView.as_view(), name='api-logistics-jobs'),
    path('api/logistics/jobs/<int:pk>/claim/', views.TransportJobClaimView.as_view(), name='api-logistics-claim'),
    path('api/logistics/jobs/<int:pk>/update/', views.TransportJobStatusUpdateView.as_view(), name='api-logistics-update'),
    path('api/logistics/jobs/<int:pk>/assign/', views.TransportJobAssignView.as_view(), name='api-logistics-assign'),
    path('api/logistics/jobs/<int:pk>/approve/', views.TransportJobApproveView.as_view(), name='api-logistics-approve'),
]
