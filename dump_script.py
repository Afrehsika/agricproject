import os
import django
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
django.setup()

with open('datadump.json', 'w', encoding='utf-8') as f:
    call_command('dumpdata', exclude=['contenttypes', 'auth.Permission'], stdout=f)
