"""
Autonomous AI Auto-Trading API Routes.

Exposes:
- Manual and recurring trigger endpoints for autonomous trade scanning and execution.
- Bot configuration management (confluence thresholds, Gemini AI gates, auto-exit rules).
- Live decision history and audit logs.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from trading.auto_trader import auto_trading_bot, AutoTraderConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auto-trader", tags=["Autonomous AI Auto-Trader"])


class UpdateConfigRequest(BaseModel):
    enabled: Optional[bool] = Field(default=None, description="Master Auto-Trader switch")
    min_confluence_score: Optional[int] = Field(
        default=None, ge=50, le=100, description="Minimum technical score (50-100) to trigger BUY"
    )
    require_ai_approval: Optional[bool] = Field(
        default=None, description="Require Gemini AI confirmation gate before order routing"
    )
    auto_exit_on_reversal: Optional[bool] = Field(
        default=None, description="Automatically close position if technical strategy shifts to SELL"
    )
    max_open_positions: Optional[int] = Field(
        default=None, ge=1, le=10, description="Max concurrent positions per currency account"
    )
    enforce_market_hours: Optional[bool] = Field(
        default=None, description="Enforce realistic session hours (09:15-15:30 IST / 09:30-16:00 ET)"
    )
    timeframe: Optional[str] = Field(
        default=None, pattern="^(1d|1h|15m|5m)$", description="Default analysis bar timeframe"
    )


class AutoTraderTickRequest(BaseModel):
    market: str = Field(default="IN", pattern="^(IN|US)$", description="Market identifier (IN or US)")
    enforce_market_hours: Optional[bool] = Field(default=None, description="Override market hours check")
    timeframe: Optional[str] = Field(default=None, pattern="^(1d|1h|15m|5m)$", description="Override timeframe")


@router.get("/status", summary="Get Auto-Trader Status & Config")
async def get_status() -> Dict[str, Any]:
    """Returns current configuration, last execution timestamp, and recent decision log."""
    return {
        "config": auto_trading_bot.config.to_dict(),
        "last_cycle_at": auto_trading_bot.last_cycle_at.isoformat() if auto_trading_bot.last_cycle_at else None,
        "history_count": len(auto_trading_bot._history),
        "recent_decisions": auto_trading_bot.get_history(),
    }


@router.post("/config", summary="Update Auto-Trader Configuration")
async def update_config(payload: UpdateConfigRequest) -> Dict[str, Any]:
    """Updates bot execution parameters (confluence thresholds, AI gates, risk ceilings)."""
    cfg = auto_trading_bot.config
    if payload.enabled is not None:
        cfg.enabled = payload.enabled
    if payload.min_confluence_score is not None:
        cfg.min_confluence_score = payload.min_confluence_score
    if payload.require_ai_approval is not None:
        cfg.require_ai_approval = payload.require_ai_approval
    if payload.auto_exit_on_reversal is not None:
        cfg.auto_exit_on_reversal = payload.auto_exit_on_reversal
    if payload.max_open_positions is not None:
        cfg.max_open_positions = payload.max_open_positions
    if payload.enforce_market_hours is not None:
        cfg.enforce_market_hours = payload.enforce_market_hours
    if payload.timeframe is not None:
        cfg.timeframe = payload.timeframe

    logger.info(f"Auto-Trader configuration updated: {cfg.to_dict()}")
    return {
        "status": "success",
        "message": "Auto-Trader configuration updated successfully",
        "config": cfg.to_dict(),
    }


@router.post("/tick", summary="Trigger Autonomous Trading Evaluation Cycle")
async def trigger_cycle(
    market: str = Query(default="IN", pattern="^(IN|US)$"),
    enforce_market_hours: Optional[bool] = Query(default=None),
    timeframe: Optional[str] = Query(default=None, pattern="^(1d|1h|15m|5m)$"),
    payload: Optional[AutoTraderTickRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Executes a single autonomous evaluation and order routing cycle:
    1. Monitors open positions for stop-loss / take-profit hits or technical reversals.
    2. Scans universe for high-confluence entry signals.
    3. Sizes approved orders via 1% equity risk rule and executes paper trade.
    """
    active_market = payload.market if payload and payload.market else market
    active_market = active_market.upper()

    # Clone configuration for override if needed
    cfg_override = AutoTraderConfig(
        enabled=auto_trading_bot.config.enabled,
        min_confluence_score=auto_trading_bot.config.min_confluence_score,
        require_ai_approval=auto_trading_bot.config.require_ai_approval,
        auto_exit_on_reversal=auto_trading_bot.config.auto_exit_on_reversal,
        max_open_positions=auto_trading_bot.config.max_open_positions,
        enforce_market_hours=(
            payload.enforce_market_hours
            if payload and payload.enforce_market_hours is not None
            else (enforce_market_hours if enforce_market_hours is not None else auto_trading_bot.config.enforce_market_hours)
        ),
        timeframe=(
            payload.timeframe
            if payload and payload.timeframe is not None
            else (timeframe if timeframe is not None else auto_trading_bot.config.timeframe)
        ),
    )

    try:
        result = await auto_trading_bot.run_cycle(
            session=db,
            market=active_market,
            config_override=cfg_override,
        )
        return {
            "status": "success",
            "cycle_result": result,
        }
    except Exception as exc:
        logger.error(f"Auto-Trader cycle execution failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auto-Trader cycle failed: {str(exc)}",
        )


@router.post("/clear-history", summary="Clear Decision History")
async def clear_history() -> Dict[str, Any]:
    """Clears in-memory decision audit log."""
    auto_trading_bot.clear_history()
    return {"status": "success", "message": "Decision history cleared."}
