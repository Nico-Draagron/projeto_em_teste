# backend/app/integrations/notifications/slack.py
"""
Slack notification integration
"""

import httpx
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class SlackService:
    """
    Service for sending Slack notifications
    """
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL
        self.client = httpx.AsyncClient(timeout=10.0)
        
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured")
    
    async def send_message(
        self,
        text: str,
        channel: Optional[str] = None,
        username: Optional[str] = "WeatherBiz Bot",
        icon_emoji: Optional[str] = ":chart_with_upwards_trend:",
        attachments: Optional[List[Dict]] = None,
        blocks: Optional[List[Dict]] = None
    ) -> bool:
        """
        Send message to Slack
        """
        if not self.webhook_url:
            logger.warning("Slack webhook not configured")
            return False
        
        try:
            payload = {
                "text": text,
                "username": username,
                "icon_emoji": icon_emoji
            }
            
            if channel:
                payload["channel"] = channel
            
            if attachments:
                payload["attachments"] = attachments
            
            if blocks:
                payload["blocks"] = blocks
            
            response = await self.client.post(
                self.webhook_url,
                json=payload
            )
            
            if response.status_code == 200:
                logger.info("Slack message sent successfully")
                return True
            else:
                logger.error(f"Slack API error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Slack message: {str(e)}")
            return False
    
    async def send_alert(
        self,
        alert_type: str,
        alert_message: str,
        severity: str = "medium",
        details: Optional[Dict] = None
    ) -> bool:
        """
        Send formatted alert to Slack
        """
        # Color based on severity
        color = {
            "low": "#36a64f",      # Green
            "medium": "#ff9800",   # Orange
            "high": "#ff5722",     # Deep Orange
            "critical": "#f44336"  # Red
        }.get(severity, "#808080")
        
        # Emoji based on severity
        emoji = {
            "low": ":information_source:",
            "medium": ":warning:",
            "high": ":exclamation:",
            "critical": ":rotating_light:"
        }.get(severity, ":warning:")
        
        # Build attachment
        attachment = {
            "color": color,
            "fallback": f"{alert_type}: {alert_message}",
            "title": f"{emoji} WeatherBiz Alert",
            "text": alert_message,
            "fields": [
                {
                    "title": "Type",
                    "value": alert_type,
                    "short": True
                },
                {
                    "title": "Severity",
                    "value": severity.upper(),
                    "short": True
                }
            ],
            "footer": "WeatherBiz Analytics",
            "ts": int(datetime.utcnow().timestamp())
        }
        
        # Add additional details if provided
        if details:
            for key, value in details.items():
                attachment["fields"].append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": len(str(value)) < 20
                })
        
        return await self.send_message(
            text=f"Alert: {alert_type}",
            attachments=[attachment]
        )
    
    async def send_report_notification(
        self,
        report_type: str,
        download_url: str,
        metrics: Optional[Dict] = None
    ) -> bool:
        """
        Send report ready notification with metrics
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 {report_type} Report Ready"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Your *{report_type}* report has been generated successfully!"
                }
            }
        ]
        
        # Add metrics if provided
        if metrics:
            fields = []
            for key, value in metrics.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:*\n{value}"
                })
            
            blocks.append({
                "type": "section",
                "fields": fields[:10]  # Slack limits to 10 fields
            })
        
        # Add download button
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📥 Download Report"
                    },
                    "url": download_url,
                    "style": "primary"
                }
            ]
        })
        
        return await self.send_message(
            text=f"{report_type} report is ready",
            blocks=blocks
        )
    
    async def send_daily_summary(
        self,
        company_name: str,
        metrics: Dict[str, Any]
    ) -> bool:
        """
        Send daily summary to Slack
        """
        # Format metrics
        text = f"*Daily Summary for {company_name}*\n\n"
        text += f"📈 *Sales:* R$ {metrics.get('total_sales', 0):,.2f}\n"
        text += f"📦 *Transactions:* {metrics.get('transactions', 0)}\n"
        text += f"🌡️ *Avg Temperature:* {metrics.get('avg_temperature', 0):.1f}°C\n"
        text += f"☔ *Precipitation:* {metrics.get('precipitation', 0):.1f}mm\n"
        
        if metrics.get('weather_impact'):
            impact = metrics['weather_impact']
            if impact > 0:
                text += f"✅ *Weather Impact:* +{impact:.1f}% (positive)\n"
            else:
                text += f"⚠️ *Weather Impact:* {impact:.1f}% (negative)\n"
        
        return await self.send_message(text)
