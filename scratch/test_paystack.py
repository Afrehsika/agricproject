import os
import requests
from dotenv import load_dotenv

load_dotenv()

PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
print("Secret key exists:", bool(PAYSTACK_SECRET_KEY))
print("Secret key prefix/suffix:", PAYSTACK_SECRET_KEY[:8] + "..." + PAYSTACK_SECRET_KEY[-8:] if PAYSTACK_SECRET_KEY else "None")

headers = {
    'Authorization': f'Bearer {PAYSTACK_SECRET_KEY}',
    'Content-Type': 'application/json',
}

payload = {
    'email': 'test@agriconnect.gh',
    'amount': 5000,
    'currency': 'GHS',
    'reference': 'AGRI-TEST-REF-1',
}

try:
    resp = requests.post(
        'https://api.paystack.co/transaction/initialize',
        json=payload,
        headers=headers,
        timeout=10
    )
    print("Status Code:", resp.status_code)
    print("Response JSON:", resp.json())
except Exception as e:
    print("Request failed:", e)
