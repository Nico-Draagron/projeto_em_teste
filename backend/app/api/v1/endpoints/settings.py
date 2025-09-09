# backend/app/api/v1/endpoints/settings.py
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, require_manager
from app.models.user import User
from app.models.company import CompanySettings
from app.models.integration import Integration
from app.schemas.settings import (
    GeneralSettings,
    NotificationSettings,
    IntegrationSettings,
    AlertThresholds,
    DataRetention,
    APISettings
)

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/general", response_model=GeneralSettings)
async def get_general_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get general application settings for the company
    """
    settings = db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).first()
    
    if not settings:
        # Create default settings
        settings = CompanySettings(
            company_id=current_user.company_id,
            timezone="America/Sao_Paulo",
            currency="BRL",
            language="pt-BR",
            date_format="DD/MM/YYYY",
            time_format="24h",
            week_starts_on="monday",
            fiscal_year_start=1,
            default_location="São Paulo, BR"
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings

@router.put("/general", response_model=GeneralSettings)
async def update_general_settings(
    settings_data: GeneralSettings,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Update general settings (Manager or Admin only)
    """
    settings = db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).first()
    
    if not settings:
        settings = CompanySettings(company_id=current_user.company_id)
        db.add(settings)
    
    # Update fields
    for field, value in settings_data.dict(exclude_unset=True).items():
        if hasattr(settings, field):
            setattr(settings, field, value)
    
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    
    return settings

@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get notification settings
    """
    settings = db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).first()
    
    return {
        "email_enabled": settings.notification_email if settings else True,
        "whatsapp_enabled": settings.notification_whatsapp if settings else False,
        "in_app_enabled": settings.notification_in_app if settings else True,
        "daily_summary": settings.daily_summary if settings else True,
        "weekly_report": settings.weekly_report if settings else True,
        "alert_notifications": settings.alert_notifications if settings else True,
        "summary_time": settings.summary_time if settings else "09:00",
        "report_day": settings.report_day if settings else "monday",
        "notification_channels": {
            "critical_alerts": ["email", "whatsapp", "in_app"],
            "normal_alerts": ["email", "in_app"],
            "reports": ["email"],
            "system_updates": ["in_app"]
        }
    }

@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    settings_data: NotificationSettings,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Update notification settings
    """
    settings = db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).first()
    
    if not settings:
        settings = CompanySettings(company_id=current_user.company_id)
        db.add(settings)
    
    # Map notification settings to database fields
    settings.notification_email = settings_data.email_enabled
    settings.notification_whatsapp = settings_data.whatsapp_enabled
    settings.notification_in_app = settings_data.in_app_enabled
    settings.daily_summary = settings_data.daily_summary
    settings.weekly_report = settings_data.weekly_report
    settings.alert_notifications = settings_data.alert_notifications
    settings.summary_time = settings_data.summary_time
    settings.report_day = settings_data.report_day
    
    settings.updated_at = datetime.utcnow()
    db.commit()
    
    return settings_data

@router.get("/alert-thresholds", response_model=AlertThresholds)
async def get_alert_thresholds(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get alert threshold settings
    """
    settings = db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).first()
    
    return {
        "temperature_min": settings.alert_threshold_temp_min if settings else 10,
        "temperature_max": settings.alert_threshold_temp_max if settings else 35,
        "precipitation_min": settings.alert_threshold_rain if settings else 30,
        "wind_speed_max": settings.alert_threshold_wind if settings else 60,
        "humidity_min": 30,
        "humidity_max": 90,
        "sales_drop_percent": 20,
        "sales_spike_percent": 30
    }

@router.put("/alert-thresholds", response_model=AlertThresholds)
async def update_alert_thresholds(
    thresholds: AlertThresholds,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Update alert thresholds
    """
    settings = db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).first()
    
    if not settings:
        settings = CompanySettings(company_id=current_user.company_id)
        db.add(settings)
    
    settings.alert_threshold_temp_min = thresholds.temperature_min
    settings.alert_threshold_temp_max = thresholds.temperature_max
    settings.alert_threshold_rain = thresholds.precipitation_min
    settings.alert_threshold_wind = thresholds.wind_speed_max
    
    settings.updated_at = datetime.utcnow()
    db.commit()
    
    return thresholds

