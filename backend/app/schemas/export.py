# ===========================
# backend/app/schemas/export.py
# ===========================

from pydantic import Field, validator, EmailStr
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum

from app.schemas.base import BaseSchema, TenantSchema


class ExportFormat(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    POWERPOINT = "powerpoint"


class ReportType(str, Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    SALES_ANALYSIS = "sales_analysis"
    WEATHER_IMPACT = "weather_impact"
    PREDICTIONS = "predictions"
    ALERTS_SUMMARY = "alerts_summary"
    CUSTOM = "custom"


class ExportRequest(BaseSchema):
    """Request para exportação"""
    report_type: ReportType
    format: ExportFormat
    start_date: date
    end_date: date
    filters: Optional[Dict[str, Any]] = None
    include_charts: bool = True
    include_raw_data: bool = False
    template_id: Optional[str] = None
    recipients: Optional[List[EmailStr]] = None
    
    @validator("end_date")
    def end_after_start(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class ExportResponse(BaseSchema):
    """Response de exportação"""
    job_id: str
    status: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ExportJobStatus(BaseSchema):
    """Status do job de exportação"""
    job_id: str
    status: str = Field(..., regex="^(pending|processing|completed|failed|cancelled)$")
    progress: int = Field(0, ge=0, le=100)
    message: Optional[str] = None
    estimated_completion: Optional[datetime] = None


class ReportTemplate(BaseSchema):
    """Template de relatório"""
    id: str
    name: str
    description: Optional[str] = None
    report_type: ReportType
    format: ExportFormat
    layout: Dict[str, Any]
    variables: List[str]
    is_system: bool = False
    is_active: bool = True


class ScheduledReport(BaseSchema):
    """Relatório agendado"""
    name: str
    report_type: ReportType
    format: ExportFormat
    schedule: str = Field(..., regex="^(daily|weekly|monthly)$")
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    time: time
    recipients: List[EmailStr]
    filters: Optional[Dict[str, Any]] = None
    is_active: bool = True
