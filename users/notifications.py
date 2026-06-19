import logging
import requests
from django.conf import settings
from django.core.mail import send_mail
from .models import Notification

logger = logging.getLogger(__name__)

def send_sms(phone_number, message):
    """
    Sends an SMS via Arkesel SMS Gateway API v2.
    If settings.ARKESEL_API_KEY is not set, falls back to logging to console.
    """
    api_key = getattr(settings, 'ARKESEL_API_KEY', '')
    sender_id = getattr(settings, 'ARKESEL_SENDER_ID', 'AgriConnect')
    
    print(f"\n--- [SMS SIMULATOR] To: {phone_number} | Message: {message} ---\n")
    
    if not api_key:
        logger.info(f"Arkesel API Key not configured. SMS not sent via API. Content: {message}")
        return None
        
    url = "https://sms.arkesel.com/api/v2/sms/send"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "sender": sender_id,
        "message": message,
        "recipients": [phone_number]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        logger.info(f"Arkesel API Response: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        logger.error(f"Error calling Arkesel SMS API: {e}")
        return None


def send_email(email_address, subject, content):
    """
    Sends an Email. Falls back to logging to console.
    """
    print(f"\n--- [EMAIL SIMULATOR] To: {email_address} | Subject: {subject} | Content: {content} ---\n")
    
    try:
        send_mail(
            subject=subject,
            message=content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost'),
            recipient_list=[email_address],
            fail_silently=True
        )
    except Exception as e:
        logger.error(f"Error sending email: {e}")


def create_alert(user, notification_type, title, content):
    """
    Creates a Notification record in the database, and dispatches real/simulated SMS or Email.
    """
    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        content=content
    )
    
    if notification_type == 'SMS':
        if user.phone_number:
            send_sms(user.phone_number, content)
        else:
            logger.warning(f"User {user.username} has no phone number. SMS not sent.")
    elif notification_type == 'EMAIL':
        if user.email:
            send_email(user.email, title, content)
        else:
            logger.warning(f"User {user.username} has no email. Email not sent.")
            
    return notification
