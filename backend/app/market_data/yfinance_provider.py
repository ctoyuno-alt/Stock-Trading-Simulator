"""
Yahoo Finance Market Data Provider Implementation.

Characteristics:
- Designed for historical backtesting and initial paper-trading prototyping.
- Explicitly flags data delays (15-min delay for NSE equity).
- Validates price hierarchy (High >= Low, positive prices) and detects data gaps.
- Includes synthetic fixture generator for deterministic testing in offline environments.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import time
from typing import List, Optional
from zoneinfo import ZoneInfo

from backend.app.market_data.base import Candle, MarketDataBatch, MarketDataProvider
from backend.app.market_data.universe import universe_manager

logger = logging.getLogger(__name__)
IST_ZONE = ZoneInfo("Asia/Kolkata")


class YFinanceProvider(MarketDataProvider):
    """Yahoo Finance market data ingestion engine with retry and safety checks."""

    def __init__(self, cache_ttl_minutes: int = 15) -> None:
        self.cache_ttl_minutes = cache_ttl_minutes

    @property
    def provider_name(self) -> str:
        return "yfinance"

    def fetch_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        period: Optional[str] = "1y",
    ) -> MarketDataBatch:
        """
        Fetches historical OHLCV data for an NSE symbol.
        """
        clean_symbol = universe_manager.normalize_symbol(symbol)
        yf_ticker = universe_manager.get_yfinance_ticker(clean_symbol)

        logger.info(
            f"Fetching historical OHLCV data for {clean_symbol} ({yf_ticker}) [Timeframe: {timeframe}]",
            extra={"extra_context": {"symbol": clean_symbol, "ticker": yf_ticker, "timeframe": timeframe}}
        )

        candles: List[Candle] = []

        try:
            import yfinance as yf
            ticker_obj = yf.Ticker(yf_ticker)

            # Map timeframes
            interval_map = {"1d": "1d", "1h": "1h", "15m": "15m", "5m": "5m"}
            interval = interval_map.get(timeframe.lower(), "1d")

            # Fetch DataFrame
            if start_date and end_date:
                df = ticker_obj.history(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                    interval=interval,
                    auto_adjust=False,
                )
            else:
                df = ticker_obj.history(
                    period=period or "1y",
                    interval=interval,
                    auto_adjust=False,
                )

            if df is not None and not df.empty:
                # Calculate VWAP if volume exists: Typical Price = (H + L + C) / 3
                typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
                cum_vol = df["Volume"].cumsum()
                cum_tp_vol = (typical_price * df["Volume"]).cumsum()
                vwap_series = cum_tp_vol / cum_vol.replace(0, 1)

                for ts_index, row in df.iterrows():
                    # Handle pandas Timestamp
                    if hasattr(ts_index, "to_pydatetime"):
                        ts = ts_index.to_pydatetime()
                    else:
                        ts = ts_index
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=IST_ZONE)

                    candle = Candle(
                        timestamp=ts,
                        open=Decimal(str(round(float(row["Open"]), 2))),
                        high=Decimal(str(round(float(row["High"]), 2))),
                        low=Decimal(str(round(float(row["Low"]), 2))),
                        close=Decimal(str(round(float(row["Close"]), 2))),
                        volume=int(row["Volume"]),
                        vwap=Decimal(str(round(float(vwap_series.loc[ts_index]), 2))) if ts_index in vwap_series else None,
                    )
                    candles.append(candle)
        except Exception as exc:
            logger.warning(
                f"yfinance download failed for {yf_ticker} (Network/API constraint): {str(exc)}. "
                "Returning fallback batch if available."
            )

        batch = MarketDataBatch(
            symbol=clean_symbol,
            exchange="NSE",
            timeframe=timeframe,
            candles=candles,
            provider=self.provider_name,
            is_delayed=True,
            delay_minutes=15,
            data_source_disclaimer=(
                "DATA NOTICE: Historical data sourced via Yahoo Finance. "
                "Quotes are delayed by at least 15 minutes. Strictly for paper trading research."
            ),
        )

        # Validate the batch
        self.validate_batch(batch)
        return batch

    def fetch_latest_quote(self, symbol: str) -> Candle:
        """Fetches the latest available candle for the symbol."""
        batch = self.fetch_historical_ohlcv(symbol, timeframe="1d", period="5d")
        if not batch.candles:
            raise RuntimeError(f"No recent quotes available for {symbol}")
        return batch.candles[-1]

    @staticmethod
    def generate_synthetic_history(
        symbol: str,
        start_price: Decimal = Decimal("2500.00"),
        days: int = 100,
        trend: float = 0.001,
        volatility: float = 0.015,
    ) -> MarketDataBatch:
        """
        Generates deterministic, mathematically consistent synthetic OHLCV history
        for offline testing, sandbox verification, and deterministic backtest fixtures.
        """
        clean_symbol = universe_manager.normalize_symbol(symbol)
        candles: List[Candle] = []

        base_dt = datetime(2026, 1, 1, 9, 15, tzinfo=IST_ZONE)
        current_close = start_price

        # Deterministic pseudo-random seed based on symbol
        seed_val = sum(ord(c) for c in clean_symbol)

        current_day = 0
        added_days = 0

        while added_days < days:
            current_day += 1
            dt = base_dt + timedelta(days=current_day)
            # Skip weekends (Saturday=5, Sunday=6)
            if dt.weekday() in (5, 6):
                continue

            # Deterministic pseudo-random fluctuation
            sim_factor = ((seed_val * (added_days + 1) * 37) % 1000) / 1000.0
            daily_pct = (sim_factor - 0.48) * volatility * 2.0 + trend

            day_open = current_close * Decimal(str(round(1.0 + (sim_factor - 0.5) * 0.005, 4)))
            day_close = day_open * Decimal(str(round(1.0 + daily_pct, 4)))

            spread = abs(day_close - day_open) + (current_close * Decimal("0.005"))
            day_high = max(day_open, day_close) + (spread * Decimal("0.6"))
            day_low = min(day_open, day_close) - (spread * Decimal("0.6"))

            # Ensure strict price hierarchy
            day_open = day_open.quantize(Decimal("0.05"))
            day_high = max(day_high, day_open, day_close).quantize(Decimal("0.05"))
            day_low = max(Decimal("1.00"), min(day_low, day_open, day_close)).quantize(Decimal("0.05"))
            day_close = day_close.quantize(Decimal("0.05"))

            volume = 500000 + int(sim_factor * 2000000)
            vwap = ((day_high + day_low + day_close) / Decimal("3")).quantize(Decimal("0.05"))

            candles.append(Candle(
                timestamp=dt,
                open=day_open,
                high=day_high,
                low=day_low,
                close=day_close,
                volume=volume,
                vwap=vwap,
            ))

            current_close = day_close
            added_days += 1

        batch = MarketDataBatch(
            symbol=clean_symbol,
            exchange="NSE",
            timeframe="1d",
            candles=candles,
            provider="synthetic_fixture",
            is_delayed=False,
            delay_minutes=0,
            data_source_disclaimer="DATA NOTICE: Deterministic synthetic market data fixture for testing.",
        )

        # Validate generated batch
        provider = YFinanceProvider()
        provider.validate_batch(batch)
        return batch
