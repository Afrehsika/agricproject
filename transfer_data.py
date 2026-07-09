import os
import django

# Setup environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
django.setup()

from django.conf import settings
from pathlib import Path

# Override DATABASES back to sqlite3 for dumping
BASE_DIR = Path(__file__).resolve().parent
settings.DATABASES['default'] = {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': BASE_DIR / 'db.sqlite3',
}

import dj_database_url
from django.core.management import call_command
from django.conf import settings
from django.db import connections

def run_migration():
    print("Dumping data from sqlite3...")
    with open('datadump.json', 'w', encoding='utf-8') as f:
        call_command('dumpdata', exclude=['contenttypes', 'auth.permission'], stdout=f)

    print("Data dumped. Applying migrations to Neon Postgres...")
    # Now we switch the database to Postgres
    neon_db_url = "postgresql://neondb_owner:npg_oJA2HpmDlh5n@ep-cool-bird-aiykg0pd-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    settings.DATABASES['default'] = dj_database_url.config(default=neon_db_url, conn_max_age=600)
    
    # Close old connections
    connections.close_all()

    print("Running migrations on Neon DB...")
    call_command('migrate')

    print("Loading data into Neon DB...")
    call_command('loaddata', 'datadump.json')
    print("Data transfer complete!")

if __name__ == '__main__':
    run_migration()
