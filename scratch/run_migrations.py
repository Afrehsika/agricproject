import os
import django
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
django.setup()

try:
    print("Running makemigrations...")
    call_command('makemigrations')
    print("Running migrate...")
    call_command('migrate')
    print("Done!")
except Exception as e:
    import traceback
    traceback.print_exc()
