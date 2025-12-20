"""API dependencies for FastAPI application."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine
import structlog

from app.database import get_async_session
from app.services.ticket_service import TicketService
from app.services.sla_engine import SLAEngine
from app.services.escalation_service import EscalationService
from app.utils.sla_calculator import SLACalculator

logger = structlog.get_logger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_db_session():
    """Dependency to get database session."""
    async for session in get_async_session():
        yield session


async def get_ticket_service(db_session: AsyncSession = Depends(get_db_session)) -> TicketService:
    """Dependency to get ticket service instance."""
    sla_calculator = SLACalculator()
    return TicketService(sla_calculator)


async def get_sla_engine(
    ticket_service: TicketService = Depends(get_ticket_service),
    db_session: AsyncSession = Depends(get_db_session)
) -> SLAEngine:
    """Dependency to get SLA engine instance."""
    escalation_service = EscalationService()
    return SLAEngine(ticket_service, escalation_service)


async def get_escalation_service() -> EscalationService:
    """Dependency to get escalation service instance."""
    return EscalationService()


# Optional authentication (can be extended for production)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Optional authentication - currently returns a mock user."""
    # In production, implement proper JWT token validation
    return {"user_id": "system", "role": "admin"}

