"""Logging configuration and setup for structured logging."""

import logging
import sys
from typing import Any

import structlog
from pythonjsonlogger import jsonlogger

from app.config import settings


def setup_logging():
    """Setup structured logging configuration."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if not settings.debug else logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    
    # Log startup message
    structlog.get_logger(__name__).info(
        "Logging configuration initialized",
        log_level=settings.log_level,
        structured_logging=settings.structured_logging,
        debug=settings.debug
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_request(
    logger: structlog.BoundLogger,
    request: Any,
    response_status: int,
    response_time: float,
    correlation_id: str = None
):
    """Log HTTP request with structured data."""
    logger.info(
        "HTTP request processed",
        method=getattr(request, 'method', 'UNKNOWN'),
        url=str(getattr(request, 'url', 'UNKNOWN')),
        status_code=response_status,
        response_time_seconds=response_time,
        correlation_id=correlation_id,
        user_agent=getattr(request, 'headers', {}).get('user-agent', 'UNKNOWN')
    )


def log_database_operation(
    logger: structlog.BoundLogger,
    operation: str,
    table: str,
    record_id: str = None,
    duration_ms: float = None,
    success: bool = True,
    error: str = None
):
    """Log database operations."""
    log_data = {
        "operation": operation,
        "table": table,
        "record_id": record_id,
        "duration_ms": duration_ms,
        "success": success
    }
    
    if error:
        log_data["error"] = error
        logger.error("Database operation failed", **log_data)
    else:
        logger.info("Database operation completed", **log_data)


def log_sla_event(
    logger: structlog.BoundLogger,
    event_type: str,
    ticket_id: str,
    external_id: str,
    sla_type: str = None,
    status: str = None,
    remaining_minutes: int = None,
    escalation_level: int = None
):
    """Log SLA-related events."""
    logger.info(
        f"SLA event: {event_type}",
        event_type=event_type,
        ticket_id=ticket_id,
        external_id=external_id,
        sla_type=sla_type,
        status=status,
        remaining_minutes=remaining_minutes,
        escalation_level=escalation_level
    )


def log_websocket_event(
    logger: structlog.BoundLogger,
    event_type: str,
    user_id: str = None,
    connection_id: str = None,
    message_type: str = None,
    success: bool = True,
    error: str = None
):
    """Log WebSocket events."""
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "connection_id": connection_id,
        "message_type": message_type,
        "success": success
    }
    
    if error:
        log_data["error"] = error
        logger.error("WebSocket event failed", **log_data)
    else:
        logger.info("WebSocket event completed", **log_data)


def add_correlation_id(
    logger: structlog.BoundLogger,
    correlation_id: str
) -> structlog.BoundLogger:
    """Add correlation ID to logger context."""
    return logger.bind(correlation_id=correlation_id)
