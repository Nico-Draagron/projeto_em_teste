# WhatsApp Business API
# ===========================
# backend/app/integrations/notifications/whatsapp.py
# ===========================
"""
WhatsApp Business API Integration
"""

import httpx
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Service for sending WhatsApp messages via Business API
    """
    
    def __init__(self):
        self.api_url = settings.WHATSAPP_API_URL
        self.api_token = settings.WHATSAPP_API_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.client = httpx.AsyncClient(timeout=30.0)
        
        if not all([self.api_url, self.api_token, self.phone_number_id]):
            logger.warning("WhatsApp Business API not fully configured")
    
    async def send_message(
        self,
        to_number: str,
        message: str,
        template: Optional[str] = None,
        template_params: Optional[List[str]] = None,
        media_url: Optional[str] = None
    ) -> bool:
        """
        Send WhatsApp message
        """
        if not self.api_token:
            logger.warning("WhatsApp API not configured")
            return False
        
        try:
            # Format phone number (remove special characters, add country code if needed)
            to_number = self._format_phone_number(to_number)
            
            if template:
                # Send template message
                payload = self._build_template_payload(to_number, template, template_params)
            elif media_url:
                # Send media message
                payload = self._build_media_payload(to_number, message, media_url)
            else:
                # Send text message
                payload = self._build_text_payload(to_number, message)
            
            response = await self.client.post(
                f"{self.api_url}/{self.phone_number_id}/messages",
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"WhatsApp message sent to {to_number}")
                return True
            else:
                logger.error(f"WhatsApp API error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {str(e)}")
            return False
    
    async def send_alert(
        self,
        to_number: str,
        alert_type: str,
        alert_message: str,
        severity: str = "medium",
        action_url: Optional[str] = None
    ) -> bool:
        """
        Send alert via WhatsApp
        """
        # Format alert message
        emoji = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔴",
            "critical": "🚨"
        }.get(severity, "⚠️")
        
        message = f"{emoji} *Alerta WeatherBiz*\n\n"
        message += f"*Tipo:* {alert_type}\n"
        message += f"*Severidade:* {severity.upper()}\n\n"
        message += f"{alert_message}"
        
        if action_url:
            message += f"\n\n🔗 Ver detalhes: {action_url}"
        
        return await self.send_message(to_number, message)
    
    async def send_report_notification(
        self,
        to_number: str,
        report_type: str,
        download_url: str
    ) -> bool:
        """
        Send report ready notification
        """
        message = f"📊 *Relatório WeatherBiz Pronto*\n\n"
        message += f"Seu relatório *{report_type}* está pronto!\n\n"
        message += f"📥 Download: {download_url}\n\n"
        message += f"_Link válido por 24 horas_"
        
        return await self.send_message(to_number, message)
    
    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number for WhatsApp API
        """
        # Remove all non-numeric characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Add Brazil country code if not present
        if not phone.startswith('55'):
            phone = '55' + phone
        
        return phone
    
    def _build_text_payload(self, to: str, message: str) -> Dict[str, Any]:
        """
        Build payload for text message
        """
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": True,
                "body": message
            }
        }
    
    def _build_template_payload(
        self,
        to: str,
        template: str,
        params: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build payload for template message
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template,
                "language": {
                    "code": "pt_BR"
                }
            }
        }
        
        if params:
            payload["template"]["components"] = [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": param}
                    for param in params
                ]
            }]
        
        return payload
    
    def _build_media_payload(
        self,
        to: str,
        caption: str,
        media_url: str
    ) -> Dict[str, Any]:
        """
        Build payload for media message
        """
        # Determine media type from URL
        media_type = "image"  # Default
        if media_url.lower().endswith(('.pdf', '.doc', '.docx')):
            media_type = "document"
        elif media_url.lower().endswith(('.mp4', '.mov', '.avi')):
            media_type = "video"
        
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": media_type,
            media_type: {
                "link": media_url,
                "caption": caption
            }
        }