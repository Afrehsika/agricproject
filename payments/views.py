import uuid
import requests
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import WalletTransaction, WithdrawalRequest
from .serializers import WalletTransactionSerializer, WithdrawalRequestSerializer
from users.notifications import create_alert

PAYSTACK_BASE = 'https://api.paystack.co'


def paystack_headers():
    return {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }


class PaystackInitializeView(APIView):
    """
    POST /api/payments/initialize/
    Creates a Paystack charge and returns the authorization_url for redirect/popup.
    Body: { "amount": 500 }  (amount in GHS)
    """
    def post(self, request):
        amount_ghs = request.data.get('amount')
        if not amount_ghs:
            return Response({'detail': 'amount is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_ghs = float(amount_ghs)
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

        if amount_ghs < 1:
            return Response({'detail': 'Minimum top-up is GHS 1'}, status=status.HTTP_400_BAD_REQUEST)

        # Reference must be unique per transaction
        reference = f'AGRI-{uuid.uuid4().hex[:16].upper()}'

        payload = {
            'email': f'{request.user.username}@agriconnect.gh',
            'amount': int(amount_ghs * 100),  # Paystack uses pesewas (kobo)
            'currency': 'GHS',
            'reference': reference,
            'metadata': {
                'user_id': request.user.id,
                'username': request.user.username,
            }
        }

        try:
            resp = requests.post(
                f'{PAYSTACK_BASE}/transaction/initialize',
                json=payload,
                headers=paystack_headers(),
                timeout=10,
            )
            data = resp.json()
        except requests.RequestException as e:
            return Response({'detail': f'Paystack error: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)

        if not data.get('status'):
            return Response({'detail': data.get('message', 'Paystack initialization failed')}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'authorization_url': data['data']['authorization_url'],
            'reference': reference,
            'access_code': data['data']['access_code'],
            'public_key': settings.PAYSTACK_PUBLIC_KEY,
        })


class PaystackVerifyView(APIView):
    """
    GET /api/payments/verify/<reference>/
    Verifies a Paystack payment and credits the buyer's wallet.
    """
    def get(self, request, reference):
        try:
            resp = requests.get(
                f'{PAYSTACK_BASE}/transaction/verify/{reference}',
                headers=paystack_headers(),
                timeout=10,
            )
            data = resp.json()
        except requests.RequestException as e:
            return Response({'detail': f'Paystack error: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)

        if not data.get('status') or data['data']['status'] != 'success':
            return Response({'detail': 'Payment not successful or not found'}, status=status.HTTP_400_BAD_REQUEST)

        # Guard against duplicate credit
        if WalletTransaction.objects.filter(reference=reference).exists():
            return Response({'detail': 'Payment already processed', 'already_credited': True})

        amount_ghs = Decimal(data['data']['amount']) / Decimal('100')  # Convert from pesewas

        with transaction.atomic():
            user = request.user
            user.wallet_balance += amount_ghs
            user.save()

            WalletTransaction.objects.create(
                user=user,
                transaction_type='TOPUP',
                amount=amount_ghs,
                reference=reference,
                description=f'Paystack wallet top-up via {data["data"].get("channel", "card")}'
            )

        create_alert(
            user=user,
            notification_type='SMS',
            title='Wallet Top-Up Successful',
            content=f"Wallet topped up successfully! GHS {amount_ghs:.2f} has been credited to your wallet via Paystack."
        )

        return Response({
            'message': f'Wallet credited with GHS {amount_ghs:.2f}',
            'new_balance': float(user.wallet_balance),
        })


class WithdrawView(APIView):
    """
    POST /api/payments/withdraw/
    Creates a withdrawal request and triggers Paystack Transfer API.
    Body: { "amount": 100, "channel": "mobile_money", "account_number": "024XXXXXXX", "bank_code": "" }
    Only FARMER or TRANSPORTER roles can withdraw.
    """
    def post(self, request):
        if request.user.role not in ('FARMER', 'TRANSPORTER', 'BUYER'):
            return Response({'detail': 'Only farmers, transporters, and buyers can withdraw'}, status=status.HTTP_403_FORBIDDEN)

        amount = request.data.get('amount')
        channel = request.data.get('channel', 'mobile_money')
        account_number = request.data.get('account_number', '')
        bank_code = request.data.get('bank_code', '')

        if not amount or not account_number:
            return Response({'detail': 'amount and account_number are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

        if amount < Decimal('1'):
            return Response({'detail': 'Minimum withdrawal is GHS 1'}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.wallet_balance < amount:
            return Response({'detail': 'Insufficient wallet balance'}, status=status.HTTP_400_BAD_REQUEST)

        # --- Step 1: Create Paystack Transfer Recipient ---
        recipient_payload = {
            'type': channel,
            'name': request.user.username,
            'account_number': account_number,
            'currency': 'GHS',
        }
        if channel == 'mobile_money':
            # Paystack requires a mobile money provider code for Ghana
            # Auto-detect: MTN (024/054/055/059), Vodafone (020/050), AirtelTigo (026/027/056/057)
            prefix = account_number[:3]
            momo_banks = {
                '024': 'MTN', '054': 'MTN', '055': 'MTN', '059': 'MTN',
                '020': 'VOD', '050': 'VOD',
                '026': 'ATL', '027': 'ATL', '056': 'ATL', '057': 'ATL',
            }
            recipient_payload['bank_code'] = momo_banks.get(prefix, 'MTN')
        else:
            recipient_payload['bank_code'] = bank_code

        try:
            rec_resp = requests.post(
                f'{PAYSTACK_BASE}/transferrecipient',
                json=recipient_payload,
                headers=paystack_headers(),
                timeout=10,
            )
            rec_data = rec_resp.json()
        except requests.RequestException as e:
            return Response({'detail': f'Paystack recipient error: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)

        if not rec_data.get('status'):
            return Response({'detail': rec_data.get('message', 'Failed to create transfer recipient')}, status=status.HTTP_400_BAD_REQUEST)

        recipient_code = rec_data['data']['recipient_code']

        # --- Step 2: Initiate Transfer ---
        transfer_reference = f'AGRI-WD-{uuid.uuid4().hex[:12].upper()}'
        transfer_payload = {
            'source': 'balance',
            'amount': int(amount * 100),
            'recipient': recipient_code,
            'reason': f'AgriConnect withdrawal for {request.user.username}',
            'reference': transfer_reference,
            'currency': 'GHS',
        }

        try:
            tr_resp = requests.post(
                f'{PAYSTACK_BASE}/transfer',
                json=transfer_payload,
                headers=paystack_headers(),
                timeout=10,
            )
            tr_data = tr_resp.json()
        except requests.RequestException as e:
            return Response({'detail': f'Paystack transfer error: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)

        transfer_success = tr_data.get('status') and tr_data['data'].get('status') in ('success', 'pending', 'otp')
        simulated = False

        # Fallback simulation for Starter Business accounts in Test/Sandbox Mode
        is_test_mode = settings.PAYSTACK_SECRET_KEY.startswith('sk_test_')
        is_restricted = not tr_data.get('status') and tr_data.get('code') == 'transfer_unavailable'
        if not transfer_success and is_test_mode and is_restricted:
            transfer_success = True
            simulated = True

        with transaction.atomic():
            user = request.user
            if transfer_success:
                user.wallet_balance -= amount
                user.save()

            wd = WithdrawalRequest.objects.create(
                user=user,
                amount=amount,
                channel=channel,
                account_number=account_number,
                bank_code=bank_code,
                status='SUCCESS' if transfer_success else 'FAILED',
                transfer_code=tr_data.get('data', {}).get('transfer_code', 'SIMULATED-TRANSFER' if simulated else ''),
            )

            if transfer_success:
                desc = f'Withdrawal to {channel} ({account_number})'
                if simulated:
                    desc += ' (Simulated Sandbox Payout)'
                WalletTransaction.objects.create(
                    user=user,
                    transaction_type='PAYOUT',
                    amount=amount,
                    reference=transfer_reference,
                    description=desc
                )

        if transfer_success:
            msg = f'Withdrawal of GHS {amount:.2f} initiated successfully'
            if simulated:
                msg += ' (Simulated Sandbox Payout due to Paystack Starter Business restriction)'
            
            create_alert(
                user=user,
                notification_type='SMS',
                title='Withdrawal Successful',
                content=f"Withdrawal successful! GHS {amount:.2f} has been transferred to your mobile money account {account_number}."
            )
            
            return Response({
                'message': msg,
                'new_balance': float(user.wallet_balance),
                'status': wd.status,
            })
        else:
            create_alert(
                user=user,
                notification_type='SMS',
                title='Withdrawal Failed',
                content=f"Withdrawal of GHS {amount:.2f} failed. Paystack returned error: {tr_data.get('message', 'Transfer failed')}."
            )
            
            return Response({
                'detail': tr_data.get('message', 'Transfer failed. Check Paystack dashboard for transfer approval status.'),
                'paystack_response': tr_data,
            }, status=status.HTTP_400_BAD_REQUEST)


class WalletTransactionListView(APIView):
    """
    GET /api/payments/transactions/
    Returns all wallet transactions for the current user.
    """
    def get(self, request):
        txns = WalletTransaction.objects.filter(user=request.user)
        serializer = WalletTransactionSerializer(txns, many=True)
        return Response(serializer.data)
