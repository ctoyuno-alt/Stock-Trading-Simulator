"""
Unified Technical Indicator Engine.

Orchestrates:
- Vectorized execution of EMA 20, EMA 50, RSI 14, MACD (12, 26, 9), and VWAP.
- Strict warmup validation (EMA 50 and MACD requirements).
- Market regime classification (Trend, Momentum, and Crossover states).
- Produces full time series aligned with candles and current bar snapshot.
"""

from decimal import Decimal
import logging
from typing import List, Optional, Sequence
from backend.app.market_data.base import Candle
from indicators.base import (
    IndicatorSnapshot,
    IndicatorTimeSeries,
    InsufficientDataError,
    MACDState,
    MomentumRegime,
    TrendRegime,
)
from indicators.moving_averages import calculate_ema
from indicators.momentum import calculate_rsi
from indicators.trend import calculate_macd
from indicators.volume import calculate_vwap

logger = logging.getLogger(__name__)

# Minimum bars required for mathematical convergence of 50-period EMA and MACD
MIN_WARMUP_BARS = 50


class TechnicalIndicatorEngine:
    """Unified quantitative engine computing technical indicators over candle bars."""

    def __init__(
        self,
        ema_fast_period: int = 20,
        ema_slow_period: int = 50,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
    ) -> None:
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

    def compute(
        self,
        symbol: str,
        candles: Sequence[Candle],
        require_full_warmup: bool = False,
    ) -> IndicatorTimeSeries:
        """
        Computes all technical indicators over the given candle sequence.
        
        Args:
            symbol: Ticker symbol (e.g., 'RELIANCE').
            candles: List of Candle dataclasses sorted chronologically.
            require_full_warmup: If True, raises InsufficientDataError when len(candles) < 50.
        """
        n = len(candles)
        if require_full_warmup and n < MIN_WARMUP_BARS:
            raise InsufficientDataError(
                f"Insufficient data for {symbol}: provided {n} bars, but minimum warmup is {MIN_WARMUP_BARS} bars."
            )

        if n == 0:
            raise InsufficientDataError(f"Cannot compute indicators on empty candle sequence for {symbol}.")

        timestamps = [c.timestamp for c in candles]
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]

        # 1. Exponential Moving Averages (EMA 20 & 50)
        ema_fast = calculate_ema(closes, self.ema_fast_period)
        ema_slow = calculate_ema(closes, self.ema_slow_period)

        # 2. Relative Strength Index (RSI 14)
        rsi = calculate_rsi(closes, self.rsi_period)

        # 3. MACD (12, 26, 9)
        macd = calculate_macd(closes, self.macd_fast, self.macd_slow, self.macd_signal)

        # 4. Volume Weighted Average Price (VWAP)
        vwap = calculate_vwap(highs, lows, closes, volumes, timestamps, reset_daily=True)

        # 5. Extract latest values for Snapshot
        latest_close = closes[-1]
        latest_ts = timestamps[-1]
        latest_ema_fast = ema_fast[-1]
        latest_ema_slow = ema_slow[-1]
        latest_rsi = rsi[-1]
        latest_macd_line = macd.macd_line[-1]
        latest_macd_sig = macd.signal_line[-1]
        latest_macd_hist = macd.histogram[-1]
        latest_vwap = vwap[-1]

        # Trend Regime Classification
        if latest_ema_fast is not None and latest_ema_slow is not None:
            if latest_ema_fast > latest_ema_slow:
                ema_trend = TrendRegime.BULLISH
            elif latest_ema_fast < latest_ema_slow:
                ema_trend = TrendRegime.BEARISH
            else:
                ema_trend = TrendRegime.NEUTRAL
            ema_spread = float((latest_ema_fast - latest_ema_slow) / latest_ema_slow * Decimal("100.0"))
        else:
            ema_trend = TrendRegime.NEUTRAL
            ema_spread = None

        # Momentum Regime Classification (RSI)
        if latest_rsi is not None:
            if latest_rsi >= 70.0:
                rsi_regime = MomentumRegime.OVERBOUGHT
            elif latest_rsi <= 30.0:
                rsi_regime = MomentumRegime.OVERSOLD
            elif 50.0 <= latest_rsi < 70.0:
                rsi_regime = MomentumRegime.BULLISH_MOMENTUM
            else:
                rsi_regime = MomentumRegime.BEARISH_MOMENTUM
        else:
            rsi_regime = MomentumRegime.NEUTRAL

        # MACD State Classification
        prev_hist = macd.histogram[-2] if n >= 2 else None
        if latest_macd_hist is not None:
            if prev_hist is not None:
                if prev_hist <= 0.0 and latest_macd_hist > 0.0:
                    macd_state = MACDState.BULLISH_CROSSOVER
                elif prev_hist >= 0.0 and latest_macd_hist < 0.0:
                    macd_state = MACDState.BEARISH_CROSSOVER
                elif latest_macd_hist > 0.0:
                    macd_state = MACDState.BULLISH_ABOVE
                else:
                    macd_state = MACDState.BEARISH_BELOW
            else:
                macd_state = MACDState.BULLISH_ABOVE if latest_macd_hist > 0 else MACDState.BEARISH_BELOW
        else:
            macd_state = MACDState.NEUTRAL

        # VWAP Percentage Distance
        if latest_vwap is not None and latest_vwap > Decimal("0.00"):
            price_to_vwap = float((latest_close - latest_vwap) / latest_vwap * Decimal("100.0"))
        else:
            price_to_vwap = None

        is_warmed_up = n >= MIN_WARMUP_BARS and latest_ema_slow is not None and latest_macd_hist is not None

        snapshot = IndicatorSnapshot(
            timestamp=latest_ts,
            symbol=symbol.upper(),
            close_price=latest_close,
            ema_fast_20=latest_ema_fast,
            ema_slow_50=latest_ema_slow,
            ema_trend_regime=ema_trend,
            ema_spread_pct=ema_spread,
            rsi_14=latest_rsi,
            rsi_regime=rsi_regime,
            macd_line=latest_macd_line,
            macd_signal=latest_macd_sig,
            macd_histogram=latest_macd_hist,
            macd_state=macd_state,
            vwap=latest_vwap,
            price_to_vwap_pct=price_to_vwap,
            bars_available=n,
            min_bars_required=MIN_WARMUP_BARS,
            is_warmed_up=is_warmed_up,
        )

        return IndicatorTimeSeries(
            symbol=symbol.upper(),
            timestamps=timestamps,
            closes=closes,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            macd_line=macd.macd_line,
            macd_signal=macd.signal_line,
            macd_hist=macd.histogram,
            vwap=vwap,
            snapshot=snapshot,
        )


# Global indicator engine singleton
indicator_engine = TechnicalIndicatorEngine()
