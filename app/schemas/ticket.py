"""Pydantic schemas for ticket operations."""

from datetime import datetime,timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum as PyEnum

from pydantic import BaseModel, Field, validator

# Import enums from models to avoid duplication
from app.models.ticket import (
    TicketStatus, Priority, CustomerTier, SLAStatus, EscalationLevel
)


class TicketBase(BaseModel):
    """Base ticket schema with common fields."""
    
    external_id: str = Field(..., description="External system ticket ID")
    title: str = Field(..., max_length=500, description="Ticket title")
    description: Optional[str] = Field(None, description="Ticket description")
    priority: Priority = Field(..., description="Ticket priority")
    customer_tier: CustomerTier = Field(..., description="Customer tier")
    status: TicketStatus = Field(default=TicketStatus.OPEN, description="Ticket status")
    assigned_to: Optional[str] = Field(None, description="Assigned agent")
    department: Optional[str] = Field(None, description="Department")
    tags: List[str] = Field(default_factory=list, description="Ticket tags")
    ticket_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TicketCreate(TicketBase):
    """Schema for creating a new ticket."""
    
    created_at: Optional[datetime] = Field(None, description="Ticket creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    
    @validator('created_at', pre=True)
    def validate_created_at(cls, v):
        """Validate and set created_at."""
        if v is None:
            return datetime.now(timezone.utc)
        return v
    
    @validator('updated_at', pre=True)
    def validate_updated_at(cls, v):
        """Validate and set updated_at."""
        if v is None:
            return datetime.now(timezone.utc)
        return v


class TicketResponse(BaseModel):
    """Schema for ticket response with SLA information."""
    
    id: UUID
    external_id: str
    title: str
    description: Optional[str]
    priority: Priority
    customer_tier: CustomerTier
    status: TicketStatus
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    # SLA information
    response_sla_target: Optional[int] = None
    resolution_sla_target: Optional[int] = None
    response_sla_deadline: Optional[datetime] = None
    resolution_sla_deadline: Optional[datetime] = None
    
    # Current SLA status
    response_sla_status: SLAStatus
    resolution_sla_status: SLAStatus
    response_sla_remaining_minutes: int
    resolution_sla_remaining_minutes: int
    
    # Escalation information
    escalation_level: EscalationLevel
    escalation_count: int
    last_escalation_at: Optional[datetime] = None
    
    # Additional fields
    assigned_to: Optional[str]
    department: Optional[str]
    tags: List[str]
    ticket_metadata: Dict[str, Any]
    
    class Config:
        from_attributes = True


class TicketSLASummary(BaseModel):
    """SLA summary information for a ticket."""
    
    response: Dict[str, Any] = Field(..., description="Response SLA information")
    resolution: Dict[str, Any] = Field(..., description="Resolution SLA information")
    escalation_level: int
    escalation_count: int


class TicketStatusHistoryItem(BaseModel):
    """Schema for ticket status history item."""
    
    id: UUID
    from_status: Optional[TicketStatus]
    to_status: TicketStatus
    changed_at: datetime
    changed_by: Optional[str]
    reason: Optional[str]
    
    class Config:
        from_attributes = True


class TicketListResponse(BaseModel):
    """Schema for paginated ticket list response."""
    
    tickets: List[TicketResponse]
    total: int
    page: int
    size: int
    pages: int


class TicketBatchRequest(BaseModel):
    """Schema for batch ticket creation/update."""
    
    tickets: List[TicketCreate] = Field(..., min_items=1, max_items=1000)
    
    @validator('tickets')
    def validate_ticket_batch(cls, v):
        """Validate ticket batch."""
        if len(v) == 0:
            raise ValueError("At least one ticket required")
        
        # Check for duplicate external_ids in batch
        external_ids = [ticket.external_id for ticket in v]
        if len(external_ids) != len(set(external_ids)):
            raise ValueError("Duplicate external_ids in batch")
        
        return v


class TicketBatchResponse(BaseModel):
    """Schema for batch operation response."""
    
    successful: int = Field(..., description="Number of successfully processed tickets")
    failed: int = Field(..., description="Number of failed tickets")
    errors: List[str] = Field(default_factory=list, description="List of error messages")


class TicketEvent(BaseModel):
    """Schema for ticket events from external systems."""
    
    event_type: str = Field(..., description="Event type: created, updated, status_changed")
    ticket: TicketCreate = Field(..., description="Ticket data")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing")


class TicketFilters(BaseModel):
    """Schema for filtering tickets in queries."""
    
    status: Optional[List[TicketStatus]] = Field(None, description="Filter by status")
    priority: Optional[List[Priority]] = Field(None, description="Filter by priority")
    customer_tier: Optional[List[CustomerTier]] = Field(None, description="Filter by customer tier")
    escalation_level: Optional[List[int]] = Field(None, description="Filter by escalation level")
    response_sla_status: Optional[List[SLAStatus]] = Field(None, description="Filter by response SLA status")
    resolution_sla_status: Optional[List[SLAStatus]] = Field(None, description="Filter by resolution SLA status")
    assigned_to: Optional[List[str]] = Field(None, description="Filter by assigned agent")
    department: Optional[List[str]] = Field(None, description="Filter by department")
    created_from: Optional[datetime] = Field(None, description="Filter by creation date (from)")
    created_to: Optional[datetime] = Field(None, description="Filter by creation date (to)")
    search: Optional[str] = Field(None, description="Search in title and description")
