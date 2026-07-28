from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('produce', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StorageFacility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('facility_type', models.CharField(choices=[('SOLAR_COLD_ROOM', 'Solar-Powered Cold Room (4°C - 12°C)'), ('EVAPORATIVE_COOLER', 'Evaporative Cooling Chamber (14°C - 18°C)'), ('REFRIGERATED_WAREHOUSE', 'Refrigerated Cold Chain Warehouse'), ('VENTILATED_BARN', 'Inspected Ventilated Dry Storage')], default='SOLAR_COLD_ROOM', max_length=50)),
                ('capacity', models.CharField(default='500 Crates / 10 Tonnes', max_length=100)),
                ('location', models.CharField(default='Techiman Central Storage Hub', max_length=200)),
                ('temperature_humidity', models.CharField(blank=True, default='8°C - 12°C / 85% RH', max_length=100)),
                ('photo_url', models.CharField(blank=True, default='', max_length=255)),
                ('status', models.CharField(choices=[('PENDING', 'Pending Admin Inspection'), ('APPROVED', 'Approved & Verified'), ('REJECTED', 'Inspection Rejected')], default='PENDING', max_length=30)),
                ('badge', models.CharField(choices=[('GOLD_COLD_CHAIN', '❄️ Gold Cold-Chain Verified'), ('SILVER_COOL_ROOM', '🌿 Silver Solar-Cool Certified'), ('BRONZE_VENTILATED', '📦 Bronze Inspected Storage'), ('NONE', 'No Badge')], default='NONE', max_length=30)),
                ('admin_notes', models.TextField(blank=True, default='')),
                ('inspected_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('farmer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='storage_facilities', to=settings.AUTH_USER_MODEL)),
                ('inspected_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inspected_facilities', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='produce',
            name='storage_facility',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stored_produces', to='produce.storagefacility'),
        ),
    ]
