"""Ticket API endpoints."""

from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_ticket_service, get_current_user
from app.schemas.ticket import (
    TicketCreate,  TicketResponse, TicketListResponse,
    TicketBatchRequest, TicketBatchResponse, TicketFilters
)
from app.services.ticket_service import TicketService
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_200_OK)
async def create_ticket(
    ticket_data: TicketCreate,
    db_session: AsyncSession = Depends(get_db_session),
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: dict = Depends(get_current_user)
):
    """Create a new ticket with SLA calculations."""
    try:
        ticket = await ticket_service.create_ticket(db_session, ticket_data)
        # logger.info(
        #     "Ticket created via API",
        #     ticket_id=str(ticket.id),
        #     external_id=ticket.external_id,
        #     user_id=current_user.get("user_id")
        # )
        return ticket
    except Exception as e:
        # logger.error("Failed to create ticket", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ticket: {str(e)}"
        )



@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: dict = Depends(get_current_user)
):
    """Get ticket by ID with current SLA status and remaining time."""
    try:
        ticket = await ticket_service.get_ticket_by_id(db_session, ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        # logger.info(
        #     "Ticket retrieved",
        #     ticket_id=str(ticket_id),
        #     user_id=current_user.get("user_id")
        # )
        
        return ticket
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve ticket", ticket_id=str(ticket_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve ticket: {str(e)}"
        )



@router.get("/", response_model=TicketListResponse)
async def list_tickets(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Items per page"),
    status: Optional[List[str]] = Query(None, description="Filter by status"),
    db_session: AsyncSession = Depends(get_db_session),
    ticket_service: TicketService = Depends(get_ticket_service),
    current_user: dict = Depends(get_current_user)
):
    """Get tickets with pagination and filtering."""
    try:
        # Build filters
        filters = {}
        if status:
            filters["status"] = status
        # Calculate pagination
        skip = (page - 1) * size
        
        # Get tickets
        tickets, total = await ticket_service.get_tickets(
            db_session, skip=skip, limit=size, filters=filters
        )
        
        # Calculate pagination metadata
        pages = (total + size - 1) // size  # Ceiling division
        
        # logger.info(
        #     "Tickets listed",
        #     page=page,
        #     size=size,
        #     total=total,
        #     user_id=current_user.get("user_id")
        # )
        
        return TicketListResponse(
            tickets=tickets,
            total=total,
            page=page,
            size=size,
            pages=pages
        )
        
    except Exception as e:
        logger.error("Failed to list tickets", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tickets: {str(e)}"
        )

