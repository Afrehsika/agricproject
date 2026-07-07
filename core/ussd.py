import urllib.parse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from django.http import HttpResponse
from users.models import CustomUser

from rest_framework.permissions import AllowAny

class USSDWebhookView(APIView):
    # Enforce OAuth2 authentication
    authentication_classes = [OAuth2Authentication]
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Client credentials grant does not have a user, so IsAuthenticated fails.
        if not request.auth:
            return HttpResponse("Unauthorized", status=401)
            
        # USSD gateways typically send data as form-urlencoded
        session_id = request.data.get('sessionId', '')
        service_code = request.data.get('serviceCode', '')
        phone_number = request.data.get('phoneNumber', '')
        text = request.data.get('text', '')

        # Fallback to JSON if someone sends JSON
        if not phone_number and hasattr(request, 'data'):
            phone_number = request.data.get('phoneNumber', '')
            text = request.data.get('text', '')
            
        if service_code != '*920*44#':
            return HttpResponse("END Connection problem or invalid MMI code.", content_type="text/plain")

        if not phone_number:
            return HttpResponse("END Error: No phone number provided.", content_type="text/plain")

        # Strip any formatting like '+' from phone number if needed
        # In our DB, it's stored as plain strings
        user = CustomUser.objects.filter(phone_number=phone_number).first()

        if not user:
            return HttpResponse("END Error: Number not registered on AgriConnect.", content_type="text/plain")

        # Parse text (inputs are separated by '*')
        # Example text: "1*2" means user selected 1, then 2.
        inputs = text.split('*') if text else []
        
        response_text = ""

        if len(inputs) == 0:
            # Main Menu
            response_text = f"CON Welcome {user.username} ({user.get_role_display()})\n"
            response_text += "1. Check Wallet\n"
            
            if user.role == 'BUYER':
                response_text += "2. Transporter Approvals\n3. Confirm Escrow Releases\n4. Connect via Phone"
            elif user.role == 'TRANSPORTER':
                response_text += "2. Claim Available Contracts\n3. My Active Cargoes\n4. Connect via Phone"
            elif user.role == 'FARMER':
                response_text += "2. List Tomato Harvest\n3. Dispatch Cargo to Buyer\n4. Connect via Phone"
                
        elif inputs[0] == '1':
            # Check Wallet
            response_text = f"END AgriConnect Wallet:\nBalance: GHS {user.wallet_balance}"
            
        elif inputs[0] == '2':
            if user.role == 'BUYER':
                response_text = "END Transporter Approvals: No pending approvals."
            elif user.role == 'TRANSPORTER':
                response_text = "END Available Contracts: None."
            elif user.role == 'FARMER':
                if len(inputs) == 1:
                    response_text = "CON Enter Tomato Crates yield quantity:"
                elif len(inputs) == 2:
                    response_text = "CON Enter Price per Crate (GHS):"
                elif len(inputs) == 3:
                    qty = inputs[1]
                    price = inputs[2]
                    response_text = f"END Success! Listed {qty} Crates at GHS {price}."
                    
        elif inputs[0] == '3':
            if user.role == 'BUYER':
                response_text = "END Confirm Releases: No pending releases."
            elif user.role == 'TRANSPORTER':
                response_text = "END My Active Cargoes: None."
            elif user.role == 'FARMER':
                response_text = "END Dispatch Cargo: Under Construction."
                
        elif inputs[0] == '4':
            if len(inputs) == 1:
                response_text = "CON Enter mobile phone number to connect:"
            elif len(inputs) == 2:
                phone = inputs[1]
                response_text = f"END Connection request sent to {phone}!"
        else:
            response_text = "END Invalid Option Selected."

        # Return plain text response required by USSD gateways
        return HttpResponse(response_text, content_type="text/plain")
