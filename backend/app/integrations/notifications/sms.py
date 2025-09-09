# ===========================
# backend/app/integrations/notifications/sms.py
# ===========================
"""
SMS notification service using Twilio or similar
"""

import httpx
from typing import List, Optional
import logging
from base64 import b64encode

from app.core.config import settings

logger = logging.getLogger(__name__)


class SMSService:
    """
    Service for sending SMS notifications
    Using Twilio as example (can be adapted for other providers)
    """
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.api_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}"
        self.client = httpx.AsyncClient(timeout=10.0)
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning("SMS service (Twilio) not fully configured")
    
    async def send_sms(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None
    ) -> bool:
        """
        Send SMS message
        """
        if not self.auth_token:
            logger.warning("SMS service not configured")
            return False
        
        try:
            # Format phone number
            to_number = self._format_phone_number(to_number)
            
            # Prepare data
            data = {
                "From": self.from_number,
                "To": to_number,
                "Body": message
            }
            
            if media_url:
                data["MediaUrl"] = media_url
            
            # Create auth header
            auth = b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
            
            # Send SMS
            response = await self.client.post(
                f"{self.api_url}/Messages.json",
                data=data,
                headers={
                    "Authorization": f"Basic {auth}"
                }
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"SMS sent to {to_number}")
                return True
            else:
                logger.error(f"SMS API error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send SMS: {str(e)}")
            return False
    
    async def send_alert_sms(
        self,
        to_number: str,
        alert_type: str,
        alert_message: str,
        severity: str = "medium"
    ) -> bool:
        """
        Send alert via SMS (limited to 160 chars)
        """
        # Create concise message
        emoji = {
            "low": "ℹ",
            "medium": "⚠",
            "high": "🔴",
            "critical": "🚨"
        }.get(severity, "⚠")
        
        # Truncate message to fit SMS limit
        max_msg_length = 140  # Leave room for header
        truncated_msg = alert_message[:max_msg_length]
        if len(alert_message) > max_msg_length:
            truncated_msg += "..."
        
        message = f"{emoji} WeatherBiz {alert_type}: {truncated_msg}"
        
        return await self.send_sms(to_number, message)
    
    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number for SMS
        """
        # Remove all non-numeric characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Add country code if not present
        if not phone.startswith('+'):
            # Assume Brazil if no country code
            if not phone.startswith('55'):
                phone = '55' + phone
            phone = '+' + phone
        
        return phone


# ===========================
# backend/app/integrations/payment/__init__.py
# ===========================
"""
Payment integrations
"""

from app.integrations.payment.stripe import StripeClient

__all__ = ["StripeClient"]
