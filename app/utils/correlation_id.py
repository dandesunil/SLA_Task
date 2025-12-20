"""Correlation ID middleware for request tracing."""

import uuid
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to requests and responses."""
    
    def __init__(self, app, header_name: str = "X-Correlation-ID"):
        super().__init__(app)
        self.header_name = header_name
        self.logger = structlog.get_logger(__name__)
    
    async def dispatch(self, request: Request, call_next):
        # Get or generate correlation ID
        correlation_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        
        # Add correlation ID to request state for access in route handlers
        request.state.correlation_id = correlation_id
        
        # Add correlation ID to response headers
        response = await call_next(request)
        response.headers[self.header_name] = correlation_id
        
        # Log request with correlation ID
        # self.logger.info(
        #     "Request processed",
        #     correlation_id=correlation_id,
        #     method=request.method,
        #     url=str(request.url),
        #     client_ip=request.client.host if request.client else "unknown"
        # )
        
        return response


def get_correlation_id(request: Request) -> str:
    """Get correlation ID from request state."""
    return getattr(request.state, 'correlation_id', 'no-correlation-id')


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())
