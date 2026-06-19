from rest_framework import serializers
from .models import WalletTransaction, WithdrawalRequest


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ('id', 'transaction_type', 'amount', 'reference', 'description', 'created_at')
        read_only_fields = fields


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawalRequest
        fields = ('id', 'amount', 'channel', 'account_number', 'bank_code', 'status', 'created_at')
        read_only_fields = ('id', 'status', 'created_at')