@router.get("/integrations", response_model=List[IntegrationSettings])
async def get_integrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all configured integrations
    """
    integrations = db.query(Integration).filter(
        Integration.company_id == current_user.company_id
    ).all()
    
    return [
        {
            "id": str(i.id),
            "name": i.name,
            "type": i.type,
            "is_active": i.is_active,
            "config": i.config,
            "last_sync": i.last_sync,
            "created_at": i.created_at
        }
        for i in integrations
    ]

@router.post("/integrations", response_model=IntegrationSettings)
async def add_integration(
    integration_data: IntegrationSettings,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Add new integration
    """
    # Check if integration already exists
    existing = db.query(Integration).filter(
        Integration.company_id == current_user.company_id,
        Integration.type == integration_data.type
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Integration of type {integration_data.type} already exists"
        )
    
    new_integration = Integration(
        company_id=current_user.company_id,
        name=integration_data.name,
        type=integration_data.type,
        config=integration_data.config,
        is_active=integration_data.is_active,
        created_at=datetime.utcnow()
    )
    
    db.add(new_integration)
    db.commit()
    db.refresh(new_integration)
    
    return new_integration

@router.put("/integrations/{integration_id}")
async def update_integration(
    integration_id: str,
    integration_data: dict,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Update integration configuration
    """
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.company_id == current_user.company_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    for field, value in integration_data.items():
        if hasattr(integration, field) and field != "id":
            setattr(integration, field, value)
    
    integration.updated_at = datetime.utcnow()
    db.commit()
    
    return integration

@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: str,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Delete integration
    """
    integration = db.query(Integration).filter(
        Integration.id == integration_id,
        Integration.company_id == current_user.company_id
    ).first()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    db.delete(integration)
    db.commit()
    
    return {"message": "Integration deleted successfully"}

@router.get("/data-retention", response_model=DataRetention)
async def get_data_retention_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get data retention settings
    """
    settings = db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).first()
    
    return {
        "weather_data_days": settings.weather_retention_days if settings else 730,
        "sales_data_days": settings.sales_retention_days if settings else 1095,
        "alerts_history_days": settings.alerts_retention_days if settings else 365,
        "chat_history_days": settings.chat_retention_days if settings else 180,
        "predictions_days": settings.predictions_retention_days if settings else 365,
        "auto_cleanup": settings.auto_cleanup if settings else True,
        "cleanup_schedule": settings.cleanup_schedule if settings else "weekly"
    }

@router.put("/data-retention", response_model=DataRetention)
async def update_data_retention_settings(
    retention_data: DataRetention,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Update data retention settings (Admin only)
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can modify data retention settings"
        )
    
    settings = db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).first()
    
    if not settings:
        settings = CompanySettings(company_id=current_user.company_id)
        db.add(settings)
    
    settings.weather_retention_days = retention_data.weather_data_days
    settings.sales_retention_days = retention_data.sales_data_days
    settings.alerts_retention_days = retention_data.alerts_history_days
    settings.chat_retention_days = retention_data.chat_history_days
    settings.predictions_retention_days = retention_data.predictions_days
    settings.auto_cleanup = retention_data.auto_cleanup
    settings.cleanup_schedule = retention_data.cleanup_schedule
    
    settings.updated_at = datetime.utcnow()
    db.commit()
    
    return retention_data

@router.get("/api", response_model=APISettings)
async def get_api_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get API access settings
    """
    company = current_user.company
    
    return {
        "api_enabled": company.api_access_enabled if company else False,
        "api_key": company.api_key if company and company.api_access_enabled else None,
        "rate_limit": company.api_rate_limit if company else 1000,
        "allowed_ips": company.allowed_ips if company else [],
        "webhook_url": company.webhook_url if company else None,
        "webhook_events": company.webhook_events if company else []
    }

@router.post("/api/regenerate-key")
async def regenerate_api_key(
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Regenerate API key
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can regenerate API keys"
        )
    
    company = current_user.company
    
    if not company.api_access_enabled:
        raise HTTPException(
            status_code=400,
            detail="API access is not enabled for your plan"
        )
    
    # Generate new API key
    import secrets
    new_api_key = f"wbz_{secrets.token_urlsafe(32)}"
    
    company.api_key = new_api_key
    company.api_key_generated_at = datetime.utcnow()
    db.commit()
    
    return {
        "api_key": new_api_key,
        "message": "API key regenerated successfully"
    }

@router.post("/reset-to-defaults")
async def reset_to_defaults(
    confirm: bool = Body(..., embed=True),
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """
    Reset all settings to defaults
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required to reset settings"
        )
    
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can reset settings to defaults"
        )
    
    # Delete current settings
    db.query(CompanySettings).filter(
        CompanySettings.company_id == current_user.company_id
    ).delete()
    
    # Create new default settings
    default_settings = CompanySettings(
        company_id=current_user.company_id,
        timezone="America/Sao_Paulo",
        currency="BRL",
        language="pt-BR",
        weather_units="metric",
        date_format="DD/MM/YYYY",
        time_format="24h",
        created_at=datetime.utcnow()
    )
    
    db.add(default_settings)
    db.commit()
    
    return {
        "message": "Settings reset to defaults successfully"
    }