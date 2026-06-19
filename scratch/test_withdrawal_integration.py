import os
import requests
from dotenv import load_dotenv

# Load env variables from root
load_dotenv(dotenv_path='.env')

secret_key = os.getenv('PAYSTACK_SECRET_KEY')
print(f"Loaded Paystack Secret Key: {'Yes' if secret_key else 'No'}")
if secret_key:
    print(f"Prefix/Suffix: {secret_key[:8]}...{secret_key[-8:]}")

headers = {
    'Authorization': f'Bearer {secret_key}',
    'Content-Type': 'application/json',
}

# 1. Test creating a mobile money transfer recipient (Ghana)
recipient_payload = {
    'type': 'mobile_money',
    'name': 'Test AgriConnect User',
    'account_number': '0244123456',
    'bank_code': 'MTN',
    'currency': 'GHS'
}

print("\n--- Sending request to Paystack /transferrecipient ---")
try:
    resp = requests.post(
        'https://api.paystack.co/transferrecipient',
        json=recipient_payload,
        headers=headers,
        timeout=10
    )
    status_code = resp.status_code
    response_json = resp.json()
    
    print(f"Status Code: {status_code}")
    print(f"Response: {response_json}")
    
    if response_json.get('status'):
        print("\nSUCCESS: Connection established and transfer recipient created successfully!")
        print(f"Recipient Code: {response_json['data']['recipient_code']}")
    else:
        print("\nFAILED: Paystack rejected the recipient creation:")
        print(response_json.get('message'))
except Exception as e:
    print(f"\nERROR: Could not connect to Paystack: {e}")
