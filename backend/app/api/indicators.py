"""
Technical Indicators API Routes.

Exposes:
- Latest computed indicator snapshot (EMA 20/50, RSI 14, MACD, VWAP).
- Full indicator time series aligned with historical OHLCV bars.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.market_data.storage import MarketDataStorage
from backend.app.market_data.universe import universe_manager
from backend.app.market_data.yfinance_provider import YFinanceProvider
from database.session import get_db
from indicators.engine import indicator_engine

router = APIRouter(prefix="/api/v1/indicators", tags=["Technical Indicators"])
market_provider = YFinanceProvider()


@router.get("/{symbol}", summary="Fetch Technical Indicators Time Series & Snapshot")
async def get_indicators(
    symbol: str,
    timeframe: str = Query("1d", regex="^(1d|1h|15m|5m)$"),
    include_series: bool = Query(True, description="Whether to include full historical time series"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Computes EMA 20, EMA 50, RSI 14, MACD (12, 26, 9), and VWAP.
    Returns market regime classification and indicator snapshot.
    """
    clean_symbol = universe_manager.normalize_symbol(symbol)
    if clean_symbol not in universe_manager.get_symbols():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{clean_symbol}' not found in active trading universe.",
        )

    # 1. Fetch historical candles from DB or Provider
    candles = await MarketDataStorage.get_candles(db, symbol=clean_symbol, timeframe=timeframe, limit=200)

    if not candles or len(candles) < 30:
        # Fallback to provider or deterministic generator
        batch = market_provider.fetch_historical_ohlcv(clean_symbol, timeframe=timeframe, period="1y")
        if not batch.candles:
            batch = YFinanceProvider.generate_synthetic_history(clean_symbol, days=120)
        candles = batch.candles

    # 2. Compute Indicators
    try:
        series = indicator_engine.compute(clean_symbol, candles)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indicator calculation error for {clean_symbol}: {str(exc)}",
        )

    if include_series:
        return series.to_dict()

    return {
        "symbol": clean_symbol,
        "latest_snapshot": series.snapshot.to_dict(),
    }


@router.get("/snapshot/{symbol}", summary="Fetch Latest Indicator Snapshot")
async def get_indicator_snapshot(
    symbol: str,
    timeframe: str = Query("1d", regex="^(1d|1h|15m|5m)$"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Lightweight endpoint returning strictly the current indicator snapshot and market regime flags.
    """
    return await get_indicators(symbol=symbol, timeframe=timeframe, include_series=False, db=db)
