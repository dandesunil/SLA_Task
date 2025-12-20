"""Database configuration and connection management."""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Base model class
Base = declarative_base()



# Async database engine for PostgreSQL
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    max_overflow=20,
    pool_size=10,
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_async_session():
    """Dependency to get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", error=str(e))
            raise
        finally:
            await session.close()



async def init_database():
    """Initialize database tables."""
    async with async_engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    # logger.info("Database initialized successfully")


async def close_database():
    """Close database connections."""
    await async_engine.dispose()
    # logger.info("Database connections closed")
