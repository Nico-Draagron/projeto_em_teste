# GET/POST /alerts, /notifications
# backend/app/api/v1/endpoints/alerts.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime, date

from app.api import deps
from app.models.database import User, Company, Alert, AlertRule
from app.models.schemas import (
    AlertConfig,
    AlertTrigger,
    AlertResponse,
    AlertHistory,
    PaginatedResponse
)
from app.services.alert_service import AlertService, AlertType, AlertPriority, AlertChannel

router = APIRouter()


@router.post("/rules", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    alert_config: AlertConfig,
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Create new alert rule
    """
    service = AlertService(db, company.id)
    
    try:
        rule = await service.create_alert_rule(
            name=alert_config.name,
            alert_type=AlertType(alert_config.alert_type),
            conditions=alert_config.conditions,
            channels=[AlertChannel(c) for c in alert_config.channels],
            priority=AlertPriority(alert_config.priority.value),
            message_template=alert_config.message_template,
            cooldown_minutes=alert_config.cooldown_minutes,
            is_active=alert_config.is_active
        )
        
        return {
            "id": rule.id,
            "name": rule.name,
            "alert_type": rule.alert_type,
            "is_active": rule.is_active,
            "created_at": rule.created_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating alert rule: {str(e)}"
        )


@router.get("/rules")
async def list_alert_rules(
    is_active: Optional[bool] = Query(None),
    alert_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    List alert rules
    """
    query = db.query(AlertRule).filter(AlertRule.company_id == company.id)
    
    if is_active is not None:
        query = query.filter(AlertRule.is_active == is_active)
    if alert_type:
        query = query.filter(AlertRule.alert_type == alert_type)
    
    total = query.count()
    rules = query.offset(skip).limit(limit).all()
    
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "alert_type": r.alert_type,
                "priority": r.priority,
                "is_active": r.is_active,
                "trigger_count": r.trigger_count,
                "last_triggered": r.last_triggered.isoformat() if r.last_triggered else None
            }
            for r in rules
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.put("/rules/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    updates: dict,
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Update alert rule
    """
    service = AlertService(db, company.id)
    
    try:
        rule = await service.update_alert_rule(rule_id, **updates)
        return {"message": "Alert rule updated successfully", "rule_id": rule.id}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating alert rule: {str(e)}"
        )


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    current_user: User = Depends(deps.require_role("admin")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Delete alert rule
    """
    service = AlertService(db, company.id)
    
    try:
        success = await service.delete_alert_rule(rule_id)
        if success:
            return {"message": "Alert rule deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert rule not found"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting alert rule: {str(e)}"
        )


@router.post("/trigger", response_model=AlertResponse)
async def trigger_manual_alert(
    alert: AlertTrigger,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Manually trigger an alert
    """
    service = AlertService(db, company.id)
    
    try:
        response = await service.trigger_manual_alert(
            title=alert.title,
            message=alert.message,
            channels=[AlertChannel(c) for c in alert.channels],
            priority=AlertPriority(alert.priority.value),
            data=alert.data
        )
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering alert: {str(e)}"
        )


@router.post("/check")
async def check_alerts(
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Check and trigger alerts based on current conditions
    """
    service = AlertService(db, company.id)
    
    try:
        triggered_alerts = await service.check_and_trigger_alerts()
        
        return {
            "checked_at": datetime.utcnow().isoformat(),
            "triggered_count": len(triggered_alerts),
            "triggered_alerts": [
                {
                    "alert_id": a.alert_id,
                    "title": a.title,
                    "priority": a.priority
                }
                for a in triggered_alerts
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking alerts: {str(e)}"
        )


@router.get("/active")
async def get_active_alerts(
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get currently active alerts
    """
    service = AlertService(db, company.id)
    
    try:
        active_alerts = await service.get_active_alerts()
        return {
            "alerts": active_alerts,
            "total": len(active_alerts),
            "critical_count": len([a for a in active_alerts if a["priority"] == "critical"]),
            "high_count": len([a for a in active_alerts if a["priority"] == "high"])
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting active alerts: {str(e)}"
        )


@router.get("/history", response_model=List[dict])
async def get_alert_history(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    alert_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get alert history
    """
    service = AlertService(db, company.id)
    
    try:
        history = await service.get_alert_history(
            start_date=datetime.combine(start_date, datetime.min.time()) if start_date else None,
            end_date=datetime.combine(end_date, datetime.max.time()) if end_date else None,
            alert_type=AlertType(alert_type) if alert_type else None,
            limit=limit
        )
        return history
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting alert history: {str(e)}"
        )


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_note: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Mark alert as resolved
    """
    service = AlertService(db, company.id)
    
    try:
        success = await service.resolve_alert(alert_id, resolution_note)
        if success:
            return {"message": "Alert resolved successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resolving alert: {str(e)}"
        )


@router.post("/test/{rule_id}")
async def test_alert_rule(
    rule_id: str,
    test_data: Optional[dict] = None,
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Test alert rule without triggering notifications
    """
    service = AlertService(db, company.id)
    
    try:
        result = await service.test_alert_rule(rule_id, test_data)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing alert rule: {str(e)}"
        )


# ===========================
# backend/app/api/v1/endpoints/notifications.py
# ===========================

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime

from app.api import deps
from app.models.database import User, Company, Notification
from app.models.schemas import (
    NotificationRequest,
    NotificationResponse,
    NotificationSettings,
    PaginatedResponse
)
from app.services.notification_service import NotificationService, NotificationType, NotificationChannel

router = APIRouter()


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    notification: NotificationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Send notification to specified recipients
    """
    service = NotificationService(db, company.id)
    
    try:
        response = await service.send_notification(
            recipients=notification.recipients,
            title=notification.title,
            message=notification.message,
            notification_type=NotificationType(notification.type.value),
            channels=[NotificationChannel(c) for c in notification.channels],
            priority=notification.priority,
            data=notification.data,
            schedule_for=notification.schedule_for
        )
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending notification: {str(e)}"
        )


@router.get("/", response_model=PaginatedResponse)
async def list_notifications(
    unread_only: bool = Query(False),
    notification_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    List user notifications
    """
    service = NotificationService(db, company.id)
    
    notifications = await service.get_user_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
        offset=skip
    )
    
    # Get total count
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.filter(Notification.is_read == False)
    if notification_type:
        query = query.filter(Notification.type == notification_type)
    
    total = query.count()
    
    return {
        "items": notifications,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": total > skip + limit
    }


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get count of unread notifications
    """
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    
    return {"unread_count": count}


@router.post("/mark-read")
async def mark_notifications_as_read(
    notification_ids: List[str],
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Mark notifications as read
    """
    service = NotificationService(db, company.id)
    
    success = await service.mark_as_read(notification_ids, current_user.id)
    
    if success:
        return {"message": f"{len(notification_ids)} notifications marked as read"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to mark notifications as read"
        )


@router.post("/mark-all-read")
async def mark_all_notifications_as_read(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Mark all notifications as read
    """
    updated = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update(
        {"is_read": True, "read_at": datetime.utcnow()},
        synchronize_session=False
    )
    
    db.commit()
    
    return {"message": f"{updated} notifications marked as read"}


@router.get("/settings", response_model=NotificationSettings)
async def get_notification_settings(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get user notification settings
    """
    from app.models.database import NotificationPreference
    
    pref = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id
    ).first()
    
    if pref:
        import json
        preferences = json.loads(pref.preferences)
        
        return NotificationSettings(
            email_enabled=preferences.get("email_enabled", True),
            whatsapp_enabled=preferences.get("whatsapp_enabled", False),
            internal_enabled=preferences.get("internal_enabled", True),
            digest_frequency=preferences.get("digest_frequency", "daily"),
            alert_types=preferences.get("alert_types", []),
            quiet_hours=preferences.get("quiet_hours")
        )
    
    # Return defaults
    return NotificationSettings()


@router.put("/settings")
async def update_notification_settings(
    settings: NotificationSettings,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Update user notification settings
    """
    service = NotificationService(db, company.id)
    
    success = await service.update_preferences(
        user_id=current_user.id,
        preferences=settings.dict()
    )
    
    if success:
        return {"message": "Notification settings updated successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification settings"
        )


@router.post("/digest")
async def create_notification_digest(
    frequency: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    force: bool = Query(False),
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Create and send notification digest
    """
    service = NotificationService(db, company.id)
    
    try:
        result = await service.create_digest(frequency=frequency, force=force)
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating digest: {str(e)}"
        )


@router.post("/test")
async def test_notification(
    channel: str = Query("internal", regex="^(email|whatsapp|internal)$"),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Send test notification
    """
    service = NotificationService(db, company.id)
    
    test_message = f"Teste de notificação {channel} - WeatherBiz Analytics"
    
    if channel == "email":
        success = await service.send_email(
            recipients=[current_user.email],
            subject="Teste de Email - WeatherBiz",
            body=test_message
        )
    elif channel == "whatsapp":
        if current_user.phone:
            success = await service.send_whatsapp(
                phone_numbers=[current_user.phone],
                message=test_message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User phone number not configured"
            )
    else:  # internal
        success = await service.create_internal_notification(
            title="Teste de Notificação",
            message=test_message,
            target_users=[current_user.id]
        )
    
    if success:
        return {"message": f"Test notification sent via {channel}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification via {channel}"
        )


# ===========================
# backend/app/api/v1/endpoints/exports.py
# ===========================

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime, date
import os

from app.api import deps
from app.models.database import User, Company, ExportJob
from app.models.schemas import (
    ExportRequest,
    ExportResponse,
    ReportSchedule,
    PaginatedResponse
)
from app.services.export_service import ExportService, ExportFormat, ReportType

router = APIRouter()


@router.post("/generate", response_model=ExportResponse)
async def generate_report(
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Generate export/report
    """
    service = ExportService(db, company.id)
    
    try:
        response = await service.generate_report(
            report_type=ReportType(export_request.report_type),
            format=ExportFormat(export_request.format.value),
            start_date=datetime.combine(export_request.start_date, datetime.min.time()),
            end_date=datetime.combine(export_request.end_date, datetime.max.time()),
            filters=export_request.filters,
            template_id=export_request.template_id,
            include_charts=export_request.include_charts,
            async_generation=True
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}"
        )


@router.get("/download/{job_id}")
async def download_report(
    job_id: str,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Download generated report
    """
    job = db.query(ExportJob).filter(
        ExportJob.id == job_id,
        ExportJob.company_id == company.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export job not found"
        )
    
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report is not ready. Current status: {job.status}"
        )
    
    if not job.file_path or not os.path.exists(job.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found"
        )
    
    # Determine MIME type
    mime_types = {
        "pdf": "application/pdf",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "json": "application/json"
    }
    
    media_type = mime_types.get(job.format, "application/octet-stream")
    filename = os.path.basename(job.file_path)
    
    return FileResponse(
        path=job.file_path,
        media_type=media_type,
        filename=filename
    )


@router.get("/status/{job_id}")
async def get_export_status(
    job_id: str,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get export job status
    """
    job = db.query(ExportJob).filter(
        ExportJob.id == job_id,
        ExportJob.company_id == company.id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export job not found"
        )
    
    response = {
        "job_id": job.id,
        "status": job.status,
        "report_type": job.report_type,
        "format": job.format,
        "created_at": job.created_at.isoformat()
    }
    
    if job.status == "completed":
        response["completed_at"] = job.completed_at.isoformat()
        response["file_size"] = job.file_size
        response["download_url"] = f"/api/v1/exports/download/{job.id}"
    elif job.status == "failed":
        response["error_message"] = job.error_message
    
    return response


@router.get("/history")
async def get_export_history(
    limit: int = Query(50, ge=1, le=200),
    include_failed: bool = Query(False),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get export/report history
    """
    service = ExportService(db, company.id)
    
    try:
        history = await service.get_export_history(
            limit=limit,
            include_failed=include_failed
        )
        
        return {
            "exports": history,
            "total": len(history)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting export history: {str(e)}"
        )


@router.post("/schedule")
async def schedule_report(
    schedule: ReportSchedule,
    current_user: User = Depends(deps.require_role("manager")),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Schedule automatic report generation
    """
    service = ExportService(db, company.id)
    
    try:
        # Parse start time
        start_time = None
        if schedule.start_time:
            hour, minute = map(int, schedule.start_time.split(':'))
            start_time = datetime.utcnow().replace(hour=hour, minute=minute, second=0)
        
        result = await service.schedule_report(
            report_config={
                "name": schedule.name,
                "report_type": schedule.report_type,
                "format": schedule.format.value,
                "filters": schedule.filters
            },
            schedule=schedule.schedule,
            recipients=schedule.recipients,
            start_time=start_time
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scheduling report: {str(e)}"
        )


@router.get("/templates")
async def list_report_templates(
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    List available report templates
    """
    from app.models.database import ExportTemplate
    
    templates = db.query(ExportTemplate).filter(
        or_(
            ExportTemplate.company_id == company.id,
            ExportTemplate.is_system == True
        ),
        ExportTemplate.is_active == True
    ).all()
    
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "report_type": t.report_type,
                "format": t.format,
                "is_system": t.is_system
            }
            for t in templates
        ],
        "total": len(templates)
    }


# ===========================
# backend/app/api/v1/endpoints/chat.py
# ===========================

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime

from app.api import deps
from app.models.database import User, Company
from app.models.schemas import (
    ChatMessage,
    ChatResponse,
    AIInsight,
    PaginatedResponse
)
from app.services.ai_agent_service import AIAgentService

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_chat_message(
    message: ChatMessage,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Send message to AI agent
    """
    service = AIAgentService(db, company.id, current_user.id)
    
    try:
        response = await service.process_message(
            message=message.message,
            session_id=message.session_id,
            include_context=True
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )


@router.get("/history")
async def get_chat_history(
    session_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get chat history
    """
    service = AIAgentService(db, company.id, current_user.id)
    
    try:
        history = await service.get_chat_history(
            session_id=session_id,
            limit=limit
        )
        
        return {
            "messages": history,
            "total": len(history),
            "session_id": session_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting chat history: {str(e)}"
        )


@router.get("/sessions")
async def list_chat_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    List user's chat sessions
    """
    from app.models.database import ChatSession
    
    query = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.company_id == company.id
    )
    
    total = query.count()
    sessions = query.order_by(
        ChatSession.last_activity.desc()
    ).offset(skip).limit(limit).all()
    
    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title or f"Session {s.created_at.strftime('%Y-%m-%d')}",
                "created_at": s.created_at.isoformat(),
                "last_activity": s.last_activity.isoformat(),
                "is_active": s.is_active
            }
            for s in sessions
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/question")
async def ask_question(
    question: str,
    context: Optional[dict] = None,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Ask a specific question to AI agent
    """
    service = AIAgentService(db, company.id, current_user.id)
    
    try:
        answer = await service.answer_question(
            question=question,
            data_context=context
        )
        
        return answer
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error answering question: {str(e)}"
        )


@router.get("/suggestions")
async def get_chat_suggestions(
    context: str = Query("general"),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get suggested questions/topics
    """
    suggestions_map = {
        "general": [
            "Como estão as vendas hoje?",
            "Qual a previsão do tempo para amanhã?",
            "Existe algum alerta ativo?",
            "Mostre um resumo da semana"
        ],
        "sales": [
            "Qual foi o melhor dia de vendas este mês?",
            "Compare as vendas desta semana com a anterior",
            "Quais produtos estão vendendo mais?",
            "Identifique anomalias nas vendas recentes"
        ],
        "weather": [
            "Como o clima afetou as vendas ontem?",
            "Qual a correlação entre temperatura e vendas?",
            "Vai chover nos próximos dias?",
            "Quando foi o último evento climático extremo?"
        ],
        "insights": [
            "Quais são os principais insights do mês?",
            "Que padrões você identificou nos dados?",
            "O que você recomenda para aumentar as vendas?",
            "Simule um cenário de temperatura alta amanhã"
        ]
    }
    
    return {
        "suggestions": suggestions_map.get(context, suggestions_map["general"]),
        "context": context
    }


@router.post("/report-summary")
async def generate_report_summary(
    report_data: dict,
    max_length: int = Query(500, ge=100, le=2000),
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Generate AI summary of report data
    """
    service = AIAgentService(db, company.id, current_user.id)
    
    try:
        summary = await service.generate_report_summary(
            report_data=report_data,
            max_length=max_length
        )
        
        return {
            "summary": summary,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating summary: {str(e)}"
        )


@router.post("/explain-chart")
async def explain_chart(
    chart_data: dict,
    chart_type: str,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get AI explanation of chart/visualization
    """
    service = AIAgentService(db, company.id, current_user.id)
    
    try:
        explanation = await service.explain_chart(
            chart_data=chart_data,
            chart_type=chart_type
        )
        
        return {
            "explanation": explanation,
            "chart_type": chart_type
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error explaining chart: {str(e)}"
        )


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    current_user: User = Depends(deps.get_current_active_user),
    company: Company = Depends(deps.get_current_company),
    db: Session = Depends(deps.get_db)
):
    """
    WebSocket endpoint for real-time chat
    """
    await websocket.accept()
    
    service = AIAgentService(db, company.id, current_user.id)
    session_id = None
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            if data.get("type") == "message":
                # Process message
                response = await service.process_message(
                    message=data.get("message", ""),
                    session_id=session_id,
                    include_context=True
                )
                
                # Update session ID
                session_id = response.session_id
                
                # Send response
                await websocket.send_json({
                    "type": "response",
                    "data": {
                        "message": response.message,
                        "intent": response.intent,
                        "suggestions": response.suggestions,
                        "timestamp": response.timestamp
                    }
                })
            
            elif data.get("type") == "typing":
                # Handle typing indicator if needed
                pass
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"Error: {str(e)}"
        })
        await websocket.close()