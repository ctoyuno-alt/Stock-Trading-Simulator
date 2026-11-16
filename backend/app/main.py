"""
FastAPI Backend Application Entrypoint for AI Paper Trading Simulator.

Provides:
- Liveness & Readiness health check endpoints with database connectivity probes.
- Market session awareness (NSE/BSE trading window: 09:15 - 15:30 IST).
- Emergency Kill Switch management.
- Structured JSON logging.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.core.config import get_settings
from backend.app.core.logging import setup_logging
from backend.app.core.market_schedule import get_current_ist_time, is_market_open
from backend.app.api.market_data import router as market_data_router
from backend.app.api.indicators import router as indicators_router
from backend.app.api.strategies import router as strategies_router
from backend.app.api.ai_analysis import router as ai_analysis_router
from database.init_db import init_db, verify_database_connection

# Initialize structured logging
settings = get_settings()
setup_logging(log_level=settings.LOG_LEVEL, service_name="paper-trading-backend")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info("Initializing Paper Trading Backend service...")

    # Log sanitized configurations
    logger.info("Configuration loaded", extra={"extra_context": settings.sanitized_dict()})

    # Validate that real trading is strictly disabled
    if settings.ENABLE_REAL_TRADING:
        logger.critical("FATAL: Real trading flag is enabled. Halting startup immediately.")
        raise RuntimeError("Real trading is forbidden in paper trading environment.")

    # Attempt database initialization with graceful retry
    try:
        await init_db()
        logger.info("Database initialized and primary paper account verified.")
    except Exception as exc:
        logger.warning(
            f"Database initialization deferred (database may still be starting up): {str(exc)}"
        )

    yield

    logger.info("Shutting down Paper Trading Backend service...")


app = FastAPI(
    title="Gemini-Powered AI Paper Trading Simulator (NSE/BSE)",
    description=(
        "Production-grade paper trading and quantitative research platform "
        "tailored for Indian stock markets (NSE/BSE). Strictly virtual execution."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Streamlit and external dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(market_data_router)
app.include_router(indicators_router)
app.include_router(strategies_router)
app.include_router(ai_analysis_router)


# --- Response Schemas ---
class HealthLiveResponse(BaseModel):
    status: str
    service: str
    timestamp_utc: str
    version: str


class DatabaseHealth(BaseModel):
    connected: bool
    latency_ms: float
    message: str


class HealthReadyResponse(BaseModel):
    status: str
    database: DatabaseHealth
    kill_switch_active: bool
    real_trading_enabled: bool
    market_open: bool
    market_status: str
    ist_time: str


class KillSwitchRequest(BaseModel):
    activate: bool
    reason: str


# --- Health & Diagnostic Endpoints ---
@app.get(
    "/health/live",
    response_model=HealthLiveResponse,
    summary="Liveness Probe",
    tags=["Health"],
)
async def health_live() -> HealthLiveResponse:
    """Returns 200 OK if the FastAPI process is running."""
    return HealthLiveResponse(
        status="alive",
        service="paper-trading-backend",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )


@app.get(
    "/health/ready",
    response_model=HealthReadyResponse,
    summary="Readiness Probe",
    tags=["Health"],
)
async def health_ready() -> HealthReadyResponse:
    """
    Validates readiness:
    - Tests database connectivity and query latency.
    - Verifies safety constraints (kill switch, real trading disabled).
    - Checks Indian stock market session status.
    """
    db_healthy, db_latency, db_msg = await verify_database_connection()
    is_open, market_reason = is_market_open()
    ist_now = get_current_ist_time().strftime("%Y-%m-%d %H:%M:%S IST")

    overall_ready = db_healthy and not settings.PAPER_TRADING_KILL_SWITCH

    response_payload = HealthReadyResponse(
        status="ready" if overall_ready else "degraded",
        database=DatabaseHealth(
            connected=db_healthy,
            latency_ms=db_latency,
            message=db_msg,
        ),
        kill_switch_active=settings.PAPER_TRADING_KILL_SWITCH,
        real_trading_enabled=settings.ENABLE_REAL_TRADING,
        market_open=is_open,
        market_status=market_reason,
        ist_time=ist_now,
    )

    if not overall_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response_payload.model_dump(),
        )

    return response_payload


@app.get(
    "/api/v1/system/status",
    summary="Trading System Overview",
    tags=["System"],
)
async def system_status() -> Dict[str, Any]:
    """Returns exchange session status, virtual capital, universe, and risk budgets."""
    is_open, market_reason = is_market_open()
    ist_now = get_current_ist_time().strftime("%Y-%m-%d %H:%M:%S IST")

    return {
        "service": "AI Paper Trading Simulator",
        "primary_exchange": settings.PRIMARY_EXCHANGE,
        "secondary_exchange": settings.SECONDARY_EXCHANGE,
        "ist_time": ist_now,
        "market_open": is_open,
        "market_session_details": market_reason,
        "virtual_capital_currency": settings.CURRENCY,
        "initial_virtual_capital_inr": float(settings.INITIAL_VIRTUAL_CAPITAL_INR),
        "trading_universe": settings.universe_list,
        "universe_size": len(settings.universe_list),
        "risk_management": {
            "max_risk_per_trade_pct": settings.MAX_RISK_PER_TRADE * 100.0,
            "max_open_positions": settings.MAX_OPEN_POSITIONS,
            "max_allocation_per_position_pct": settings.MAX_ALLOCATION_PER_POSITION * 100.0,
            "mandatory_stop_loss": True,
        },
        "safety_guardrails": {
            "real_trading_enabled": settings.ENABLE_REAL_TRADING,
            "kill_switch_active": settings.PAPER_TRADING_KILL_SWITCH,
            "mode": "PAPER_TRADING_ONLY",
        },
    }


@app.post(
    "/api/v1/system/kill-switch",
    summary="Toggle Emergency Kill Switch",
    tags=["System"],
)
async def toggle_kill_switch(payload: KillSwitchRequest) -> Dict[str, Any]:
    """
    Emergency kill switch to halt all paper trade placement.
    """
    previous_state = settings.PAPER_TRADING_KILL_SWITCH
    settings.PAPER_TRADING_KILL_SWITCH = payload.activate

    logger.warning(
        f"KILL SWITCH STATE ALTERED: {previous_state} -> {payload.activate}",
        extra={"extra_context": {"reason": payload.reason, "activated": payload.activate}}
    )

    return {
        "success": True,
        "kill_switch_active": settings.PAPER_TRADING_KILL_SWITCH,
        "reason": payload.reason,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", summary="Root Metadata", tags=["System"])
async def root_index() -> Dict[str, Any]:
    return {
        "name": "Gemini-Powered AI Paper Trading Simulator (NSE/BSE)",
        "version": "1.0.0",
        "documentation": "/docs",
        "health_liveness": "/health/live",
        "health_readiness": "/health/ready",
        "system_status": "/api/v1/system/status",
    }
