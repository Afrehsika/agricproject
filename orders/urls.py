from django.urls import path
from . import views

urlpatterns = [
    path('api/orders/create/', views.OrderCreateView.as_view(), name='api-order-create'),
    path('api/orders/<int:pk>/pay/', views.OrderPayView.as_view(), name='api-order-pay'),
    path('api/orders/<int:pk>/confirm-delivery/', views.OrderConfirmDeliveryView.as_view(), name='api-order-confirm-delivery'),
    # Cart endpoints
    path('api/cart/', views.CartView.as_view(), name='api-cart'),
    path('api/cart/<int:pk>/', views.CartItemDeleteView.as_view(), name='api-cart-item-delete'),
    path('api/cart/checkout/', views.CartCheckoutView.as_view(), name='api-cart-checkout'),
    path('api/orders/dispatch/', views.OrderDispatchView.as_view(), name='api-order-dispatch'),
]
