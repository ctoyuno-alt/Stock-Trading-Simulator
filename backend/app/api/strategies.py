"""
Quantitative Trading Strategies API Routes.

Exposes:
- Real-time deterministic swing trading signals for individual instruments.
- Multi-asset strategy universe scanner evaluating all 10 liquid NSE equities.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.market_data.storage import MarketDataStorage
from backend.app.market_data.universe import universe_manager
from backend.app.market_data.yfinance_provider import YFinanceProvider
from database.session import get_db
from strategies.swing_strategy import EMAMACDSwingStrategy

router = APIRouter(prefix="/api/v1/strategies", tags=["Trading Strategies"])
strategy = EMAMACDSwingStrategy()
market_provider = YFinanceProvider()


@router.get("/signal/{symbol}", summary="Evaluate Strategy Signal for Symbol")
async def get_symbol_signal(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1d|1h|15m|5m)$"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Evaluates multi-factor swing trading rules (EMA 20/50, RSI 14, MACD, VWAP)
    and returns a structured TradeSignal with stop-loss and take-profit targets.
    """
    clean_symbol = universe_manager.normalize_symbol(symbol)
    if clean_symbol not in universe_manager.get_symbols():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{clean_symbol}' not found in active trading universe.",
        )

    # 1. Fetch historical candles from DB or Provider
    candles = await MarketDataStorage.get_candles(db, symbol=clean_symbol, timeframe=timeframe, limit=200)

    if not candles or len(candles) < 50:
        batch = market_provider.fetch_historical_ohlcv(clean_symbol, timeframe=timeframe, period="1y")
        if not batch.candles or len(batch.candles) < 50:
            batch = YFinanceProvider.generate_synthetic_history(clean_symbol, days=120)
        candles = batch.candles

    signal = strategy.generate_signal(clean_symbol, candles)
    return signal.to_dict()


@router.get("/signals", summary="Scan Active Universe for Signals")
async def scan_universe_signals(
    timeframe: str = Query("1d", pattern="^(1d|1h|15m|5m)$"),
    market: Optional[str] = Query(None, pattern="^(IN|US)$", description="Optional market filter: IN or US"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Scans the tradable universe (NSE or US mega-caps) and returns active signals.
    """
    symbols = universe_manager.get_symbols(market=market)
    buy_signals = []
    sell_signals = []
    hold_signals = []

    for sym in symbols:
        candles = await MarketDataStorage.get_candles(db, symbol=sym, timeframe=timeframe, limit=120)
        if not candles or len(candles) < 50:
            batch = market_provider.fetch_historical_ohlcv(sym, timeframe=timeframe, period="6mo")
            if not batch.candles or len(batch.candles) < 50:
                batch = YFinanceProvider.generate_synthetic_history(sym, days=120)
            candles = batch.candles

        sig = strategy.generate_signal(sym, candles)
        sig_dict = sig.to_dict()

        if sig.action.value == "BUY":
            buy_signals.append(sig_dict)
        elif sig.action.value == "SELL":
            sell_signals.append(sig_dict)
        else:
            hold_signals.append(sig_dict)

    return {
        "strategy": strategy.strategy_name,
        "timeframe": timeframe,
        "scanned_universe_size": len(symbols),
        "buy_signals_count": len(buy_signals),
        "sell_signals_count": len(sell_signals),
        "hold_signals_count": len(hold_signals),
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "hold_signals": hold_signals,
    }
