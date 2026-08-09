import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
client = Client()

user = User.objects.filter(username='Kumasi_Restaurant_Hub').first()
if not user:
    print("User Kumasi_Restaurant_Hub not found.")
    sys.exit(1)

client.force_login(user)
print("Testing /api/messages/chats/ ...")
try:
    res = client.get('/api/messages/chats/')
    print(res.status_code, res.content[:500])
except Exception as e:
    print("Error in /api/messages/chats/:", e)


