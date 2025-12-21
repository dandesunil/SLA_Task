"""Business logic for ticket operations."""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone,timedelta
from uuid import UUID

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ticket import (
    Ticket, TicketStatusHistory, Alert, SLAStatus, 
    TicketStatus, Priority, CustomerTier, EscalationLevel
)
from app.schemas.ticket import TicketCreate, TicketResponse
from app.config import sla_config
from app.utils.sla_calculator import SLACalculator
import structlog

logger = structlog.get_logger(__name__)


class TicketService:
    """Service for ticket business logic operations."""
    
    def __init__(self, sla_calculator: SLACalculator):
        self.sla_calculator = sla_calculator
    
    async def create_ticket(self, db: AsyncSession, ticket_data: TicketCreate) -> Ticket:
        """Create a new ticket with SLA calculations."""
        # Calculate SLA targets based on priority and customer tier
        response_target = sla_config.get_sla_target("response", ticket_data.priority.value, ticket_data.customer_tier.value)
        resolution_target = sla_config.get_sla_target("resolution", ticket_data.priority.value, ticket_data.customer_tier.value)
        
        # Calculate deadlines
        now = datetime.now(timezone.utc)
        response_deadline = now + timedelta(minutes=response_target)
        resolution_deadline = now + timedelta(minutes=resolution_target)
        
        # Create ticket
        ticket = Ticket(
            external_id=ticket_data.external_id,
            title=ticket_data.title,
            description=ticket_data.description,
            priority=Priority(ticket_data.priority.value),
            customer_tier=CustomerTier(ticket_data.customer_tier.value),
            status=TicketStatus(ticket_data.status.value),
            created_at=ticket_data.created_at,
            updated_at=ticket_data.updated_at,
            response_sla_target=response_target,
            resolution_sla_target=resolution_target,
            response_sla_deadline=response_deadline,
            resolution_sla_deadline=resolution_deadline,
            assigned_to=ticket_data.assigned_to,
            department=ticket_data.department,
            tags=ticket_data.tags,
            ticket_metadata=ticket_data.ticket_metadata
        )
        
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
        
        # Create initial status history entry
        await self._create_status_history(db, ticket, None, ticket.status, "System", "Ticket created")
        
        # logger.info(
        #     "Ticket created", 
        #     ticket_id=str(ticket.id), 
        #     external_id=ticket.external_id,
        #     priority=ticket.priority.value,
        #     customer_tier=ticket.customer_tier.value
        # )
        
        return ticket
  
    async def get_ticket_by_id(self, db: AsyncSession, ticket_id: UUID) -> Optional[Ticket]:
        """Get ticket by ID with all related data."""
        result = await db.execute(
            select(Ticket)
            .options(
                selectinload(Ticket.status_history),
                selectinload(Ticket.alerts)
            )
            .where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()
    
    
    async def get_tickets(
        self, 
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Ticket], int]:
        """Get tickets with pagination and filtering."""
        try:
            query = select(Ticket)
            
            # Apply filters
            if filters:
                query = self._apply_filters(query, filters)
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar()
            
            # Apply pagination and ordering
            query = query.order_by(desc(Ticket.created_at)).offset(skip).limit(limit)
            
            # Execute query
            result = await db.execute(query)
            tickets = result.scalars().all()
            
            return tickets, total
        except Exception as e:
            raise Exception(f"Error retrieving tickets: {str(e)}")
    
    
    async def _create_status_history(
        self, 
        db: AsyncSession, 
        ticket: Ticket, 
        from_status: Optional[TicketStatus], 
        to_status: TicketStatus, 
        changed_by: str, 
        reason: str
    ):
        """Create a status history entry."""
        history = TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            reason=reason
        )
        db.add(history)
        await db.commit()
    
    async def _recalculate_sla_targets(self, db: AsyncSession, ticket: Ticket):
        """Recalculate SLA targets when priority or customer tier changes."""
        response_target = sla_config.get_sla_target("response", ticket.priority.value, ticket.customer_tier.value)
        resolution_target = sla_config.get_sla_target("resolution", ticket.priority.value, ticket.customer_tier.value)
        
        now = datetime.now(timezone.utc)
        ticket.response_sla_target = response_target
        ticket.resolution_sla_target = resolution_target
        ticket.response_sla_deadline = now + timedelta(minutes=response_target)
        ticket.resolution_sla_deadline = now + timedelta(minutes=resolution_target)
        
        # Update SLA status
        ticket.update_sla_status()
    
    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to the query."""
        # This is a simplified version - in practice, you'd want more sophisticated filtering
        if "status" in filters and filters["status"]:
            statuses = [
                TicketStatus[s.upper()] if isinstance(s, str) else s
                for s in filters["status"]
            ]
            query = query.where(Ticket.status.in_(statuses))
            
        if "priority" in filters and filters["priority"]:
            query = query.where(Ticket.priority.in_(filters["priority"]))
        
        if "customer_tier" in filters and filters["customer_tier"]:
            query = query.where(Ticket.customer_tier.in_(filters["customer_tier"]))
        
        if "escalation_level" in filters and filters["escalation_level"]:
            query = query.where(Ticket.escalation_level.in_(filters["escalation_level"]))
        
        if "response_sla_status" in filters and filters["response_sla_status"]:
            query = query.where(Ticket.response_sla_status.in_(filters["response_sla_status"]))
        
        if "resolution_sla_status" in filters and filters["resolution_sla_status"]:
            query = query.where(Ticket.resolution_sla_status.in_(filters["resolution_sla_status"]))
        
        if "assigned_to" in filters and filters["assigned_to"]:
            query = query.where(Ticket.assigned_to.in_(filters["assigned_to"]))
        
        if "department" in filters and filters["department"]:
            query = query.where(Ticket.department.in_(filters["department"]))
        
        if "created_from" in filters and filters["created_from"]:
            query = query.where(Ticket.created_at >= filters["created_from"])
        
        if "created_to" in filters and filters["created_to"]:
            query = query.where(Ticket.created_at <= filters["created_to"])
        
        if "search" in filters and filters["search"]:
            search_term = f"%{filters['search']}%"
            query = query.where(
                or_(
                    Ticket.title.ilike(search_term),
                    Ticket.description.ilike(search_term)
                )
            )
        
        return query
