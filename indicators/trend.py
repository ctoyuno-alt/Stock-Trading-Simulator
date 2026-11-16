"""
Moving Average Convergence Divergence (MACD) Quantitative Engine.

Mathematical Formulation:
    Fast EMA (default 12)
    Slow EMA (default 26)
    MACD Line = Fast EMA - Slow EMA
    Signal Line = 9-period EMA of MACD Line
    Histogram = MACD Line - Signal Line
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Sequence, Union
from indicators.moving_averages import calculate_ema


@dataclass
class MACDResult:
    macd_line: List[Optional[float]]
    signal_line: List[Optional[float]]
    histogram: List[Optional[float]]


def calculate_macd(
    prices: Sequence[Union[Decimal, float, int]],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MACDResult:
    """
    Computes MACD Line, Signal Line, and MACD Histogram.
    Returns None for bars before each component's warmup threshold:
    - MACD Line requires slow_period bars (26).
    - Signal Line requires slow_period + signal_period - 1 bars (34).
    """
    n = len(prices)
    if fast_period >= slow_period:
        raise ValueError(f"Fast period ({fast_period}) must be less than slow period ({slow_period}).")

    macd_line: List[Optional[float]] = [None] * n
    signal_line: List[Optional[float]] = [None] * n
    histogram: List[Optional[float]] = [None] * n

    if n < slow_period:
        return MACDResult(macd_line, signal_line, histogram)

    # 1. Calculate Fast and Slow EMAs
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)

    # 2. Calculate MACD Line = Fast EMA - Slow EMA
    valid_macd_indices: List[int] = []
    valid_macd_values: List[float] = []

    for i in range(slow_period - 1, n):
        f = fast_ema[i]
        s = slow_ema[i]
        if f is not None and s is not None:
            diff = float(f - s)
            macd_line[i] = round(diff, 4)
            valid_macd_indices.append(i)
            valid_macd_values.append(diff)

    # 3. Calculate Signal Line = EMA(MACD Line, signal_period)
    if len(valid_macd_values) >= signal_period:
        valid_signal = calculate_ema(valid_macd_values, signal_period)
        for sub_idx, sig_val in enumerate(valid_signal):
            if sig_val is not None:
                orig_idx = valid_macd_indices[sub_idx]
                sig_float = float(sig_val)
                signal_line[orig_idx] = round(sig_float, 4)
                # Histogram = MACD Line - Signal Line
                histogram[orig_idx] = round(macd_line[orig_idx] - sig_float, 4)

    return MACDResult(
        macd_line=macd_line,
        signal_line=signal_line,
        histogram=histogram,
    )
