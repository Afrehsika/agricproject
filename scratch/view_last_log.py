import os
import sys
import django

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
django.setup()

from payments.models import WalletTransaction, WithdrawalRequest

print("=== LAST 5 WALLET TRANSACTIONS ===")
for tx in WalletTransaction.objects.all()[:5]:
    print(f"User: {tx.user.username} | Type: {tx.transaction_type} | Amount: {tx.amount} | Ref: {tx.reference} | Desc: {tx.description} | Time: {tx.created_at}")

print("\n=== LAST 5 WITHDRAWAL REQUESTS ===")
for wd in WithdrawalRequest.objects.all()[:5]:
    print(f"User: {wd.user.username} | Amount: {wd.amount} | Channel: {wd.channel} | Status: {wd.status} | Transfer Code: {wd.transfer_code} | Time: {wd.created_at}")
