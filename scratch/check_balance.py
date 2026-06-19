import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
django.setup()

from django.contrib.auth import get_user_model
from payments.models import WalletTransaction, WithdrawalRequest

User = get_user_model()

print("=== USERS & WALLET BALANCES ===")
for u in User.objects.all():
    print(f"Username: {u.username} | Role: {u.role} | Balance: {u.wallet_balance}")

print("\n=== WALLET TRANSACTIONS ===")
for tx in WalletTransaction.objects.all():
    print(f"User: {tx.user.username} | Type: {tx.transaction_type} | Amount: {tx.amount} | Ref: {tx.reference} | Desc: {tx.description}")

print("\n=== WITHDRAWAL REQUESTS ===")
for wd in WithdrawalRequest.objects.all():
    print(f"User: {wd.user.username} | Amount: {wd.amount} | Channel: {wd.channel} | Status: {wd.status} | Ref: {wd.transfer_code}")
