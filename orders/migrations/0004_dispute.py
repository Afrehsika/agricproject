# Generated for Disputes & Buyer Rejection

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_cartitem'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='payment_status',
            field=models.CharField(choices=[('UNPAID', 'Unpaid'), ('HELD_IN_ESCROW', 'Held in Escrow'), ('RELEASED', 'Released to Farmer'), ('REFUNDED', 'Refunded to Buyer'), ('DISPUTED', 'Disputed'), ('PARTIALLY_REFUNDED', 'Partially Refunded')], default='UNPAID', max_length=20),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('PAID', 'Paid (Held in Escrow)'), ('SHIPPED', 'Shipped'), ('DELIVERED', 'Delivered'), ('REJECTED', 'Rejected by Buyer'), ('DISPUTED', 'In Dispute'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20),
        ),
        migrations.CreateModel(
            name='Dispute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('SPOILED_ROTTEN', 'Spoiled or Rotten Produce'), ('WRONG_VARIETY_QUALITY', 'Wrong Variety or Substandard Quality'), ('QUANTITY_SHORTAGE', 'Quantity Shortage / Missing Items'), ('DAMAGED_IN_TRANSIT', 'Cargo Damaged in Transit'), ('OTHER', 'Other Reason')], default='SPOILED_ROTTEN', max_length=30)),
                ('description', models.TextField()),
                ('evidence_url', models.CharField(blank=True, max_length=500)),
                ('status', models.CharField(choices=[('OPEN', 'Open Dispute'), ('UNDER_REVIEW', 'Under Review'), ('RESOLVED_REFUND', 'Resolved (Full Refund to Buyer)'), ('RESOLVED_RELEASE', 'Resolved (Escrow Released to Farmer)'), ('RESOLVED_PARTIAL', 'Resolved (Partial Refund / Split)'), ('CANCELLED', 'Dispute Cancelled')], default='OPEN', max_length=25)),
                ('resolution', models.CharField(blank=True, choices=[('REFUND_BUYER', 'Full Refund to Buyer'), ('RELEASE_FARMER', 'Full Escrow Release to Farmer'), ('PARTIAL_SPLIT', 'Partial Split Refund'), ('DISMISS', 'Disputed Claim Dismissed')], max_length=25)),
                ('refund_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('release_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('resolution_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disputes', to='orders.order')),
                ('raised_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disputes_raised', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_disputes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
