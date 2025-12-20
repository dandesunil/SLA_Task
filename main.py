"""Main FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import structlog
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings, sla_config
from app.database import init_database, close_database
from app.api.tickets import router as tickets_router
from app.services.sla_engine import SLAEngine
from app.services.ticket_service import TicketService
from app.services.escalation_service import EscalationService
from app.utils.sla_calculator import SLACalculator
from app.utils.logging import setup_logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydantic import ValidationError
from app.database import AsyncSessionLocal
from ticket_triage_service.rag_pipeline import run_rag,PromptIntentClassifier


# Setup structured logging
# setup_logging()

logger = structlog.get_logger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


class ConfigFileHandler(FileSystemEventHandler):
    """Handle configuration file changes."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        super().__init__()
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.yaml'):
            # logger.info("Configuration file changed, reloading...")
            try:
                self.config_manager.load_config()
                # logger.info("Configuration reloaded successfully")
            except Exception as e:
                logger.error("Failed to reload configuration", error=str(e))


async def start_background_scheduler():
    """Start the background SLA evaluation scheduler."""
    global scheduler
    
    try:
        # Create service instances
        sla_calculator = SLACalculator()
        ticket_service = TicketService(sla_calculator)
        escalation_service = EscalationService()
        sla_engine = SLAEngine(ticket_service, escalation_service)
        
        # Add job to run every minute
        scheduler.add_job(
            run_sla_evaluation,
            trigger=CronTrigger(minute="*"),  # Run every minute
            id="sla_evaluation",
            name="SLA Evaluation",
            replace_existing=True,
            max_instances=1  # Ensure only one instance runs at a time
        )
        
        # Start scheduler
        scheduler.start()
        
        # logger.info(
        #     "Background SLA scheduler started",
        #     interval_seconds=settings.scheduler_interval
        # )
        
    except Exception as e:
        logger.error("Failed to start background scheduler", error=str(e))
        raise


async def stop_background_scheduler():
    """Stop the background scheduler."""
    global scheduler
    
    try:
        scheduler.shutdown()
        # logger.info("Background scheduler stopped")
    except Exception as e:
        logger.error("Error stopping scheduler", error=str(e))


async def run_sla_evaluation():
    """Run SLA evaluation for all tickets."""
    try:
        from app.database import get_async_session
        from app.services.sla_engine import SLAEngine
        from app.services.ticket_service import TicketService
        from app.services.escalation_service import EscalationService
        from app.utils.sla_calculator import SLACalculator
        
        # Create service instances
        sla_calculator = SLACalculator()
        ticket_service = TicketService(sla_calculator)
        escalation_service = EscalationService()
        sla_engine = SLAEngine(ticket_service, escalation_service)
        
        # Get database session
        async with AsyncSessionLocal() as db:
            await sla_engine.evaluate_all_tickets(db)
        # result = await sla_engine.evaluate_all_tickets(db_session)
         # logger.info(
            #     "Scheduled SLA evaluation completed",
            #     processed_tickets=result["processed_tickets"],
            #     alerts_created=result["alerts_created"],
            #     breaches_detected=result["breaches_detected"]
            # )
            
           
            
    except Exception as e:
        logger.error("Scheduled SLA evaluation failed", error=str(e))


async def setup_config_monitoring():
    """Setup file monitoring for configuration changes."""
    try:
        event_handler = ConfigFileHandler(sla_config)
        observer = Observer()
        observer.schedule(event_handler, ".", recursive=False)
        observer.start()
        # logger.info("Configuration file monitoring started")
    except Exception as e:
        logger.error("Failed to setup config monitoring", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    # logger.info("Starting SLA Tracking Service", 
    #            app_name=settings.app_name,
    #            debug=settings.debug)
    
    try:
        # Initialize database
        await init_database()
        # logger.info("Database initialized")
        
        # Start background scheduler
        await start_background_scheduler()
        
        # Setup configuration monitoring
        await setup_config_monitoring()
        
        # logger.info("SLA Tracking Service started successfully")
        yield
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise
    finally:
        # Shutdown
        # logger.info("Shutting down SLA Tracking Service")
        
        try:
            await stop_background_scheduler()
            await close_database()
            # logger.info("SLA Tracking Service shutdown complete")
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Micro service for tracking and escalating customer support tickets with SLA monitoring",
    version="1.0.0",
    lifespan=lifespan
)

class CustomMiddleWare(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            # Custom middleware logic can be added here
            response = await call_next(request)
            return response
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})


app.add_middleware(CustomMiddleWare)

# Include routers
app.include_router(tickets_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "SLA Tracker API"}


@app.post("/classify")
async def classify_ticket(content: str):
    """Classify ticket content using RAG pipeline"""
    try:
        classifier = PromptIntentClassifier()

        intents = [
            "password reset",
            "account login issue",
            "DSPM documentation question",
            "release notes inquiry",
            "general help"
        ]
        result = classifier.classify(content, intents)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
    
@app.post("/respond")
async def responsd(question: str):
    """Run RAG on given input question"""
    try:
        result = run_rag(question)
        print("\nANSWER:\n", result["answer"])
        print("\nSOURCES:")
        for i, s in enumerate(result["sources"], 1):
            print(f"[{i}] {s[:200]}...")
        return {"result": result["answer"]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

if __name__ == "__main__":
    import uvicorn
    
    # logger.info("Starting SLA Tracking Service with uvicorn")
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )
