from django.db import models
from django.conf import settings


class WalletTransaction(models.Model):
    """Logs every wallet debit/credit for traceability."""
    TYPE_CHOICES = (
        ('TOPUP', 'Wallet Top-Up'),
        ('PAYMENT', 'Order Payment'),
        ('PAYOUT', 'Payout to Farmer/Driver'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=200, unique=True)
    description = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.transaction_type} | GHS {self.amount}"


class WithdrawalRequest(models.Model):
    """Tracks payout requests from farmers/transporters."""
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )

    CHANNEL_CHOICES = (
        ('mobile_money', 'Mobile Money'),
        ('bank_account', 'Bank Account'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    account_number = models.CharField(max_length=50)  # phone or bank acct
    bank_code = models.CharField(max_length=20, blank=True)  # for bank transfers
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transfer_code = models.CharField(max_length=100, blank=True)  # Paystack transfer code
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} withdrawal GHS {self.amount} via {self.channel} ({self.status})"
