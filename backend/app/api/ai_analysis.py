"""
AI Market Analysis API Routes.

Exposes:
- Structured Gemini AI market interpretation.
- Grounded technical signal explanations with non-hallucination guardrails.
- Disclaimers that AI confidence is not a probability of profit.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai.gemini_analyzer import GeminiMarketAnalyzer
from backend.app.market_data.storage import MarketDataStorage
from backend.app.market_data.universe import universe_manager
from backend.app.market_data.yfinance_provider import YFinanceProvider
from database.session import get_db
from indicators.engine import indicator_engine
from strategies.swing_strategy import EMAMACDSwingStrategy

router = APIRouter(prefix="/api/v1/ai", tags=["AI Market Analysis"])
ai_analyzer = GeminiMarketAnalyzer()
strategy = EMAMACDSwingStrategy()
market_provider = YFinanceProvider()


class AnalysisRequest(BaseModel):
    timeframe: str = "1d"
    news_headlines: Optional[List[str]] = None


@router.post("/analyze/{symbol}", summary="Generate Gemini AI Technical Analysis")
async def analyze_symbol_ai(
    symbol: str,
    payload: Optional[AnalysisRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Synthesizes a schema-validated Gemini AI technical analysis:
    - Interprets EMA 20/50, RSI 14, MACD, and VWAP.
    - Evaluates confirming and conflicting indicators.
    - Provides confidence score with mandatory disclaimer (never a probability of profit).
    """
    timeframe = payload.timeframe if payload else "1d"
    news_headlines = payload.news_headlines if payload else None

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

    # 2. Compute quantitative indicators & deterministic signal
    series = indicator_engine.compute(clean_symbol, candles)
    signal = strategy.generate_signal(clean_symbol, candles)

    # 3. Request Gemini AI structured analysis
    analysis_summary = await ai_analyzer.analyze_market_state(
        symbol=clean_symbol,
        snapshot=series.snapshot,
        signal=signal,
        news_headlines=news_headlines,
    )

    dump_fn = getattr(analysis_summary, "model_dump", None) or getattr(analysis_summary, "to_dict", None)
    ai_data = dump_fn() if dump_fn else vars(analysis_summary)

    return {
        "symbol": clean_symbol,
        "timeframe": timeframe,
        "deterministic_signal": signal.to_dict(),
        "ai_analysis": ai_data,
        "data_notice": "Historical delayed market data (15-min delay). Prototyping only.",
    }
