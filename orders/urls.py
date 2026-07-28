from django.urls import path
from . import views

urlpatterns = [
    path('api/orders/create/', views.OrderCreateView.as_view(), name='api-order-create'),
    path('api/orders/<int:pk>/pay/', views.OrderPayView.as_view(), name='api-order-pay'),
    path('api/orders/<int:pk>/confirm-delivery/', views.OrderConfirmDeliveryView.as_view(), name='api-order-confirm-delivery'),
    path('api/orders/<int:pk>/reject/', views.OrderRejectView.as_view(), name='api-order-reject'),
    path('api/orders/<int:pk>/dispute/', views.OrderDisputeView.as_view(), name='api-order-dispute'),
    # Dispute endpoints
    path('api/disputes/', views.DisputeListView.as_view(), name='api-dispute-list'),
    path('api/disputes/<int:pk>/', views.DisputeDetailView.as_view(), name='api-dispute-detail'),
    path('api/disputes/<int:pk>/resolve/', views.DisputeResolveView.as_view(), name='api-dispute-resolve'),
    # Cart endpoints
    path('api/cart/', views.CartView.as_view(), name='api-cart'),
    path('api/cart/<int:pk>/', views.CartItemDeleteView.as_view(), name='api-cart-item-delete'),
    path('api/cart/checkout/', views.CartCheckoutView.as_view(), name='api-cart-checkout'),
    path('api/orders/dispatch/', views.OrderDispatchView.as_view(), name='api-order-dispatch'),
]

