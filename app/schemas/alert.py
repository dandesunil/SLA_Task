"""Alert schemas for API responses."""

from datetime import datetime,timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum as PyEnum

from pydantic import BaseModel, Field

# Import enums from models to avoid duplication
from app.models.ticket import SLAStatus


class AlertType(PyEnum):
    """Alert type enumeration."""
    WARNING = "warning"
    CRITICAL = "critical"
    BREACHED = "breached"


class SLAType(PyEnum):
    """SLA type enumeration."""
    RESPONSE = "response"
    RESOLUTION = "resolution"


class AlertBase(BaseModel):
    """Base alert schema."""
    
    alert_type: AlertType = Field(..., description="Type of alert")
    sla_type: SLAType = Field(..., description="Type of SLA (response or resolution)")
    threshold_percentage: float = Field(..., description="Percentage of time remaining when alert triggered")
    time_remaining_minutes: int = Field(..., description="Minutes remaining when alert triggered")
    alert_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional alert metadata")


class AlertResponse(AlertBase):
    """Schema for alert response."""
    
    id: UUID
    ticket_id: UUID
    is_active: bool
    is_sent: bool
    sent_at: Optional[datetime] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """Schema for paginated alert list response."""
    
    alerts: List[AlertResponse]
    total: int
    page: int
    size: int
    pages: int


class AlertCreate(BaseModel):
    """Schema for creating an alert."""
    
    ticket_id: UUID = Field(..., description="Ticket ID this alert is for")
    alert_type: AlertType = Field(..., description="Type of alert")
    sla_type: SLAType = Field(..., description="Type of SLA")
    threshold_percentage: float = Field(..., description="Percentage threshold")
    time_remaining_minutes: int = Field(..., description="Time remaining in minutes")
    alert_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AlertUpdate(BaseModel):
    """Schema for updating an alert."""
    
    is_active: Optional[bool] = None
    is_sent: Optional[bool] = None
    resolved_at: Optional[datetime] = None
    alert_metadata: Optional[Dict[str, Any]] = None
