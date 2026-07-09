@echo off
echo Installing required packages...
call venv\Scripts\pip install -r requirements.txt

echo Temporarily unsetting DATABASE_URL to dump data from sqlite...
set DATABASE_URL=
call venv\Scripts\python manage.py dumpdata --exclude auth.permission --exclude contenttypes -o datadump.json

echo Setting DATABASE_URL to Neon Postgres...
set DATABASE_URL=postgresql://neondb_owner:npg_oJA2HpmDlh5n@ep-cool-bird-aiykg0pd-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require^&channel_binding=require

echo Running migrations on Neon Postgres...
call venv\Scripts\python manage.py migrate

echo Loading data into Neon Postgres...
call venv\Scripts\python manage.py loaddata datadump.json

echo Data transfer complete!
