# SMTP
# ===========================
# backend/app/integrations/notifications/email.py
# ===========================
"""
Email notification service using SMTP
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
import logging
from pathlib import Path
import aiosmtplib
from jinja2 import Template

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails via SMTP
    """
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_tls = settings.SMTP_TLS
        self.from_email = settings.SMTP_FROM_EMAIL or self.smtp_user
        self.from_name = settings.SMTP_FROM_NAME or "WeatherBiz Analytics"
        
        # Email templates
        self.templates = {
            "alert": self._get_alert_template(),
            "report": self._get_report_template(),
            "welcome": self._get_welcome_template(),
            "password_reset": self._get_password_reset_template()
        }
    
    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        template: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send email asynchronously
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = ", ".join(to_emails)
            
            # Use template if specified
            if template and template in self.templates:
                template_obj = Template(self.templates[template])
                html_body = template_obj.render(**(template_data or {}))
                body = self._html_to_text(html_body)
            
            # Add body
            msg.attach(MIMEText(body, "plain"))
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    self._attach_file(msg, attachment)
            
            # Send via aiosmtplib
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                use_tls=self.smtp_tls
            )
            
            logger.info(f"Email sent successfully to {to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def send_email_sync(
        self,
        to_emails: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Send email synchronously (for Celery tasks)
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = ", ".join(to_emails)
            
            msg.attach(MIMEText(body, "plain"))
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            
            if attachments:
                for attachment in attachments:
                    self._attach_file(msg, attachment)
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_emails}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def _attach_file(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """
        Attach file to email
        """
        part = MIMEBase("application", "octet-stream")
        
        if "content" in attachment:
            part.set_payload(attachment["content"])
        elif "filepath" in attachment:
            with open(attachment["filepath"], "rb") as f:
                part.set_payload(f.read())
        
        encoders.encode_base64(part)
        
        filename = attachment.get("filename", "attachment")
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {filename}"
        )
        
        msg.attach(part)
    
    def _html_to_text(self, html: str) -> str:
        """
        Convert HTML to plain text (simplified)
        """
        import re
        # Remove HTML tags
        text = re.sub('<[^<]+?>', '', html)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text
    
    def _get_alert_template(self) -> str:
        """
        Alert email template
        """
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .alert { padding: 20px; border-left: 4px solid #ff9800; background: #fff3e0; }
                .alert.critical { border-left-color: #f44336; background: #ffebee; }
                .footer { margin-top: 30px; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <h2>⚠️ Alerta WeatherBiz</h2>
            <div class="alert {{ 'critical' if severity == 'critical' else '' }}">
                <h3>{{ alert_title }}</h3>
                <p>{{ alert_message }}</p>
                <p><strong>Severidade:</strong> {{ severity }}</p>
                <p><strong>Data/Hora:</strong> {{ datetime }}</p>
                {% if recommendations %}
                <h4>Recomendações:</h4>
                <ul>
                {% for rec in recommendations %}
                    <li>{{ rec }}</li>
                {% endfor %}
                </ul>
                {% endif %}
            </div>
            <div class="footer">
                <p>Este é um email automático do WeatherBiz Analytics.</p>
            </div>
        </body>
        </html>
        """
    
    def _get_report_template(self) -> str:
        """
        Report email template
        """
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; }
                .header { background: #2196F3; color: white; padding: 20px; }
                .content { padding: 20px; }
                .metrics { display: flex; justify-content: space-around; margin: 20px 0; }
                .metric { text-align: center; }
                .metric .value { font-size: 24px; font-weight: bold; color: #2196F3; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Relatório WeatherBiz</h1>
                <p>{{ report_period }}</p>
            </div>
            <div class="content">
                <h2>Resumo Executivo</h2>
                <p>{{ executive_summary }}</p>
                
                <div class="metrics">
                    <div class="metric">
                        <div class="value">R$ {{ total_revenue }}</div>
                        <div>Receita Total</div>
                    </div>
                    <div class="metric">
                        <div class="value">{{ growth_rate }}%</div>
                        <div>Crescimento</div>
                    </div>
                    <div class="metric">
                        <div class="value">{{ weather_impact }}</div>
                        <div>Impacto Climático</div>
                    </div>
                </div>
                
                <p>O relatório completo está anexado a este email.</p>
            </div>
        </body>
        </html>
        """
    
    def _get_welcome_template(self) -> str:
        """
        Welcome email template
        """
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .welcome { text-align: center; padding: 40px; }
                .button { display: inline-block; padding: 12px 24px; background: #4CAF50; color: white; text-decoration: none; border-radius: 4px; }
            </style>
        </head>
        <body>
            <div class="welcome">
                <h1>🎉 Bem-vindo ao WeatherBiz Analytics!</h1>
                <p>Olá {{ user_name }},</p>
                <p>Sua conta foi criada com sucesso!</p>
                <p>Comece a analisar o impacto do clima nas suas vendas.</p>
                <br>
                <a href="{{ login_url }}" class="button">Acessar Plataforma</a>
            </div>
        </body>
        </html>
        """
    
    def _get_password_reset_template(self) -> str:
        """
        Password reset email template
        """
        return """
        <!DOCTYPE html>
        <html>
        <body>
            <h2>Redefinição de Senha</h2>
            <p>Você solicitou a redefinição de senha.</p>
            <p>Clique no link abaixo para criar uma nova senha:</p>
            <a href="{{ reset_url }}">{{ reset_url }}</a>
            <p>Este link expira em 1 hora.</p>
            <p>Se você não solicitou isso, ignore este email.</p>
        </body>
        </html>
        """
