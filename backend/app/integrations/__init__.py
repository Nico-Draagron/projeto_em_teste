# backend/app/integrations/__init__.py
"""
External integrations for WeatherBiz Analytics
"""

from app.integrations.nomads_api import NOMADSClient
from app.integrations.openweather_api import OpenWeatherClient
from app.integrations.gemini_api import GeminiClient
from app.integrations.notifications.email import EmailService
from app.integrations.notifications.whatsapp import WhatsAppService
from app.integrations.google_sheets import GoogleSheetsClient
from app.integrations.external_data import ExternalDataService

__all__ = [
    "NOMADSClient",
    "OpenWeatherClient", 
    "GeminiClient",
    "EmailService",
    "WhatsAppService",
    "GoogleSheetsClient",
    "ExternalDataService"
]
