from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import datetime

from produce.models import Produce
from orders.models import Order
from logistics.models import TransportJob

User = get_user_model()


class AgriConnectTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create a Farmer
        self.farmer = User.objects.create_user(
            username='Kofi_Test',
            password='password123',
            role='FARMER',
            phone_number='0241111111',
            latitude=7.5855,
            longitude=-1.9350
        )
        
        # Create a Buyer
        self.buyer = User.objects.create_user(
            username='Ama_Test',
            password='password123',
            role='BUYER',
            phone_number='0242222222',
            latitude=7.5820,
            longitude=-1.9380
        )

        # Create a Transporter
        self.transporter = User.objects.create_user(
            username='Trans_Test',
            password='password123',
            role='TRANSPORTER',
            phone_number='0243333333',
            latitude=7.5890,
            longitude=-1.9280
        )

    def test_user_authentication(self):
        """Test login endpoint"""
        response = self.client.post(reverse('api-login'), {
            'username': 'Kofi_Test',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'Kofi_Test')
        self.assertEqual(response.data['role'], 'FARMER')

    def test_produce_creation_and_decay_prediction(self):
        """Test that produce lists calculate rot date and freshness automatically"""
        self.client.force_authenticate(user=self.farmer)
        
        harvest_date = datetime.date.today() - datetime.timedelta(days=2) # 2 days ago
        response = self.client.post(reverse('api-produce-create'), {
            'name': 'Tomatoes',
            'variety': 'Power Rano',
            'quantity_available': 20,
            'unit': 'Crates',
            'price_per_unit': '150.00',
            'harvest_date': harvestDateStr := harvest_date.isoformat(),
            'description': 'Test tomatoes description'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['variety'], 'Power Rano')
        
        # Tomatoes shelf life is 7 days. Harvested 2 days ago -> freshness should be:
        # (1 - 2/7) * 100 = 71.4% -> 71%
        self.assertEqual(response.data['freshness_score'], 71)
        
        # Rot date should be harvest_date + 7 days
        expected_rot = harvest_date + datetime.timedelta(days=7)
        self.assertEqual(response.data['predicted_rot_date'], expected_rot.isoformat())

    def test_end_to_end_escrow_and_logistics_flow(self):
        """Test order creation, escrow hold, transporter match, and delivery release"""
        # 1. Farmer uploads tomatoes
        harvest_date = datetime.date.today()
        produce = Produce.objects.create(
            farmer=self.farmer,
            name='Tomatoes',
            variety='Power Rano',
            quantity_available=10,
            unit='Crates',
            price_per_unit=120.00,
            harvest_date=harvest_date,
            posting_date=harvest_date
        )
        
        # 2. Buyer places order
        self.client.force_authenticate(user=self.buyer)
        order_response = self.client.post(reverse('api-order-create'), {
            'produce': produce.id,
            'quantity': 5,
            'delivery_type': 'PLATFORM_DELIVERY'
        })
        
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)
        order_id = order_response.data['id']
        self.assertEqual(order_response.data['payment_status'], 'UNPAID')
        self.assertEqual(order_response.data['status'], 'PENDING')
        
        # 3. Buyer pays via Mobile Money
        pay_response = self.client.post(reverse('api-order-pay', kwargs={'pk': order_id}))
        self.assertEqual(pay_response.status_code, status.HTTP_200_OK)
        self.assertEqual(pay_response.data['payment_status'], 'HELD_IN_ESCROW')
        self.assertEqual(pay_response.data['status'], 'PAID')
        
        # 4. Transporter views available jobs and claims it
        self.client.force_authenticate(user=self.transporter)
        job = TransportJob.objects.get(order_id=order_id)
        self.assertEqual(job.status, 'PENDING_MATCH')
        
        claim_response = self.client.post(reverse('api-logistics-claim', kwargs={'pk': job.id}))
        self.assertEqual(claim_response.status_code, status.HTTP_200_OK)
        self.assertEqual(claim_response.data['status'], 'MATCHED')
        
        # Transporter marks as Picked Up
        pick_response = self.client.post(reverse('api-logistics-update', kwargs={'pk': job.id}), {
            'status': 'PICKED_UP'
        })
        self.assertEqual(pick_response.status_code, status.HTTP_200_OK)
        self.assertEqual(pick_response.data['status'], 'PICKED_UP')
        
        # Transporter marks as Delivered
        deliver_response = self.client.post(reverse('api-logistics-update', kwargs={'pk': job.id}), {
            'status': 'DELIVERED'
        })
        self.assertEqual(deliver_response.status_code, status.HTTP_200_OK)
        self.assertEqual(deliver_response.data['status'], 'DELIVERED')
        
        # 5. Buyer verifies delivery and confirms release
        self.client.force_authenticate(user=self.buyer)
        confirm_response = self.client.post(reverse('api-order-confirm-delivery', kwargs={'pk': order_id}))
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm_response.data['payment_status'], 'RELEASED')
        self.assertEqual(confirm_response.data['status'], 'DELIVERED')
        
        # Verify farmer's wallet got credited: 5 crates * 120.00 = 600.00 GHS
        self.farmer.refresh_from_db()
        self.assertEqual(float(self.farmer.wallet_balance), 600.00)

    def test_crop_disease_scanner_simulated(self):
        """Test crop disease scanner simulated fallback"""
        self.client.force_authenticate(user=self.farmer)
        response = self.client.post(reverse('api-disease-scanner'), {
            'crop_name': 'Tomatoes'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'SUCCESS')
        self.assertEqual(response.data['crop_analyzed'], 'Tomatoes')
        self.assertIn('(Simulated)', response.data['diagnosis'])
