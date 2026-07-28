import os
import django
from django.core.management import call_command

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
    django.setup()
    from orders.views import _ensure_dispute_table_schema
    print("Running schema checks and database migrations...")
    _ensure_dispute_table_schema()
    call_command('migrate')
    print("Database migrations applied successfully!")

