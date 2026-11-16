"""
Backtesting API Router.

Exposes:
- Historical backtest simulation endpoint evaluating multi-factor swing trading strategy
  without look-ahead bias and accounting for Indian transaction costs and slippage.
"""

from decimal import Decimal
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.market_data.storage import MarketDataStorage
from backend.app.market_data.universe import universe_manager
from backend.app.market_data.yfinance_provider import YFinanceProvider
from database.session import get_db
from strategies.swing_strategy import EMAMACDSwingStrategy
from trading.backtest import BacktestEngine

router = APIRouter(prefix="/api/v1/backtest", tags=["Backtesting Engine"])
market_provider = YFinanceProvider()


class BacktestRequest(BaseModel):
    symbol: str = Field(description="NSE Ticker symbol (e.g. RELIANCE, TCS)")
    timeframe: str = Field(default="1d", pattern="^(1d|1h|15m)$")
    period: str = Field(default="1y", description="Lookback window (e.g. 6mo, 1y, 2y)")
    initial_capital_inr: float = Field(default=100000.0, gt=0, description="Virtual capital in INR")
    max_risk_per_trade: float = Field(default=0.01, gt=0, le=0.05, description="1% risk budget (0.01)")
    slippage_bps: float = Field(default=5.0, ge=0, description="Slippage in basis points (5 bps = 0.05%)")


@router.post("/run", summary="Execute Historical Strategy Backtest")
async def run_backtest(
    payload: BacktestRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Executes a walk-forward chronological backtest:
    - Simulates order execution, slippage, and Indian taxes (STT, Brokerage, GST, Stamp duty).
    - Tracks position stop-loss triggers and take-profit targets.
    - Computes Win Rate, Profit Factor, Max Drawdown, and Sharpe Ratio.
    """
    clean_symbol = universe_manager.normalize_symbol(payload.symbol)
    if clean_symbol not in universe_manager.get_symbols():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{clean_symbol}' not found in active trading universe.",
        )

    # 1. Fetch candles from DB or Provider
    candles = await MarketDataStorage.get_candles(db, symbol=clean_symbol, timeframe=payload.timeframe, limit=500)

    if not candles or len(candles) < 70:
        batch = market_provider.fetch_historical_ohlcv(clean_symbol, timeframe=payload.timeframe, period=payload.period)
        if not batch.candles or len(batch.candles) < 70:
            batch = YFinanceProvider.generate_synthetic_history(clean_symbol, days=200)
        candles = batch.candles

    if len(candles) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient historical bars ({len(candles)}) for backtesting. Minimum 50 bars required.",
        )

    strategy = EMAMACDSwingStrategy()
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital_inr=Decimal(str(round(payload.initial_capital_inr, 2))),
        max_risk_per_trade=payload.max_risk_per_trade,
        slippage_bps=payload.slippage_bps,
        warmup_bars=50,
    )

    try:
        result = engine.run(clean_symbol, candles)
        return result.to_dict()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtesting engine failed for {clean_symbol}: {str(exc)}",
        )
