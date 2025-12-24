"""Escalation service for handling SLA escalations and notifications."""

from datetime import datetime,timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import structlog

from app.models.ticket import Ticket, Alert, EscalationLevel
from app.config import sla_config
from app.utils.sla_calculator import SLACalculator

logger = structlog.get_logger(__name__)


class EscalationService:
    """Service for handling escalations and notifications."""
    
    def __init__(self):
        self.sla_calculator = SLACalculator()
    
    async def handle_alert(self, db: AsyncSession, ticket: Ticket, alert: Alert):
        """Handle alert escalation workflow."""
        try:
            # Update ticket escalation level
            await self._update_escalation_level(db, ticket, alert)
            
            # Send notifications
            await self._send_notifications(db, ticket, alert)
            
            # logger.info(
            #     "Alert escalation handled",
            #     ticket_id=str(ticket.id),
            #     alert_id=str(alert.id),
            #     alert_type=alert.alert_type,
            #     escalation_level=ticket.escalation_level.value
            # )
            
        except Exception as e:
            logger.error(
                "Alert escalation failed",
                ticket_id=str(ticket.id),
                alert_id=str(alert.id),
                error=str(e)
            )
            raise
    
    async def handle_breach(self, db: AsyncSession, ticket: Ticket, sla_type: str):
        """Handle SLA breach escalation."""
        try:
            # Force maximum escalation for breaches
            ticket.escalation_level = EscalationLevel.LEVEL_4
            ticket.escalation_count += 1
            ticket.last_escalation_at = datetime.now(timezone.utc)
            
            # Create breach notification
            breach_alert = await self._create_breach_notification(db, ticket, sla_type)
            
            # Send critical notifications
            await self._send_critical_notifications(db, ticket, breach_alert)
            
            logger.critical(
                "SLA breach escalation handled",
                ticket_id=str(ticket.id),
                sla_type=sla_type,
                escalation_level=ticket.escalation_level.value
            )
            
        except Exception as e:
            logger.error(
                "SLA breach escalation failed",
                ticket_id=str(ticket.id),
                sla_type=sla_type,
                error=str(e)
            )
            raise
    
    async def _update_escalation_level(self, db: AsyncSession, ticket: Ticket, alert: Alert):
        """Update escalation level based on alert severity."""
        current_level = ticket.escalation_level
        
        # Determine escalation level based on alert type
        if alert.alert_type == "critical":
            new_level = EscalationLevel.LEVEL_3
        elif alert.alert_type == "warning":
            new_level = EscalationLevel.LEVEL_1
        else:
            return  # No escalation for other alert types
        
        # Only escalate, never de-escalate
        if new_level.value > current_level.value:
            ticket.escalation_level = new_level
            ticket.escalation_count += 1
            ticket.last_escalation_at = datetime.now(timezone.utc)
            
            # logger.info(
            #     "Escalation level updated",
            #     ticket_id=str(ticket.id),
            #     old_level=current_level.value,
            #     new_level=new_level.value,
            #     reason=f"{alert.alert_type} alert"
            # )
    
    async def _send_notifications(self, db: AsyncSession, ticket: Ticket, alert: Alert):
        """Send notifications based on escalation level."""
        # Get webhook configuration
        webhook_config = sla_config.get_webhook_config("slack")
        webhook_url = webhook_config.get("slack_webhook_url")
        
        if not webhook_url:
            logger.warning("Slack webhook URL not configured, skipping notifications")
            return
        
        # Determine channel based on severity
        channel = webhook_config.get("channels", {}).get("general", "#sla-alerts")
        if alert.alert_type == "critical":
            channel = webhook_config.get("channels", {}).get("critical", "#sla-critical")
        
        # Send Slack notification
        await self._send_slack_notification(webhook_url, channel, ticket, alert)
        
        # Mark alert as sent
        alert.is_sent = True
        alert.sent_at = datetime.now(timezone.utc)
        
        await db.flush()
    
    async def _send_critical_notifications(self, db: AsyncSession, ticket: Ticket, alert: Alert):
        """Send critical breach notifications."""
        webhook_config = sla_config.get_webhook_config("slack")
        webhook_url = webhook_config.get("slack_webhook_url")
        
        if not webhook_url:
            logger.warning("Slack webhook URL not configured, skipping critical notifications")
            return
        
        # Send to critical channel
        channel = webhook_config.get("channels", {}).get("critical", "#sla-critical")
        await self._send_slack_notification(webhook_url, channel, ticket, alert)
        
        # Mark alert as sent
        alert.is_sent = True
        alert.sent_at = datetime.now(timezone.utc)
        
        await db.flush()
    
    async def _send_slack_notification(self, webhook_url: str, channel: str, ticket: Ticket, alert: Alert):
        """Send notification to Slack webhook."""
        try:
            # Format message based on alert type
            message = self._format_slack_message(ticket, alert)
            
            payload = {
                "channel": channel,
                "text": message["text"],
                "attachments": message["attachments"]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
            
            # logger.info(
            #     "Slack notification sent",
            #     ticket_id=str(ticket.id),
            #     channel=channel,
            #     alert_type=alert.alert_type
            # )
            
        except httpx.RequestError as e:
            logger.error(
                "Failed to send Slack notification",
                ticket_id=str(ticket.id),
                error=str(e)
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Slack API error",
                ticket_id=str(ticket.id),
                status_code=e.response.status_code,
                error=str(e)
            )
    
    def _format_slack_message(self, ticket: Ticket, alert: Alert) -> Dict[str, Any]:
        """Format Slack message based on alert type and ticket details."""
        now = datetime.now(timezone.utc)
        
        if alert.alert_type == "breached":
            return self._format_breach_message(ticket, alert, now)
        elif alert.alert_type == "critical":
            return self._format_critical_message(ticket, alert, now)
        else:
            return self._format_warning_message(ticket, alert, now)
    
    def _format_breach_message(self, ticket: Ticket, alert: Alert, now: datetime) -> Dict[str, Any]:
        """Format breach notification message."""
        escalation_level = sla_config.get_escalation_levels().get(ticket.escalation_level.value, "Unknown")
        
        text = f"🚨 SLA BREACH ALERT - {ticket.priority.value} Priority Ticket"
        
        attachments = [{
            "color": "danger",
            "fields": [
                {
                    "title": "Ticket ID",
                    "value": ticket.external_id,
                    "short": True
                },
                {
                    "title": "Title",
                    "value": ticket.title[:50] + "..." if len(ticket.title) > 50 else ticket.title,
                    "short": True
                },
                {
                    "title": "SLA Type",
                    "value": alert.sla_type.title(),
                    "short": True
                },
                {
                    "title": "Customer Tier",
                    "value": ticket.customer_tier.title(),
                    "short": True
                },
                {
                    "title": "Escalation Level",
                    "value": f"Level {ticket.escalation_level.value} - {escalation_level}",
                    "short": True
                },
                {
                    "title": "Assigned To",
                    "value": ticket.assigned_to or "Unassigned",
                    "short": True
                },
                {
                    "title": "Created",
                    "value": ticket.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                    "short": True
                },
                {
                    "title": "Breach Time",
                    "value": now.strftime("%Y-%m-%d %H:%M UTC"),
                    "short": True
                }
            ],
            "footer": "SLA Service",
            "ts": int(now.timestamp())
        }]
        
        return {"text": text, "attachments": attachments}
    
    def _format_critical_message(self, ticket: Ticket, alert: Alert, now: datetime) -> Dict[str, Any]:
        """Format critical alert message."""
        escalation_level = sla_config.get_escalation_levels().get(ticket.escalation_level.value, "Unknown")
        remaining_time = SLACalculator.format_duration(alert.time_remaining_minutes)
        
        text = f"🔴 CRITICAL SLA ALERT - {ticket.priority.value} Priority Ticket"
        
        attachments = [{
            "color": "warning",
            "fields": [
                {
                    "title": "Ticket ID",
                    "value": ticket.external_id,
                    "short": True
                },
                {
                    "title": "Title",
                    "value": ticket.title[:50] + "..." if len(ticket.title) > 50 else ticket.title,
                    "short": True
                },
                {
                    "title": "SLA Type",
                    "value": alert.sla_type.title(),
                    "short": True
                },
                {
                    "title": "Time Remaining",
                    "value": f"{remaining_time} ({alert.threshold_percentage:.1f}%)",
                    "short": True
                },
                {
                    "title": "Customer Tier",
                    "value": ticket.customer_tier.title(),
                    "short": True
                },
                {
                    "title": "Escalation Level",
                    "value": f"Level {ticket.escalation_level.value} - {escalation_level}",
                    "short": True
                },
                {
                    "title": "Assigned To",
                    "value": ticket.assigned_to or "Unassigned",
                    "short": True
                },
                {
                    "title": "Created",
                    "value": ticket.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                    "short": True
                }
            ],
            "footer": "SLA Service",
            "ts": int(now.timestamp())
        }]
        
        return {"text": text, "attachments": attachments}
    
    def _format_warning_message(self, ticket: Ticket, alert: Alert, now: datetime) -> Dict[str, Any]:
        """Format warning alert message."""
        escalation_level = sla_config.get_escalation_levels().get(ticket.escalation_level.value, "Unknown")
        remaining_time = SLACalculator.format_duration(alert.time_remaining_minutes)
        
        text = f"⚠️ SLA WARNING - {ticket.priority.value} Priority Ticket"
        
        attachments = [{
            "color": "#ffaa00",
            "fields": [
                {
                    "title": "Ticket ID",
                    "value": ticket.external_id,
                    "short": True
                },
                {
                    "title": "Title",
                    "value": ticket.title[:50] + "..." if len(ticket.title) > 50 else ticket.title,
                    "short": True
                },
                {
                    "title": "SLA Type",
                    "value": alert.sla_type.title(),
                    "short": True
                },
                {
                    "title": "Time Remaining",
                    "value": f"{remaining_time} ({alert.threshold_percentage:.1f}%)",
                    "short": True
                },
                {
                    "title": "Customer Tier",
                    "value": ticket.customer_tier.title(),
                    "short": True
                },
                {
                    "title": "Escalation Level",
                    "value": f"Level {ticket.escalation_level.value} - {escalation_level}",
                    "short": True
                },
                {
                    "title": "Assigned To",
                    "value": ticket.assigned_to or "Unassigned",
                    "short": True
                },
                {
                    "title": "Created",
                    "value": ticket.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                    "short": True
                }
            ],
            "footer": "SLA Service",
            "ts": int(now.timestamp())
        }]
        
        return {"text": text, "attachments": attachments}
    
    async def _create_breach_notification(self, db: AsyncSession, ticket: Ticket, sla_type: str):
        """Create a breach notification alert."""
        from app.models.ticket import Alert as AlertModel
        
        alert = AlertModel(
            ticket_id=ticket.id,
            alert_type="breached",
            sla_type=sla_type,
            threshold_percentage=0.0,
            time_remaining_minutes=0,
            deadline=datetime.now(timezone.utc),
            alert_metadata={
                "ticket_external_id": ticket.external_id,
                "priority": ticket.priority.value,
                "customer_tier": ticket.customer_tier.value,
                "escalation_level": ticket.escalation_level.value,
                "breach_timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        db.add(alert)
        await db.flush()
        
        return alert
