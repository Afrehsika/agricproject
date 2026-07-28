from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import datetime

from produce.models import Produce
from orders.models import Order, Dispute
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
            longitude=-1.9380,
            wallet_balance=1000.00
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

    def test_buyer_rejection_and_dispute_creation(self):
        """Test buyer rejecting shipment due to spoiled produce, creating dispute and locking escrow"""
        harvest_date = datetime.date.today()
        produce = Produce.objects.create(
            farmer=self.farmer,
            name='Tomatoes',
            variety='Power Rano',
            quantity_available=10,
            unit='Crates',
            price_per_unit=100.00,
            harvest_date=harvest_date,
            posting_date=harvest_date
        )

        self.client.force_authenticate(user=self.buyer)
        order_response = self.client.post(reverse('api-order-create'), {
            'produce': produce.id,
            'quantity': 5,
            'delivery_type': 'PLATFORM_DELIVERY'
        })
        order_id = order_response.data['id']
        self.client.post(reverse('api-order-pay', kwargs={'pk': order_id}))

        # Buyer rejects shipment upon delivery
        reject_response = self.client.post(reverse('api-order-reject', kwargs={'pk': order_id}), {
            'reason': 'SPOILED_ROTTEN',
            'description': 'Tomatoes arrived crushed and spoiled during transport',
            'evidence_url': 'https://example.com/spoiled.jpg'
        })

        self.assertEqual(reject_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reject_response.data['order']['status'], 'REJECTED')
        self.assertEqual(reject_response.data['order']['payment_status'], 'DISPUTED')
        self.assertEqual(reject_response.data['dispute']['reason'], 'SPOILED_ROTTEN')
        self.assertEqual(Dispute.objects.filter(order_id=order_id).count(), 1)

    def test_dispute_resolution_full_refund(self):
        """Test resolving a dispute with 100% refund back to buyer and restocking produce"""
        harvest_date = datetime.date.today()
        produce = Produce.objects.create(
            farmer=self.farmer,
            name='Habanero Peppers',
            variety='Scotch Bonnet',
            quantity_available=5,
            unit='Bags',
            price_per_unit=200.00,
            harvest_date=harvest_date,
            posting_date=harvest_date
        )

        self.client.force_authenticate(user=self.buyer)
        order_resp = self.client.post(reverse('api-order-create'), {
            'produce': produce.id,
            'quantity': 2,
            'delivery_type': 'PLATFORM_DELIVERY'
        })
        order_id = order_resp.data['id']
        self.client.post(reverse('api-order-pay', kwargs={'pk': order_id}))

        initial_buyer_balance = float(self.buyer.refresh_from_db() or self.buyer.wallet_balance)

        # Buyer rejects
        reject_resp = self.client.post(reverse('api-order-reject', kwargs={'pk': order_id}), {
            'reason': 'WRONG_VARIETY_QUALITY',
            'description': 'Received green peppers instead of Scotch Bonnet'
        })
        dispute_id = reject_resp.data['dispute']['id']

        # Admin resolves with full refund to buyer + restock
        resolve_resp = self.client.post(reverse('api-dispute-resolve', kwargs={'pk': dispute_id}), {
            'resolution': 'REFUND_BUYER',
            'notes': 'Verified wrong variety sent. Full refund granted to buyer.',
            'restock_inventory': True
        })

        self.assertEqual(resolve_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resolve_resp.data['order']['payment_status'], 'REFUNDED')
        
        # Verify buyer received refund
        self.buyer.refresh_from_db()
        self.assertGreater(float(self.buyer.wallet_balance), initial_buyer_balance)

        # Verify produce inventory was restocked (5 - 2 + 2 = 5)
        produce.refresh_from_db()
        self.assertEqual(produce.quantity_available, 5)

    def test_dispute_resolution_partial_split(self):
        """Test resolving dispute with partial split refund between buyer and farmer"""
        harvest_date = datetime.date.today()
        produce = Produce.objects.create(
            farmer=self.farmer,
            name='Garden Eggs',
            variety='Local White',
            quantity_available=10,
            unit='Baskets',
            price_per_unit=100.00,
            harvest_date=harvest_date,
            posting_date=harvest_date
        )

        self.client.force_authenticate(user=self.buyer)
        order_resp = self.client.post(reverse('api-order-create'), {
            'produce': produce.id,
            'quantity': 2,
            'delivery_type': 'PLATFORM_DELIVERY'
        })
        order_id = order_resp.data['id']
        self.client.post(reverse('api-order-pay', kwargs={'pk': order_id}))

        # Reject
        reject_resp = self.client.post(reverse('api-order-reject', kwargs={'pk': order_id}), {
            'reason': 'QUANTITY_SHORTAGE',
            'description': '1 basket was damaged, 1 basket was good'
        })
        dispute_id = reject_resp.data['dispute']['id']

        # Admin resolves with 50/50 split (100 refund to buyer, 100 release to farmer)
        resolve_resp = self.client.post(reverse('api-dispute-resolve', kwargs={'pk': dispute_id}), {
            'resolution': 'PARTIAL_SPLIT',
            'refund_amount': '100.00',
            'release_amount': '100.00',
            'notes': '50% refund due to 1 damaged basket.'
        })

        self.assertEqual(resolve_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resolve_resp.data['order']['payment_status'], 'PARTIALLY_REFUNDED')

        # Farmer should have received 100.00
        self.farmer.refresh_from_db()
        self.assertEqual(float(self.farmer.wallet_balance), 100.00)

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

