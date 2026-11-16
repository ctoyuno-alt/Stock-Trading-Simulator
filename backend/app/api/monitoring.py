"""
System Monitoring, Observability, and Prometheus Metrics API Routes.

Exposes:
- Diagnostic telemetry endpoint (/api/v1/monitoring/diagnostics).
- Prometheus text-formatted metrics (/metrics) for Grafana/ELK observability.
- Process memory utilization, database roundtrip latency, and quant engine state.
"""

from datetime import datetime, timezone
from decimal import Decimal
import os
import resource
import time
from typing import Any, Dict
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.market_schedule import get_current_ist_time, is_market_open
from backend.app.core.monitoring import get_process_memory_mb, get_service_uptime_seconds, SERVICE_START_TIME
from database.init_db import verify_database_connection
from database.models import AccountModel, OrderModel, PositionModel, PositionStatus
from database.session import get_db

router = APIRouter(tags=["Monitoring & Observability"])
settings = get_settings()

SERVICE_START_TIME = time.time()


def get_process_memory_mb() -> float:
    """Returns the resident set size (RSS) memory consumption of the Python process in MB."""
    # ru_maxrss is in kilobytes on Linux
    usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(usage_kb / 1024.0, 2)


@router.get("/api/v1/monitoring/diagnostics", summary="Detailed System Diagnostics")
async def get_system_diagnostics(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns granular diagnostic metrics:
    - Process uptime and resident memory.
    - Database roundtrip latency in ms.
    - Active paper trading exposure and account funds.
    - Market session state (IST).
    - Security guardrails status.
    """
    uptime_seconds = round(time.time() - SERVICE_START_TIME, 1)
    memory_mb = get_process_memory_mb()
    db_healthy, db_latency, db_msg = await verify_database_connection()
    is_open, market_reason = is_market_open()
    ist_now = get_current_ist_time().strftime("%Y-%m-%d %H:%M:%S IST")

    # Fetch ledger summary
    acc_res = await db.execute(
        select(AccountModel).where(AccountModel.account_name == "Primary Paper Account")
    )
    account = acc_res.scalar_one_or_none()

    pos_res = await db.execute(
        select(PositionModel).where(PositionModel.status == PositionStatus.OPEN)
    )
    open_positions = pos_res.scalars().all()

    orders_count_res = await db.execute(select(OrderModel))
    total_orders = len(orders_count_res.scalars().all())

    return {
        "status": "healthy" if db_healthy and not settings.PAPER_TRADING_KILL_SWITCH else "degraded",
        "service": "paper-trading-backend",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "ist_time": ist_now,
        "runtime": {
            "uptime_seconds": uptime_seconds,
            "memory_resident_mb": memory_mb,
            "pid": os.getpid(),
        },
        "database": {
            "connected": db_healthy,
            "query_latency_ms": db_latency,
            "message": db_msg,
        },
        "market_session": {
            "is_open": is_open,
            "details": market_reason,
            "exchange": settings.PRIMARY_EXCHANGE,
        },
        "trading_state": {
            "equity_inr": float(account.equity_inr) if account else 100000.0,
            "cash_balance_inr": float(account.cash_balance_inr) if account else 100000.0,
            "open_positions_count": len(open_positions),
            "total_orders_executed": total_orders,
        },
        "safety_guardrails": {
            "real_trading_locked": not settings.ENABLE_REAL_TRADING,
            "kill_switch_active": settings.PAPER_TRADING_KILL_SWITCH,
            "broker_integration": "NONE (Paper Sandbox Only)",
        },
    }


@router.get("/metrics", summary="Prometheus Text Metrics")
async def get_prometheus_metrics(
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Exposes Prometheus text-formatted gauges and counters for time-series observability.
    """
    uptime = time.time() - SERVICE_START_TIME
    mem_mb = get_process_memory_mb()
    db_healthy, db_latency, _ = await verify_database_connection()
    is_open, _ = is_market_open()

    acc_res = await db.execute(
        select(AccountModel).where(AccountModel.account_name == "Primary Paper Account")
    )
    account = acc_res.scalar_one_or_none()
    equity = float(account.equity_inr) if account else 100000.0
    cash = float(account.cash_balance_inr) if account else 100000.0

    pos_res = await db.execute(
        select(PositionModel).where(PositionModel.status == PositionStatus.OPEN)
    )
    open_count = len(pos_res.scalars().all())

    lines = [
        "# HELP paper_trading_uptime_seconds Total process uptime in seconds",
        "# TYPE paper_trading_uptime_seconds gauge",
        f"paper_trading_uptime_seconds {uptime:.1f}",
        "",
        "# HELP paper_trading_process_memory_mb Resident process memory in MB",
        "# TYPE paper_trading_process_memory_mb gauge",
        f"paper_trading_process_memory_mb {mem_mb}",
        "",
        "# HELP paper_trading_db_latency_ms Database round-trip query latency in ms",
        "# TYPE paper_trading_db_latency_ms gauge",
        f"paper_trading_db_latency_ms {db_latency}",
        "",
        "# HELP paper_trading_equity_inr Total portfolio equity in INR",
        "# TYPE paper_trading_equity_inr gauge",
        f"paper_trading_equity_inr {equity:.2f}",
        "",
        "# HELP paper_trading_cash_inr Available unencumbered cash balance in INR",
        "# TYPE paper_trading_cash_inr gauge",
        f"paper_trading_cash_inr {cash:.2f}",
        "",
        "# HELP paper_trading_open_positions Count of currently open swing positions",
        "# TYPE paper_trading_open_positions gauge",
        f"paper_trading_open_positions {open_count}",
        "",
        "# HELP paper_trading_kill_switch_active Status of emergency kill switch (1=active, 0=standby)",
        "# TYPE paper_trading_kill_switch_active gauge",
        f"paper_trading_kill_switch_active {1 if settings.PAPER_TRADING_KILL_SWITCH else 0}",
        "",
        "# HELP paper_trading_market_open Whether NSE exchange regular session is currently open (1=open, 0=closed)",
        "# TYPE paper_trading_market_open gauge",
        f"paper_trading_market_open {1 if is_open else 0}",
    ]

    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
