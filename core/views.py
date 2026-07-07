import datetime
from django.shortcuts import render
from django.db import transaction
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from produce.models import Produce
from orders.models import Order
from logistics.models import TransportJob

User = get_user_model()


class SeedDataView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        with transaction.atomic():
            # Clear existing data to avoid overlap issues
            Order.objects.all().delete()
            Produce.objects.all().delete()
            
            # Clear connection and messaging data
            from users.models import Connection, Message
            Connection.objects.all().delete()
            Message.objects.all().delete()
            
            User.objects.filter(is_superuser=False).delete()
            
            # 1. Create Farmers (Techiman region coordinates)
            # Coordinates are focused around Techiman town centre
            farmer_data = [
                {'username': 'Kofi_Mensah', 'phone': '0241112222', 'lat': 7.5855, 'lng': -1.9350, 'dist': 'Techiman Municipal'},
                {'username': 'Ama_Serwaa', 'phone': '0553334444', 'lat': 7.5790, 'lng': -1.9480, 'dist': 'Techiman Municipal'},
                {'username': 'Kwaku_Duah', 'phone': '0275556666', 'lat': 7.6320, 'lng': -1.9310, 'dist': 'Tuobodom'},
                {'username': 'Yaa_Asantewaa', 'phone': '0249999999', 'lat': 7.5990, 'lng': -1.9120, 'dist': 'Nkoranza South'}
            ]
            
            farmers = []
            for idx, fd in enumerate(farmer_data):
                f = User.objects.create_user(
                    username=fd['username'],
                    email=f"{fd['username'].lower()}@agri.com",
                    password='password123',
                    role='FARMER',
                    phone_number=fd['phone'],
                    region='Bono East',
                    district=fd['dist'],
                    latitude=fd['lat'],
                    longitude=fd['lng']
                )
                farmers.append(f)
                
            # 2. Create Buyers
            buyer_data = [
                {'username': 'Kumasi_Restaurant_Hub', 'phone': '0247778888', 'lat': 6.6960, 'lng': -1.6240, 'dist': 'Kumasi Metro'}, # Kumasi
                {'username': 'Accra_Salad_Bar', 'phone': '0501110000', 'lat': 5.6037, 'lng': -0.1870, 'dist': 'Accra Metro'}, # Accra
                {'username': 'Techiman_Retailer_Ama', 'phone': '0245678901', 'lat': 7.5820, 'lng': -1.9380, 'dist': 'Techiman Municipal'} # Local Techiman Buyer
            ]
            buyers = []
            for bd in buyer_data:
                b = User.objects.create_user(
                    username=bd['username'],
                    email=f"{bd['username'].lower()}@agri.com",
                    password='password123',
                    role='BUYER',
                    phone_number=bd['phone'],
                    region='Bono East' if 'Techiman' in bd['username'] else ('Ashanti' if 'Kumasi' in bd['username'] else 'Greater Accra'),
                    district=bd['dist'],
                    latitude=bd['lat'],
                    longitude=bd['lng'],
                    wallet_balance=5000.00
                )
                buyers.append(b)

            # 3. Create Transporters
            transporter_data = [
                {'username': 'KIA_Bongo_Kojo', 'phone': '0248889999', 'lat': 7.5890, 'lng': -1.9280, 'dist': 'Techiman Municipal'},
                {'username': 'Aboboyaa_Tricycle_Yaw', 'phone': '0558883333', 'lat': 7.5750, 'lng': -1.9420, 'dist': 'Techiman Municipal'}
            ]
            transporters = []
            for td in transporter_data:
                t = User.objects.create_user(
                    username=td['username'],
                    email=f"{td['username'].lower()}@agri.com",
                    password='password123',
                    role='TRANSPORTER',
                    phone_number=td['phone'],
                    region='Bono East',
                    district=td['dist'],
                    latitude=td['lat'],
                    longitude=td['lng']
                )
                transporters.append(t)
                
            # 4. Create Produce Listings
            today = datetime.date.today()
            produce_data = [
                # Tomatoes (Power Rano variety) - harvested 4 days ago -> rot in 3 days. Freshness: 42% -> URGENT/FLASH SALE
                {
                    'farmer': farmers[0], 'name': 'Tomatoes', 'variety': 'Power Rano',
                    'qty': 30, 'unit': 'Crates', 'price': 150.00,
                    'harvest_offset': 4, 'desc': 'Fully ripe, rich red color. Needs quick buyers!',
                    'img': 'https://images.unsplash.com/photo-1595855759920-86582396756a?auto=format&fit=crop&w=300&q=80'
                },
                # Tomatoes (Local variety) - harvested today -> rot in 7 days. Freshness: 100%
                {
                    'farmer': farmers[1], 'name': 'Tomatoes', 'variety': 'Kumasi Local',
                    'qty': 15, 'unit': 'Crates', 'price': 180.00,
                    'harvest_offset': 0, 'desc': 'Freshly harvested this morning. Hard and durable.',
                    'img': 'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?auto=format&fit=crop&w=300&q=80'
                },
                # Okra (Green Star) - harvested 3 days ago -> rot in 1 day. Freshness: 25% -> URGENT/FLASH SALE
                {
                    'farmer': farmers[2], 'name': 'Okra', 'variety': 'Green Star',
                    'qty': 20, 'unit': 'Baskets', 'price': 80.00,
                    'harvest_offset': 3, 'desc': 'Tender pods, high demand. Price discounted to sell.',
                    'img': 'https://images.unsplash.com/photo-1627308595229-7830a5c91f9f?auto=format&fit=crop&w=300&q=80'
                },
                # Peppers (Legon 18 Habanero) - harvested 2 days ago -> rot in 10 days. Freshness: 83%
                {
                    'farmer': farmers[3], 'name': 'Habanero Peppers', 'variety': 'Legon 18 Red',
                    'qty': 25, 'unit': 'Sacks', 'price': 110.00,
                    'harvest_offset': 2, 'desc': 'Very spicy hot peppers, ideal for exporters or restaurants.',
                    'img': 'https://images.unsplash.com/photo-1588252303782-cb80119abd6d?auto=format&fit=crop&w=300&q=80'
                },
                # Garden Eggs (White Giant) - harvested 6 days ago -> rot in 4 days. Freshness: 40% -> URGENT/FLASH SALE
                {
                    'farmer': farmers[1], 'name': 'Garden Eggs', 'variety': 'White Giant Eggplant',
                    'qty': 18, 'unit': 'Baskets', 'price': 90.00,
                    'harvest_offset': 6, 'desc': 'White garden eggs, slightly soft. Perfect for stews.',
                    'img': 'https://images.unsplash.com/photo-1590301157890-4810ed352733?auto=format&fit=crop&w=300&q=80'
                },
                # Leafy Greens (Gboma) - harvested 2 days ago -> rot in 1 day. Freshness: 33% -> URGENT/FLASH SALE
                {
                    'farmer': farmers[0], 'name': 'Leafy Greens', 'variety': 'Gboma Greens',
                    'qty': 12, 'unit': 'Baskets', 'price': 40.00,
                    'harvest_offset': 2, 'desc': 'Rich organic local greens, harvested under shade.',
                    'img': 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?auto=format&fit=crop&w=300&q=80'
                }
            ]
            
            for pd in produce_data:
                # Calculate harvest date
                harv_date = today - datetime.timedelta(days=pd['harvest_offset'])
                
                Produce.objects.create(
                    farmer=pd['farmer'],
                    name=pd['name'],
                    variety=pd['variety'],
                    quantity_available=pd['qty'],
                    unit=pd['unit'],
                    price_per_unit=pd['price'],
                    harvest_date=harv_date,
                    posting_date=today,
                    description=pd['desc'],
                    image_url=pd['img']
                )

            # 5. Create Connection & Messages between Kumasi_Restaurant_Hub and Kofi_Mensah
            buyer_hub = next((b for b in buyers if b.username == 'Kumasi_Restaurant_Hub'), None)
            farmer_kofi = next((f for f in farmers if f.username == 'Kofi_Mensah'), None)
            farmer_ama = next((f for f in farmers if f.username == 'Ama_Serwaa'), None)

            if buyer_hub and farmer_kofi:
                # Create Accepted Connection
                Connection.objects.create(
                    sender=farmer_kofi,
                    receiver=buyer_hub,
                    status='ACCEPTED'
                )
                
                # Create some historical messages
                messages_data = [
                    (farmer_kofi, buyer_hub, "Hello! I have a fresh batch of Power Rano tomatoes harvested today. Are you interested?"),
                    (buyer_hub, farmer_kofi, "Hi Kofi! Yes, definitely. Our restaurant is running low. What is your price per crate?"),
                    (farmer_kofi, buyer_hub, "Usually GHS 150, but since we are in the same trust circle, I can give it to you for GHS 140 if you buy more than 10 crates."),
                    (buyer_hub, farmer_kofi, "Perfect! I will place an order for 15 crates shortly. Thanks for the discount.")
                ]
                for s, r, text in messages_data:
                    Message.objects.create(sender=s, receiver=r, content=text)

            if buyer_hub and farmer_ama:
                # Create Pending Request from Ama to Kumasi_Restaurant_Hub
                Connection.objects.create(
                    sender=farmer_ama,
                    receiver=buyer_hub,
                    status='PENDING'
                )

            # Create seed notifications for the buyer
            if buyer_hub:
                from users.models import Notification
                Notification.objects.create(
                    user=buyer_hub,
                    notification_type='SMS',
                    title='Welcome to AgriConnect!',
                    content='Welcome to AgriConnect Ghana! Connect with farmers, claim transport, and manage payments safely.',
                    is_read=False
                )
                Notification.objects.create(
                    user=buyer_hub,
                    notification_type='EMAIL',
                    title='Account Configured',
                    content='Your AgriConnect account is fully configured. Start exploring local produce listings today.',
                    is_read=False
                )
                Notification.objects.create(
                    user=buyer_hub,
                    notification_type='SMS',
                    title='Wallet Top-Up Successful',
                    content='Wallet topped up successfully! GHS 2500.00 has been credited to your wallet via Paystack.',
                    is_read=True
                )

        return Response({'status': 'SUCCESS', 'message': 'Demo data seeded successfully!'})


def index_view(request):
    return render(request, 'index.html')

def simulator_view(request):
    from oauth2_provider.models import Application
    from users.models import CustomUser
    
    client_id = "ussd_auto_client_123"
    client_secret = "ussd_auto_secret_456"
    
    app = Application.objects.filter(name="USSD Simulator Auto").first()
    if not app:
        app = Application.objects.create(
            name="USSD Simulator Auto",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            client_id=client_id,
            client_secret=client_secret
        )
    else:
        # Force update the credentials in case it was created previously with random hashes
        app.client_id = client_id
        # In DOT, assigning a plaintext string to client_secret will hash it on save()
        app.client_secret = client_secret
        app.save()
    
    users = CustomUser.objects.exclude(is_superuser=True).order_by('role')
    
    context = {
        'client_id': client_id,
        'client_secret': client_secret,
        'users': users
    }
    return render(request, 'ussd_simulator_app.html', context)
