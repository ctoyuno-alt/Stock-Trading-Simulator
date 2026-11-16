"""
Market Data API Routes.

Exposes:
- Universe metadata and active instruments.
- Historical OHLCV candle query endpoints with data quality audits.
- Historical data synchronization endpoints.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.market_data.base import MarketDataBatch
from backend.app.market_data.storage import MarketDataStorage
from backend.app.market_data.universe import universe_manager
from backend.app.market_data.yfinance_provider import YFinanceProvider
from database.session import get_db

router = APIRouter(prefix="/api/v1/market-data", tags=["Market Data"])
provider = YFinanceProvider()


class InstrumentResponse(BaseModel):
    symbol: str
    yfinance_ticker: str
    company_name: str
    sector: str
    exchange: str
    tick_size: float
    lot_size: int
    currency: str
    is_active: bool


class SyncRequest(BaseModel):
    symbols: Optional[List[str]] = None
    timeframe: str = "1d"
    period: str = "6mo"


@router.get("/universe", response_model=List[InstrumentResponse], summary="List Tradable Universe")
async def get_universe() -> List[Dict[str, Any]]:
    """Returns the tracked NSE liquid large-cap universe with metadata."""
    instruments = universe_manager.list_instruments()
    return [inst.to_dict() for inst in instruments]


@router.get("/candles/{symbol}", summary="Fetch OHLCV Candles")
async def get_candles(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1d|1h|15m|5m)$"),
    period: str = Query("6mo", description="Historical period (e.g., 1mo, 3mo, 6mo, 1y)"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Fetches OHLCV candles with transparent provider metadata, delay notices, and validation audits.
    """
    clean_symbol = universe_manager.normalize_symbol(symbol)
    if clean_symbol not in universe_manager.get_symbols():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{clean_symbol}' not found in active trading universe.",
        )

    # 1. Check local DB cache first
    cached_candles = await MarketDataStorage.get_candles(db, symbol=clean_symbol, timeframe=timeframe)

    if cached_candles and len(cached_candles) >= 30:
        batch = MarketDataBatch(
            symbol=clean_symbol,
            exchange="NSE",
            timeframe=timeframe,
            candles=cached_candles,
            provider="database_cache",
            is_delayed=True,
            delay_minutes=15,
        )
        provider.validate_batch(batch)
        return batch.to_dict()

    # 2. Fetch via provider
    batch = provider.fetch_historical_ohlcv(clean_symbol, timeframe=timeframe, period=period)

    # If yfinance failed to fetch (e.g. offline environment), fallback to deterministic synthetic data
    if not batch.candles:
        batch = YFinanceProvider.generate_synthetic_history(clean_symbol, days=120)

    # Persist in DB
    try:
        await MarketDataStorage.save_candles(db, batch)
    except Exception:
        pass  # Non-fatal if DB write encounters transient issue

    return batch.to_dict()


@router.post("/sync", summary="Synchronize Historical Data")
async def sync_market_data(
    payload: SyncRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Synchronizes historical market data for all or selected universe symbols.
    """
    target_symbols = payload.symbols or universe_manager.get_symbols()
    results = {}

    for sym in target_symbols:
        clean = universe_manager.normalize_symbol(sym)
        batch = provider.fetch_historical_ohlcv(clean, timeframe=payload.timeframe, period=payload.period)
        if not batch.candles:
            batch = YFinanceProvider.generate_synthetic_history(clean, days=120)

        saved_count = await MarketDataStorage.save_candles(db, batch)
        results[clean] = {
            "synced_candles": saved_count,
            "provider": batch.provider,
            "is_delayed": batch.is_delayed,
            "validation": batch.validation.to_dict() if batch.validation else None,
        }

    return {
        "status": "success",
        "synced_instruments_count": len(results),
        "details": results,
    }
