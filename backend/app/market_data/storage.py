"""
Market Data Persistence and Retrieval Storage Service.

Handles:
- Upserting OHLCV candles to PostgreSQL (`MarketCandleModel`).
- Querying historical candles with date filtering and timeframe constraints.
- Bidirectional conversion between database entities, Candle dataclasses, and pandas DataFrames.
"""

from datetime import datetime
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from backend.app.market_data.base import Candle, MarketDataBatch

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.ext.asyncio import AsyncSession
    from database.models import MarketCandleModel
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    AsyncSession = Any  # type: ignore


class MarketDataStorage:
    """Manages asynchronous database persistence for market candle time series."""

    @staticmethod
    async def save_candles(
        session: AsyncSession,
        batch: MarketDataBatch,
    ) -> int:
        """
        Saves candles from a MarketDataBatch to the database.
        Uses PostgreSQL ON CONFLICT DO UPDATE for idempotency.
        """
        if not HAS_SQLALCHEMY:
            raise ImportError("SQLAlchemy is required for database persistence. Run within Docker container or install requirements.")

        if not batch.candles:
            return 0

        records = [
            {
                "symbol": batch.symbol,
                "exchange": batch.exchange,
                "timeframe": batch.timeframe,
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "vwap": candle.vwap,
                "provider": batch.provider,
            }
            for candle in batch.candles
        ]

        # Use PostgreSQL upsert if on Postgres, or standard loop with merge for SQLite
        try:
            stmt = pg_insert(MarketCandleModel).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "timestamp"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "vwap": stmt.excluded.vwap,
                    "provider": stmt.excluded.provider,
                },
            )
            await session.execute(stmt)
            await session.commit()
            return len(records)
        except Exception:
            # Fallback for SQLite / generic dialects during tests
            await session.rollback()
            count = 0
            for r in records:
                existing = await session.execute(
                    select(MarketCandleModel).where(
                        MarketCandleModel.symbol == r["symbol"],
                        MarketCandleModel.timeframe == r["timeframe"],
                        MarketCandleModel.timestamp == r["timestamp"],
                    )
                )
                candle_obj = existing.scalar_one_or_none()
                if candle_obj:
                    candle_obj.open = r["open"]
                    candle_obj.high = r["high"]
                    candle_obj.low = r["low"]
                    candle_obj.close = r["close"]
                    candle_obj.volume = r["volume"]
                    candle_obj.vwap = r["vwap"]
                    candle_obj.provider = r["provider"]
                else:
                    new_obj = MarketCandleModel(**r)
                    session.add(new_obj)
                count += 1
            await session.commit()
            return count

    @staticmethod
    async def get_candles(
        session: AsyncSession,
        symbol: str,
        timeframe: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Candle]:
        """Queries stored historical candles in chronological order."""
        if not HAS_SQLALCHEMY:
            raise ImportError("SQLAlchemy is required for database queries. Run within Docker container or install requirements.")

        stmt = select(MarketCandleModel).where(
            MarketCandleModel.symbol == symbol.upper(),
            MarketCandleModel.timeframe == timeframe,
        )

        if start_date:
            stmt = stmt.where(MarketCandleModel.timestamp >= start_date)
        if end_date:
            stmt = stmt.where(MarketCandleModel.timestamp <= end_date)

        stmt = stmt.order_by(MarketCandleModel.timestamp.asc()).limit(limit)
        result = await session.execute(stmt)
        models = result.scalars().all()

        return [
            Candle(
                timestamp=m.timestamp,
                open=Decimal(str(m.open)),
                high=Decimal(str(m.high)),
                low=Decimal(str(m.low)),
                close=Decimal(str(m.close)),
                volume=m.volume,
                vwap=Decimal(str(m.vwap)) if m.vwap is not None else None,
            )
            for m in models
        ]

    @staticmethod
    def candles_to_dataframe(candles: List[Candle]) -> Any:
        """Converts candle list into standard pandas DataFrame indexed by timestamp."""
        if not HAS_PANDAS:
            return [
                {
                    "timestamp": c.timestamp,
                    "open": float(c.open),
                    "high": float(c.high),
                    "low": float(c.low),
                    "close": float(c.close),
                    "volume": int(c.volume),
                    "vwap": float(c.vwap) if c.vwap is not None else None,
                }
                for c in candles
            ]

        if not candles:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "vwap"])

        data = [
            {
                "timestamp": c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": int(c.volume),
                "vwap": float(c.vwap) if c.vwap is not None else None,
            }
            for c in candles
        ]
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        return df
