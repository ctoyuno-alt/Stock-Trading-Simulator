"""
Async Database Session & Engine Configuration.

Features:
- SQLAlchemy 2.0 AsyncIO Engine.
- Resource-constrained connection pooling tuned for server stability.
- Automatic session cleanup and rollback on exception.
- Graceful fallback for local test suites.
"""

from typing import AsyncGenerator
import logging
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Singleton getter for the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        db_url = settings.async_database_url
        connect_args = {}
        pool_kwargs = {}

        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False
        else:
            # Memory-conservative pool settings for server environments
            pool_kwargs = {
                "pool_size": 5,
                "max_overflow": 5,
                "pool_timeout": 15,
                "pool_recycle": 1800,
                "pool_pre_ping": True,
            }

        _engine = create_async_engine(
            db_url,
            echo=settings.DEBUG,
            connect_args=connect_args,
            **pool_kwargs,
        )
        logger.info(
            "Initialized async database engine",
            extra={"extra_context": {"db_host": settings.POSTGRES_HOST, "db_name": settings.POSTGRES_DB}}
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Returns the async session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _sessionmaker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session per request."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
