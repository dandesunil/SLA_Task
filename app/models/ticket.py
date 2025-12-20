
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Text, 
    Enum, ForeignKey, Index, JSON, Float, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class TicketStatus(PyEnum):
    """Ticket status enumeration."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_CUSTOMER = "PENDING_CUSTOMER"
    PENDING_INTERNAL = "PENDING_INTERNAL"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class Priority(PyEnum):
    """Priority enumeration."""
    P0 = "P0"  # Critical - 15 minutes response
    P1 = "P1"  # High - 1 hour response
    P2 = "P2"  # Medium - 4 hours response
    P3 = "P3"  # Low - 8 hours response


class CustomerTier(PyEnum):
    """Customer tier enumeration."""
    ENTERPRISE = "ENTERPRISE"
    PREMIUM = "PREMIUM"
    STANDARD = "STANDARD"
    BASIC="BASIC"


class SLAStatus(PyEnum):
    """SLA status enumeration."""
    COMPLIANT = "COMPLIANT"
    WARNING = "WARNING"  # ≤ 15% time remaining
    CRITICAL = "CRITICAL"  # ≤ 5% time remaining
    BREACHED = "BREACHED"  # Time exceeded
    PAUSED = "PAUSED"  # SLA clock paused (e.g., waiting for customer)


class EscalationLevel(PyEnum):
    """Escalation level enumeration."""
    LEVEL_0 = 0  # No escalation
    LEVEL_1 = 1  # Team lead
    LEVEL_2 = 2  # Manager
    LEVEL_3 = 3  # Director
    LEVEL_4 = 4  # VP


class Ticket(Base):
    """Ticket model with SLA tracking."""
    
    __tablename__ = "tickets"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid())
    
    # Core ticket fields
    external_id = Column(String(255), nullable=False, index=True, comment="External system ticket ID")
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    # SLA tracking fields
    priority = Column(Enum(Priority), nullable=False, index=True)
    customer_tier = Column(Enum(CustomerTier,name="customertier",create_type=False), nullable=False, index=True)
    status = Column(Enum(TicketStatus,name="ticketstatus",native_enum=True,create_type=False), default=TicketStatus.OPEN, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    
    # SLA fields
    response_sla_target = Column(Integer, comment="Response SLA target in minutes")
    resolution_sla_target = Column(Integer, comment="Resolution SLA target in minutes")
    response_sla_deadline = Column(DateTime(timezone=True), comment="Response SLA deadline")
    resolution_sla_deadline = Column(DateTime(timezone=True), comment="Resolution SLA deadline")
    
    # SLA status tracking
    response_sla_status = Column(Enum(SLAStatus), default=SLAStatus.COMPLIANT)
    resolution_sla_status = Column(Enum(SLAStatus), default=SLAStatus.COMPLIANT)
    response_sla_remaining_minutes = Column(Integer, default=0)
    resolution_sla_remaining_minutes = Column(Integer, default=0)
    
    # Escalation tracking
    escalation_level = Column(Enum(EscalationLevel,name="escalationlevel",create_type=False), default=EscalationLevel.LEVEL_0, index=True)
    last_escalation_at = Column(DateTime(timezone=True))
    escalation_count = Column(Integer, default=0)
    
    # Additional metadata
    assigned_to = Column(String(255))
    department = Column(String(100))
    tags = Column(JSON, default=list)
    ticket_metadata = Column(JSON, default=dict)
    
    # Relationships
    status_history = relationship("TicketStatusHistory", back_populates="ticket", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="ticket", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_ticket_sla_status', 'response_sla_status', 'resolution_sla_status'),
        Index('idx_ticket_deadlines', 'response_sla_deadline', 'resolution_sla_deadline'),
        Index('idx_ticket_active', 'status', 'created_at'),
        UniqueConstraint('external_id', name='uq_ticket_external_id')
    )
    
    def calculate_sla_remaining_minutes(self, sla_type: str) -> int:
        """Calculate remaining SLA time in minutes."""
        if sla_type == "response":
            if not self.response_sla_deadline:
                return 0
            remaining = self.response_sla_deadline - datetime.now(timezone.utc)
            return max(0, int(remaining.total_seconds() / 60))
        
        elif sla_type == "resolution":
            if not self.resolution_sla_deadline:
                return 0
            remaining = self.resolution_sla_deadline - datetime.now(timezone.utc)
            return max(0, int(remaining.total_seconds() / 60))
        
        return 0
    
    def update_sla_status(self):
        """Update SLA status based on current time and deadlines."""
        now = datetime.now(timezone.utc)
        
        # Update response SLA status
        if self.response_sla_deadline:
            remaining_delta = self.response_sla_deadline - now
            remaining_minutes = max(0, int(remaining_delta.total_seconds() / 60))
            self.response_sla_remaining_minutes = remaining_minutes
            
            if remaining_delta.total_seconds() <= 0:
                self.response_sla_status = SLAStatus.BREACHED
            elif remaining_minutes <= int(self.response_sla_target * 0.05):  # ≤ 5%
                self.response_sla_status = SLAStatus.CRITICAL
            elif remaining_minutes <= int(self.response_sla_target * 0.15):  # ≤ 15%
                self.response_sla_status = SLAStatus.WARNING
            else:
                self.response_sla_status = SLAStatus.COMPLIANT
        else:
            self.response_sla_status = SLAStatus.PAUSED
            self.response_sla_remaining_minutes = 0
        
        # Update resolution SLA status
        if self.resolution_sla_deadline:
            remaining_delta = self.resolution_sla_deadline - now
            remaining_minutes = max(0, int(remaining_delta.total_seconds() / 60))
            self.resolution_sla_remaining_minutes = remaining_minutes
            
            if remaining_delta.total_seconds() <= 0:
                self.resolution_sla_status = SLAStatus.BREACHED
            elif remaining_minutes <= int(self.resolution_sla_target * 0.05):  # ≤ 5%
                self.resolution_sla_status = SLAStatus.CRITICAL
            elif remaining_minutes <= int(self.resolution_sla_target * 0.15):  # ≤ 15%
                self.resolution_sla_status = SLAStatus.WARNING
            else:
                self.resolution_sla_status = SLAStatus.COMPLIANT
        else:
            self.resolution_sla_status = SLAStatus.PAUSED
            self.resolution_sla_remaining_minutes = 0
    
    def get_sla_summary(self) -> Dict[str, Any]:
        """Get comprehensive SLA summary for API responses."""
        self.update_sla_status()
        
        return {
            "response": {
                "status": self.response_sla_status.value,
                "target_minutes": self.response_sla_target,
                "deadline": self.response_sla_deadline.isoformat() if self.response_sla_deadline else None,
                "remaining_minutes": self.response_sla_remaining_minutes,
                "remaining_percentage": (
                    (self.response_sla_remaining_minutes / self.response_sla_target * 100)
                    if self.response_sla_target else 0
                )
            },
            "resolution": {
                "status": self.resolution_sla_status.value,
                "target_minutes": self.resolution_sla_target,
                "deadline": self.resolution_sla_deadline.isoformat() if self.resolution_sla_deadline else None,
                "remaining_minutes": self.resolution_sla_remaining_minutes,
                "remaining_percentage": (
                    (self.resolution_sla_remaining_minutes / self.resolution_sla_target * 100)
                    if self.resolution_sla_target else 0
                )
            },
            "escalation_level": self.escalation_level.value,
            "escalation_count": self.escalation_count
        }


class TicketStatusHistory(Base):
    """Track ticket status changes over time."""
    
    __tablename__ = "ticket_status_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid())
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    
    # Status change details
    from_status = Column(Enum(TicketStatus))
    to_status = Column(Enum(TicketStatus), nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    
    # Change metadata
    changed_by = Column(String(255))
    reason = Column(Text)
    ticket_status_metadata = Column(JSON, default=dict)
    
    # Relationships
    ticket = relationship("Ticket", back_populates="status_history")
    
    # Indexes
    __table_args__ = (
        Index('idx_status_history_ticket', 'ticket_id', 'changed_at'),
    )


class Alert(Base):
    """Alert model for SLA escalations."""
    
    __tablename__ = "alerts"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid())
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, index=True)
    
    # Alert details
    alert_type = Column(String(50), nullable=False, comment="warning, critical, breached")
    sla_type = Column(String(20), nullable=False, comment="response, resolution")
    
    # Alert data
    threshold_percentage = Column(Float, comment="Percentage of time remaining when alert triggered")
    time_remaining_minutes = Column(Integer, comment="Minutes remaining when alert triggered")
    deadline = Column(DateTime(timezone=True), comment="SLA deadline")
    
    # Alert status
    is_active = Column(Boolean, default=True, index=True)
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True))
    
    # Additional data
    alert_metadata = Column(JSON, default=dict)
    
    # Relationships
    ticket = relationship("Ticket", back_populates="alerts")
    
    # Indexes
    __table_args__ = (
        Index('idx_alert_active', 'is_active', 'alert_type'),
        Index('idx_alert_ticket_type', 'ticket_id', 'alert_type'),
    )


class SLAConfigModel(Base):
    """Model to store SLA configuration snapshots."""
    
    __tablename__ = "sla_config_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid())
    
    # Configuration data
    config_data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    created_by = Column(String(255), default="system")
    
    # Indexes
    __table_args__ = (
        Index('idx_config_version', 'version'),
    )
