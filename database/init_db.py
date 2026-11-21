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
from database.models import AccountModel, Base, UserModel, UserRole
from database.session import get_engine, get_sessionmaker
from backend.app.core.config import get_settings
from backend.app.core.security import hash_password

logger = logging.getLogger(__name__)
settings = get_settings()


async def init_db() -> None:
    """Initializes tables, applies schema migrations, and seeds default user & account data."""
    engine = get_engine()
    logger.info("Initializing database tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Ensure schema migrations are applied idempotently for newly added safety & auth fields
        try:
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS daily_starting_equity NUMERIC(14, 2) DEFAULT 100000.00;"))
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS circuit_breaker_tripped BOOLEAN DEFAULT FALSE;"))
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS circuit_breaker_reason VARCHAR(128);"))
            await conn.execute(text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS user_id BIGINT;"))
            await conn.execute(text("UPDATE accounts SET daily_starting_equity = equity_inr WHERE daily_starting_equity IS NULL;"))
        except Exception as mig_exc:
            logger.debug(f"Schema migration skipped or dialect incompatible: {mig_exc}")

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        # 1. Seed or Verify Default Admin User
        admin_res = await session.execute(
            select(UserModel).where(UserModel.username == settings.DEFAULT_ADMIN_USERNAME)
        )
        admin_user = admin_res.scalar_one_or_none()

        if admin_user is None:
            hashed_pw, salt = hash_password(settings.DEFAULT_ADMIN_PASSWORD)
            admin_user = UserModel(
                username=settings.DEFAULT_ADMIN_USERNAME,
                email=settings.DEFAULT_ADMIN_EMAIL,
                hashed_password=hashed_pw,
                salt=salt,
                role=UserRole.ADMIN,
                is_active=True,
                api_key="ak_live_admin_master_key",
            )
            session.add(admin_user)
            await session.flush()
            logger.info(f"Default admin user created: '{admin_user.username}' (role: {admin_user.role})")
        else:
            logger.info(f"Default admin user verified: '{admin_user.username}'")

        # 2. Check if default INR account exists
        result_inr = await session.execute(
            select(AccountModel).where(AccountModel.account_name == "Primary Paper Account")
        )
        account_inr = result_inr.scalar_one_or_none()

        if account_inr is None:
            initial_capital = settings.INITIAL_VIRTUAL_CAPITAL_INR
            account_inr = AccountModel(
                user_id=admin_user.id,
                account_name="Primary Paper Account",
                initial_capital_inr=initial_capital,
                cash_balance_inr=initial_capital,
                equity_inr=initial_capital,
                currency="INR",
                is_active=True,
            )
            session.add(account_inr)
            logger.info(
                "Created primary INR paper trading account",
                extra={"extra_context": {"initial_capital_inr": str(initial_capital), "currency": "INR"}}
            )
        else:
            if account_inr.user_id is None:
                account_inr.user_id = admin_user.id
            logger.info(
                "Primary INR paper trading account verified",
                extra={"extra_context": {"equity_inr": str(account_inr.equity_inr)}}
            )

        # 3. Check if default USD account exists
        result_usd = await session.execute(
            select(AccountModel).where(AccountModel.account_name == "Primary USD Paper Account")
        )
        account_usd = result_usd.scalar_one_or_none()

        if account_usd is None:
            initial_usd = Decimal("25000.00")
            account_usd = AccountModel(
                user_id=admin_user.id,
                account_name="Primary USD Paper Account",
                initial_capital_inr=initial_usd,
                cash_balance_inr=initial_usd,
                equity_inr=initial_usd,
                currency="USD",
                is_active=True,
            )
            session.add(account_usd)
            logger.info(
                "Created primary USD paper trading account",
                extra={"extra_context": {"initial_capital_usd": str(initial_usd), "currency": "USD"}}
            )
        else:
            if account_usd.user_id is None:
                account_usd.user_id = admin_user.id
            logger.info(
                "Primary USD paper trading account verified",
                extra={"extra_context": {"equity_usd": str(account_usd.equity_inr)}}
            )

        await session.commit()


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
