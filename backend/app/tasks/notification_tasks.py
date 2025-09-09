# ===========================
# backend/app/tasks/notification_tasks.py
# ===========================

from typing import List, Dict, Optional
from celery import Task
from celery.utils.log import get_task_logger
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.database import Notification, User, Company
from app.services.notification_service import NotificationService

logger = get_task_logger(__name__)


@celery_app.task(name="send_email", bind=True, max_retries=3)
def send_email(
    self,
    to_emails: List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict]] = None,
    company_id: Optional[str] = None
) -> Dict:
    """
    Envia email com retry automático
    """
    logger.info(f"Sending email to {len(to_emails)} recipients")
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = ", ".join(to_emails)
        
        # Adicionar corpo do email
        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))
        
        # Adicionar anexos
        if attachments:
            for attachment in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment["content"])
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {attachment['filename']}"
                )
                msg.attach(part)
        
        # Enviar email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            server.send_message(msg)
        
        # Registrar no banco
        if company_id:
            db = SessionLocal()
            try:
                notification = Notification(
                    company_id=company_id,
                    type="email",
                    channel="email",
                    title=subject,
                    message=body[:500],  # Primeiros 500 caracteres
                    status="sent",
                    sent_at=datetime.utcnow()
                )
                db.add(notification)
                db.commit()
            finally:
                db.close()
        
        logger.info("Email sent successfully")
        return {"status": "success", "recipients": len(to_emails)}
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(name="send_whatsapp")
def send_whatsapp(
    phone_number: str,
    message: str,
    company_id: str,
    media_url: Optional[str] = None
) -> Dict:
    """
    Envia mensagem WhatsApp via API
    """
    logger.info(f"Sending WhatsApp to {phone_number}")
    
    # TODO: Implementar integração com WhatsApp Business API
    # Por enquanto, apenas registra a tentativa
    
    db = SessionLocal()
    try:
        notification = Notification(
            company_id=company_id,
            type="alert",
            channel="whatsapp",
            title="WhatsApp Alert",
            message=message,
            status="pending",  # Mudar para "sent" quando implementado
            metadata={
                "phone": phone_number,
                "media_url": media_url
            }
        )
        db.add(notification)
        db.commit()
        
        return {
            "status": "pending",
            "message": "WhatsApp integration not yet implemented"
        }
        
    finally:
        db.close()
