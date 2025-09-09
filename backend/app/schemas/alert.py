# ===========================
# backend/app/schemas/alert.py
# ===========================

from pydantic import Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from app.schemas.base import BaseSchema, TenantSchema, TimestampSchema


class AlertType(str, Enum):
    WEATHER = "weather"
    SALES = "sales"
    ANOMALY = "anomaly"
    THRESHOLD = "threshold"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertRuleBase(BaseSchema):
    """Base alert rule schema"""
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    alert_type: AlertType
    conditions: Dict[str, Any]
    severity: AlertSeverity = AlertSeverity.MEDIUM
    channels: List[str] = ["in_app"]
    recipients: List[str] = []
    is_active: bool = True


class AlertRuleCreate(AlertRuleBase, TenantSchema):
    """Schema para criação de regra de alerta"""
    pass


class AlertRuleResponse(AlertRuleBase, TenantSchema, TimestampSchema):
    """Schema de resposta de regra de alerta"""
    id: str
    triggered_count: int = 0
    last_triggered: Optional[datetime] = None


class AlertBase(BaseSchema):
    """Base alert schema"""
    rule_id: str
    title: str
    message: str
    severity: AlertSeverity
    data: Dict[str, Any]


class AlertCreate(AlertBase, TenantSchema):
    """Schema para criação de alerta"""
    triggered_value: Optional[float] = None


class AlertUpdate(BaseSchema):
    """Schema para atualização de alerta"""
    status: str = Field(..., regex="^(new|acknowledged|resolved|dismissed)$")
    notes: Optional[str] = None


class AlertResponse(AlertBase, TenantSchema, TimestampSchema):
    """Schema de resposta de alerta"""
    id: str
    status: str
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    notes: Optional[str] = None