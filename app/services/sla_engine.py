"""SLA evaluation engine with background processing."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ticket import Ticket, Alert, SLAStatus, EscalationLevel,TicketStatus
from app.services.ticket_service import TicketService
from app.services.escalation_service import EscalationService
from app.config import sla_config, settings
from app.utils.sla_calculator import SLACalculator
import structlog

logger = structlog.get_logger(__name__)


class SLAEngine:
    """Background service for SLA evaluation and alert generation."""
    
    def __init__(self, ticket_service: TicketService, escalation_service: EscalationService):
        self.ticket_service = ticket_service
        self.escalation_service = escalation_service
        self.sla_calculator = SLACalculator()
        self.is_running = False
    
    async def evaluate_all_tickets(self, db: AsyncSession) -> Dict[str, Any]:
        """Evaluate SLA status for all active tickets."""
        start_time = datetime.now(timezone.utc)
        processed_count = 0
        alert_count = 0
        breach_count = 0
        
        try:
            # Get all open tickets that haven't been resolved/closed
            open_tickets_query = select(Ticket).where(
                and_(
                    Ticket.status.not_in([
                        TicketStatus.RESOLVED,
                        TicketStatus.CLOSED,
                        TicketStatus.CANCELLED,
                    ]),
                    Ticket.response_sla_deadline.isnot(None)
                )
            )
            
            result = await db.execute(open_tickets_query)
            tickets = result.scalars().all()
            
            for ticket in tickets:
                processed_count += 1
                
                # Update SLA status for this ticket
                await self._evaluate_ticket_sla(db, ticket)
                
                # Check for alerts and escalations
                alerts_created = await self._check_and_create_alerts(db, ticket)
                alert_count += len(alerts_created)
                
                # Check for breaches
                if await self._check_for_breaches(db, ticket):
                    breach_count += 1
            
            await db.commit()
            
            evaluation_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            logger.info(
                "SLA evaluation completed",
                processed_tickets=processed_count,
                alerts_created=alert_count,
                breaches_detected=breach_count,
                evaluation_time_seconds=evaluation_time
            )
            
            return {
                "processed_tickets": processed_count,
                "alerts_created": alert_count,
                "breaches_detected": breach_count,
                "evaluation_time_seconds": evaluation_time
            }
            
        except Exception as e:
            await db.rollback()
            logger.error("SLA evaluation failed", error=str(e))
            raise
    
    async def _evaluate_ticket_sla(self, db: AsyncSession, ticket: Ticket):
        """Evaluate SLA status for a single ticket."""
        # Update SLA status
        ticket.update_sla_status()
        
        # Check if escalation level needs to be updated based on SLA status
        await self._update_escalation_level(db, ticket)
    
    async def _check_and_create_alerts(self, db: AsyncSession, ticket: Ticket) -> List[Alert]:
        """Check if alerts should be created for a ticket and create them."""
        alerts_created = []
        
        # Get alert thresholds from config
        warning_threshold = sla_config.get_alert_threshold("warning") * 100  # Convert to percentage
        critical_threshold = sla_config.get_alert_threshold("critical") * 100  # Convert to percentage
        
        # Check response SLA
        response_alerts = await self._check_sla_type_alerts(
            db, ticket, "response", warning_threshold, critical_threshold
        )
        alerts_created.extend(response_alerts)
        
        # Check resolution SLA
        resolution_alerts = await self._check_sla_type_alerts(
            db, ticket, "resolution", warning_threshold, critical_threshold
        )
        alerts_created.extend(resolution_alerts)
        
        return alerts_created
    
    async def _check_sla_type_alerts(
        self, 
        db: AsyncSession, 
        ticket: Ticket, 
        sla_type: str, 
        warning_threshold: float, 
        critical_threshold: float
    ) -> List[Alert]:
        """Check alerts for a specific SLA type (response or resolution)."""
        alerts_created = []
        
        # Get current SLA status and remaining time
        if sla_type == "response":
            remaining_minutes = ticket.response_sla_remaining_minutes
            target_minutes = ticket.response_sla_target
            deadline = ticket.response_sla_deadline
            current_status = ticket.response_sla_status
        else:  # resolution
            remaining_minutes = ticket.resolution_sla_remaining_minutes
            target_minutes = ticket.resolution_sla_target
            deadline = ticket.resolution_sla_deadline
            current_status = ticket.resolution_sla_status
        
        # Skip if no SLA target or already breached
        if not target_minutes or current_status == SLAStatus.BREACHED:
            return alerts_created
        
        # Calculate remaining percentage
        remaining_percentage = SLACalculator.calculate_remaining_percentage(remaining_minutes, target_minutes)
        
        # Determine alert type
        alert_type = None
        threshold_percentage = None
        
        if remaining_percentage <= critical_threshold and current_status != SLAStatus.CRITICAL:
            alert_type = "critical"
            threshold_percentage = critical_threshold
        elif remaining_percentage <= warning_threshold and current_status == SLAStatus.COMPLIANT:
            alert_type = "warning"
            threshold_percentage = warning_threshold
        
        # Create alert if needed
        if alert_type:
            # Check if we already have an active alert of this type
            existing_alert = await self._get_active_alert(db, ticket.id, sla_type, alert_type)
            if not existing_alert:
                alert = await self._create_alert(
                    db, ticket, sla_type, alert_type, 
                    threshold_percentage, remaining_minutes, deadline
                )
                alerts_created.append(alert)
                
                # Trigger escalation workflow
                await self.escalation_service.handle_alert(db, ticket, alert)
        
        return alerts_created
    
    async def _check_for_breaches(self, db: AsyncSession, ticket: Ticket) -> bool:
        """Check if SLA has been breached and handle escalation."""
        breach_detected = False
        
        # Check response SLA breach
        if (ticket.response_sla_deadline and 
            ticket.response_sla_status != SLAStatus.BREACHED and
            SLACalculator.is_sla_breached(ticket.response_sla_deadline)):
            
            ticket.response_sla_status = SLAStatus.BREACHED
            breach_detected = True
            
            # Create breach alert
            await self._create_breach_alert(db, ticket, "response")
        
        # Check resolution SLA breach
        if (ticket.resolution_sla_deadline and 
            ticket.resolution_sla_status != SLAStatus.BREACHED and
            SLACalculator.is_sla_breached(ticket.resolution_sla_deadline)):
            
            ticket.resolution_sla_status = SLAStatus.BREACHED
            breach_detected = True
            
            # Create breach alert
            await self._create_breach_alert(db, ticket, "resolution")
        
        # If breach detected, escalate
        if breach_detected:
            await self._escalate_breach(db, ticket)
        
        return breach_detected
    
    async def _create_alert(
        self, 
        db: AsyncSession, 
        ticket: Ticket, 
        sla_type: str, 
        alert_type: str,
        threshold_percentage: float,
        time_remaining_minutes: int,
        deadline: datetime
    ) -> Alert:
        """Create a new alert."""
        alert = Alert(
            ticket_id=ticket.id,
            alert_type=alert_type,
            sla_type=sla_type,
            threshold_percentage=threshold_percentage,
            time_remaining_minutes=time_remaining_minutes,
            deadline=deadline,
            alert_metadata={
                "ticket_external_id": ticket.external_id,
                "priority": ticket.priority.value,
                "customer_tier": ticket.customer_tier.value,
                "escalation_level": ticket.escalation_level.value
            }
        )
        
        db.add(alert)
        await db.flush()  # Get the ID without committing
        
        # logger.info(
        #     "Alert created",
        #     alert_id=str(alert.id),
        #     ticket_id=str(ticket.id),
        #     sla_type=sla_type,
        #     alert_type=alert_type,
        #     threshold_percentage=threshold_percentage
        # )
        
        return alert
    
    async def _create_breach_alert(self, db: AsyncSession, ticket: Ticket, sla_type: str):
        """Create a breach alert."""
        alert = Alert(
            ticket_id=ticket.id,
            alert_type="breached",
            sla_type=sla_type,
            threshold_percentage=0.0,
            time_remaining_minutes=0,
            deadline=datetime.now(timezone.utc),  # Already breached
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
        
        logger.warning(
            "SLA breach detected",
            alert_id=str(alert.id),
            ticket_id=str(ticket.id),
            sla_type=sla_type
        )
    
    async def _get_active_alert(
        self, 
        db: AsyncSession, 
        ticket_id: UUID, 
        sla_type: str, 
        alert_type: str
    ) -> Optional[Alert]:
        """Check if an active alert already exists for this ticket/sla_type/alert_type."""
        result = await db.execute(
            select(Alert).where(
                and_(
                    Alert.ticket_id == ticket_id,
                    Alert.sla_type == sla_type,
                    Alert.alert_type == alert_type,
                    Alert.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _update_escalation_level(self, db: AsyncSession, ticket: Ticket):
        """Update escalation level based on current SLA status."""
        current_level = ticket.escalation_level
        
        # Determine new escalation level based on SLA status
        new_level = EscalationLevel.LEVEL_0  # Default
        
        # Response SLA breaches get higher priority escalation
        if ticket.response_sla_status == SLAStatus.BREACHED:
            new_level = EscalationLevel.LEVEL_4
        elif ticket.response_sla_status == SLAStatus.CRITICAL:
            new_level = EscalationLevel.LEVEL_3
        elif ticket.response_sla_status == SLAStatus.WARNING:
            new_level = EscalationLevel.LEVEL_1
        
        # Resolution SLA escalations
        elif ticket.resolution_sla_status == SLAStatus.BREACHED:
            new_level = EscalationLevel.LEVEL_4
        elif ticket.resolution_sla_status == SLAStatus.CRITICAL:
            new_level = EscalationLevel.LEVEL_2
        
        # Update escalation level if changed
        if new_level != current_level:
            ticket.escalation_level = new_level
            ticket.escalation_count += 1
            ticket.last_escalation_at = datetime.now(timezone.utc)
            
            # logger.info(
            #     "Escalation level updated",
            #     ticket_id=str(ticket.id),
            #     old_level=current_level.value,
            #     new_level=new_level.value
            # )
    
    async def _escalate_breach(self, db: AsyncSession, ticket: Ticket):
        """Handle escalation for SLA breach."""
        # Force maximum escalation level for breaches
        ticket.escalation_level = EscalationLevel.LEVEL_4
        ticket.escalation_count += 1
        ticket.last_escalation_at = datetime.now(timezone.utc)
        
        logger.critical(
            "SLA breach escalation triggered",
            ticket_id=str(ticket.id),
            external_id=ticket.external_id,
            priority=ticket.priority.value
        )
    
    async def get_sla_metrics(self, db: AsyncSession) -> Dict[str, Any]:
        """Get SLA metrics for dashboard."""
        # Get counts by SLA status
        response_status_counts = await self._get_status_counts(db, "response")
        resolution_status_counts = await self._get_status_counts(db, "resolution")
        
        # Get escalation counts
        escalation_counts = await self._get_escalation_counts(db)
        
        # Get breach counts
        breach_counts = await self._get_breach_counts(db)
        
        return {
            "response_sla_status": response_status_counts,
            "resolution_sla_status": resolution_status_counts,
            "escalation_levels": escalation_counts,
            "breaches": breach_counts,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def _get_status_counts(self, db: AsyncSession, sla_type: str) -> Dict[str, int]:
        """Get counts of tickets by SLA status for a specific SLA type."""
        if sla_type == "response":
            status_field = Ticket.response_sla_status
        else:
            status_field = Ticket.resolution_sla_status
        
        result = await db.execute(
            select(status_field, func.count(Ticket.id))
            .group_by(status_field)
        )
        
        counts = {}
        for status, count in result:
            counts[status.value if status else "unknown"] = count
        
        return counts
    
    async def _get_escalation_counts(self, db: AsyncSession) -> Dict[str, int]:
        """Get counts of tickets by escalation level."""
        result = await db.execute(
            select(Ticket.escalation_level, func.count(Ticket.id))
            .group_by(Ticket.escalation_level)
        )
        
        counts = {}
        for level, count in result:
            counts[f"level_{level.value}"] = count
        
        return counts
    
    async def _get_breach_counts(self, db: AsyncSession) -> Dict[str, int]:
        """Get counts of breached SLAs."""
        response_breaches = await db.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.response_sla_status == SLAStatus.BREACHED
            )
        )
        
        resolution_breaches = await db.scalar(
            select(func.count(Ticket.id)).where(
                Ticket.resolution_sla_status == SLAStatus.BREACHED
            )
        )
        
        return {
            "response_breaches": response_breaches or 0,
            "resolution_breaches": resolution_breaches or 0,
            "total_breaches": (response_breaches or 0) + (resolution_breaches or 0)
        }
