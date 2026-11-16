"""
Base Definitions, Data Structures, and Exceptions for Quantitative Indicators.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import enum
from typing import Any, Dict, List, Optional


class InsufficientDataError(ValueError):
    """Raised when historical data does not meet the minimum warmup threshold for indicator calculation."""
    pass


class TrendRegime(str, enum.Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class MomentumRegime(str, enum.Enum):
    OVERSOLD = "OVERSOLD"                      # RSI < 30
    OVERBOUGHT = "OVERBOUGHT"                  # RSI > 70
    BULLISH_MOMENTUM = "BULLISH_MOMENTUM"      # 50 <= RSI <= 70
    BEARISH_MOMENTUM = "BEARISH_MOMENTUM"      # 30 <= RSI < 50
    NEUTRAL = "NEUTRAL"


class MACDState(str, enum.Enum):
    BULLISH_CROSSOVER = "BULLISH_CROSSOVER"  # MACD crossed above Signal on current bar
    BEARISH_CROSSOVER = "BEARISH_CROSSOVER"  # MACD crossed below Signal on current bar
    BULLISH_ABOVE = "BULLISH_ABOVE"          # MACD > Signal Line
    BEARISH_BELOW = "BEARISH_BELOW"          # MACD < Signal Line
    NEUTRAL = "NEUTRAL"


@dataclass
class IndicatorSnapshot:
    """Latest computed quantitative indicator readings and market regime flags."""
    timestamp: datetime
    symbol: str
    close_price: Decimal

    # Exponential Moving Averages
    ema_fast_20: Optional[Decimal]
    ema_slow_50: Optional[Decimal]
    ema_trend_regime: TrendRegime
    ema_spread_pct: Optional[float]  # (EMA20 - EMA50) / EMA50 * 100

    # Relative Strength Index
    rsi_14: Optional[float]
    rsi_regime: MomentumRegime

    # Moving Average Convergence Divergence
    macd_line: Optional[float]
    macd_signal: Optional[float]
    macd_histogram: Optional[float]
    macd_state: MACDState

    # Volume Weighted Average Price
    vwap: Optional[Decimal]
    price_to_vwap_pct: Optional[float]  # (Close - VWAP) / VWAP * 100

    # Warmup and Data Integrity Audit
    bars_available: int
    min_bars_required: int
    is_warmed_up: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "close_price": float(self.close_price),
            "ema_fast_20": float(self.ema_fast_20) if self.ema_fast_20 is not None else None,
            "ema_slow_50": float(self.ema_slow_50) if self.ema_slow_50 is not None else None,
            "ema_trend_regime": self.ema_trend_regime.value,
            "ema_spread_pct": round(self.ema_spread_pct, 4) if self.ema_spread_pct is not None else None,
            "rsi_14": round(self.rsi_14, 2) if self.rsi_14 is not None else None,
            "rsi_regime": self.rsi_regime.value,
            "macd_line": round(self.macd_line, 4) if self.macd_line is not None else None,
            "macd_signal": round(self.macd_signal, 4) if self.macd_signal is not None else None,
            "macd_histogram": round(self.macd_histogram, 4) if self.macd_histogram is not None else None,
            "macd_state": self.macd_state.value,
            "vwap": float(self.vwap) if self.vwap is not None else None,
            "price_to_vwap_pct": round(self.price_to_vwap_pct, 4) if self.price_to_vwap_pct is not None else None,
            "bars_available": self.bars_available,
            "min_bars_required": self.min_bars_required,
            "is_warmed_up": self.is_warmed_up,
        }


@dataclass
class IndicatorTimeSeries:
    """Complete time series arrays for indicators, aligned with input candles."""
    symbol: str
    timestamps: List[datetime]
    closes: List[Decimal]
    ema_fast: List[Optional[Decimal]]
    ema_slow: List[Optional[Decimal]]
    rsi: List[Optional[float]]
    macd_line: List[Optional[float]]
    macd_signal: List[Optional[float]]
    macd_hist: List[Optional[float]]
    vwap: List[Optional[Decimal]]
    snapshot: IndicatorSnapshot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "count": len(self.timestamps),
            "timestamps": [ts.isoformat() for ts in self.timestamps],
            "closes": [float(c) for c in self.closes],
            "ema_fast": [float(e) if e is not None else None for e in self.ema_fast],
            "ema_slow": [float(e) if e is not None else None for e in self.ema_slow],
            "rsi": [round(r, 2) if r is not None else None for r in self.rsi],
            "macd_line": [round(m, 4) if m is not None else None for m in self.macd_line],
            "macd_signal": [round(s, 4) if s is not None else None for s in self.macd_signal],
            "macd_hist": [round(h, 4) if h is not None else None for h in self.macd_hist],
            "vwap": [float(v) if v is not None else None for v in self.vwap],
            "latest_snapshot": self.snapshot.to_dict(),
        }
