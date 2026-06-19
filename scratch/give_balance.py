import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(username='Kumasi_Restaurant_Hub')
u.wallet_balance = 1000.00
u.save()
print('SUCCESS: Balance set to:', u.wallet_balance)
