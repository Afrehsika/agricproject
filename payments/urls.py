from django.urls import path
from . import views

urlpatterns = [
    path('api/payments/initialize/', views.PaystackInitializeView.as_view(), name='api-payments-initialize'),
    path('api/payments/verify/<str:reference>/', views.PaystackVerifyView.as_view(), name='api-payments-verify'),
    path('api/payments/withdraw/', views.WithdrawView.as_view(), name='api-payments-withdraw'),
    path('api/payments/transactions/', views.WalletTransactionListView.as_view(), name='api-payments-transactions'),
]
