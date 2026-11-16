"""
Database Initialization, Health Verification, and Seed Management.

Ensures:
- Creation of all relational tables on startup.
- Verification of database read/write health.
- Seeding of default paper trading account with ₹100,000.00 INR virtual capital.
"""

from decimal import Decimal
import logging
import time
from typing import Tuple
from sqlalchemy import select, text
from database.models import AccountModel, Base
from database.session import get_engine, get_sessionmaker
from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def init_db() -> None:
    """Initializes tables and seeds default account data."""
    engine = get_engine()
    logger.info("Initializing database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        # Check if default account exists
        result = await session.execute(
            select(AccountModel).where(AccountModel.account_name == "Primary Paper Account")
        )
        account = result.scalar_one_or_none()

        if account is None:
            initial_capital = settings.INITIAL_VIRTUAL_CAPITAL_INR
            account = AccountModel(
                account_name="Primary Paper Account",
                initial_capital_inr=initial_capital,
                cash_balance_inr=initial_capital,
                equity_inr=initial_capital,
                currency=settings.CURRENCY,
                is_active=True,
            )
            session.add(account)
            await session.commit()
            logger.info(
                "Created primary paper trading account",
                extra={"extra_context": {"initial_capital_inr": str(initial_capital), "currency": settings.CURRENCY}}
            )
        else:
            logger.info(
                "Primary paper trading account verified",
                extra={"extra_context": {"equity_inr": str(account.equity_inr)}}
            )


async def verify_database_connection() -> Tuple[bool, float, str]:
    """
    Executes a lightweight ping to verify database liveness and measure query round-trip latency.
    
    Returns:
        (is_healthy: bool, latency_ms: float, detail: str)
    """
    engine = get_engine()
    start_time = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return True, latency_ms, "Database connection operational"
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(f"Database health verification failed: {str(exc)}")
        return False, latency_ms, f"Database connectivity error: {str(exc)}"
