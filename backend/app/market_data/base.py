"""
Abstract Base Market Data Provider Interface.

Design Goals:
- Broker-agnostic architecture: completely decoupled from specific data sources.
- Strict data transparency: clear timestamping, delay labeling (e.g. 15-min delayed vs historical EOD).
- Data integrity & validation: automatic detection of anomalies (negative prices, high < low, missing bars, staleness).
- Clean conversion interfaces for quantitative processing (pandas DataFrame & typed models).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

IST_ZONE = ZoneInfo("Asia/Kolkata")


@dataclass
class Candle:
    """Individual OHLCV candle with optional VWAP."""
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    vwap: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": self.volume,
            "vwap": float(self.vwap) if self.vwap is not None else None,
        }


@dataclass
class DataValidationResult:
    """Audit report of data quality and anomalies."""
    is_valid: bool
    total_candles: int
    anomalies_detected: List[str] = field(default_factory=list)
    has_missing_candles: bool = False
    missing_intervals: List[str] = field(default_factory=list)
    staleness_seconds: float = 0.0
    is_stale: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_candles": self.total_candles,
            "anomalies_detected": self.anomalies_detected,
            "has_missing_candles": self.has_missing_candles,
            "missing_intervals": self.missing_intervals,
            "staleness_seconds": round(self.staleness_seconds, 2),
            "is_stale": self.is_stale,
        }


@dataclass
class MarketDataBatch:
    """Standardized container for a series of historical or intraday candles."""
    symbol: str
    exchange: str
    timeframe: str  # e.g., "1d", "1h", "15m"
    candles: List[Candle]
    provider: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_delayed: bool = True
    delay_minutes: int = 15
    data_source_disclaimer: str = (
        "DATA NOTICE: Historical prototyping data. Not verified real-time exchange feed. "
        "Do not use for live financial order execution."
    )
    validation: Optional[DataValidationResult] = None

    @property
    def start_time(self) -> Optional[datetime]:
        return self.candles[0].timestamp if self.candles else None

    @property
    def end_time(self) -> Optional[datetime]:
        return self.candles[-1].timestamp if self.candles else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timeframe": self.timeframe,
            "count": len(self.candles),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "provider": self.provider,
            "fetched_at": self.fetched_at.isoformat(),
            "is_delayed": self.is_delayed,
            "delay_minutes": self.delay_minutes,
            "data_source_disclaimer": self.data_source_disclaimer,
            "validation": self.validation.to_dict() if self.validation else None,
            "candles": [c.to_dict() for c in self.candles],
        }


class MarketDataProvider(ABC):
    """Abstract interface for all market data ingestion sources."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the data provider (e.g., 'yfinance', 'kite', 'angelone')."""
        pass

    @abstractmethod
    def fetch_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        period: Optional[str] = "1y",
    ) -> MarketDataBatch:
        """Fetches historical OHLCV data for the given symbol."""
        pass

    @abstractmethod
    def fetch_latest_quote(self, symbol: str) -> Candle:
        """Fetches the latest available candle/quote for the symbol."""
        pass

    def validate_batch(
        self,
        batch: MarketDataBatch,
        max_staleness_hours: float = 72.0,
    ) -> DataValidationResult:
        """
        Performs quantitative integrity validation on candle batches:
        1. Non-negative prices: Open, High, Low, Close must be > 0.
        2. Candle price hierarchy: High must be >= max(Open, Close) and Low <= min(Open, Close).
        3. Volume: Volume must be non-negative (>= 0).
        4. Chronological order: Timestamps must be strictly ascending with no duplicates.
        5. Staleness check: Compares the last candle timestamp against current time.
        """
        anomalies: List[str] = []
        candles = batch.candles

        if not candles:
            return DataValidationResult(
                is_valid=False,
                total_candles=0,
                anomalies_detected=["Batch contains zero candles."],
                has_missing_candles=True,
                is_stale=True,
            )

        prev_ts: Optional[datetime] = None

        for idx, candle in enumerate(candles):
            # 1. Price positivity
            if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
                anomalies.append(f"Row {idx} ({candle.timestamp.isoformat()}): Non-positive price detected (O={candle.open}, H={candle.high}, L={candle.low}, C={candle.close}).")

            # 2. Price hierarchy
            if candle.high < candle.low:
                anomalies.append(f"Row {idx} ({candle.timestamp.isoformat()}): High ({candle.high}) is lower than Low ({candle.low}).")
            if candle.high < candle.open or candle.high < candle.close:
                anomalies.append(f"Row {idx} ({candle.timestamp.isoformat()}): High ({candle.high}) is less than Open ({candle.open}) or Close ({candle.close}).")
            if candle.low > candle.open or candle.low > candle.close:
                anomalies.append(f"Row {idx} ({candle.timestamp.isoformat()}): Low ({candle.low}) is greater than Open ({candle.open}) or Close ({candle.close}).")

            # 3. Volume
            if candle.volume < 0:
                anomalies.append(f"Row {idx} ({candle.timestamp.isoformat()}): Negative volume detected ({candle.volume}).")

            # 4. Strict chronological order
            if prev_ts is not None:
                if candle.timestamp <= prev_ts:
                    anomalies.append(f"Row {idx}: Timestamp {candle.timestamp.isoformat()} is not strictly after previous timestamp {prev_ts.isoformat()}.")
            prev_ts = candle.timestamp

        # 5. Staleness calculation
        latest_ts = candles[-1].timestamp
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        staleness_seconds = max(0.0, (now_utc - latest_ts.astimezone(timezone.utc)).total_seconds())
        is_stale = staleness_seconds > (max_staleness_hours * 3600.0)

        is_valid = len(anomalies) == 0

        validation = DataValidationResult(
            is_valid=is_valid,
            total_candles=len(candles),
            anomalies_detected=anomalies,
            has_missing_candles=False,
            staleness_seconds=staleness_seconds,
            is_stale=is_stale,
        )
        batch.validation = validation
        return validation
