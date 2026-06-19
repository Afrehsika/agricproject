@echo off
"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe" manage.py makemigrations > scratch/migration_out.txt 2>&1
"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe" manage.py migrate >> scratch/migration_out.txt 2>&1
echo Done! >> scratch/migration_out.txt
