# ===========================
# backend/app/schemas/notification.py
# ===========================

from pydantic import Field, validator, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from app.schemas.base import BaseSchema, TenantSchema, TimestampSchema


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    IN_APP = "in_app"


class NotificationBase(BaseSchema):
    """Base notification schema"""
    type: str
    channel: NotificationChannel
    title: str
    message: str
    priority: str = Field(default="normal", regex="^(low|normal|high|urgent)$")
    data: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase, TenantSchema):
    """Schema para criação de notificação"""
    user_id: Optional[int] = None
    recipients: Optional[List[str]] = None
    scheduled_for: Optional[datetime] = None


class NotificationResponse(NotificationBase, TenantSchema, TimestampSchema):
    """Schema de resposta de notificação"""
    id: str
    user_id: Optional[int] = None
    status: str
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error_message: Optional[str] = None


class NotificationPreferences(BaseSchema):
    """Preferências de notificação"""
    email_enabled: bool = True
    email_address: Optional[EmailStr] = None
    sms_enabled: bool = False
    sms_number: Optional[str] = None
    whatsapp_enabled: bool = False
    whatsapp_number: Optional[str] = None
    slack_enabled: bool = False
    slack_webhook: Optional[str] = None
    in_app_enabled: bool = True
    quiet_hours_start: Optional[time] = None
    quiet_hours_end: Optional[time] = None


class NotificationBatch(BaseSchema):
    """Envio em lote de notificações"""
    template_id: Optional[str] = None
    recipients: List[Dict[str, str]]
    channels: List[NotificationChannel]
    variables: Dict[str, Any]
    schedule: Optional[datetime] = None
