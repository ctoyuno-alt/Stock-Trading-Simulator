"""
Exponential Moving Average (EMA) and Crossover Detection Engine.

Mathematical Formulation:
    Multiplier (alpha) = 2.0 / (period + 1.0)
    EMA_t = (Price_t * alpha) + (EMA_{t-1} * (1.0 - alpha))
    Initial seed at t = (period - 1) is the Simple Moving Average (SMA) of the first 'period' bars.
"""

from decimal import Decimal
from typing import List, Optional, Sequence, Union


def calculate_ema(
    prices: Sequence[Union[Decimal, float, int]],
    period: int,
) -> List[Optional[Decimal]]:
    """
    Calculates the Exponential Moving Average (EMA) for a price series.
    Returns None for bars prior to the warmup threshold (index < period - 1).
    """
    n = len(prices)
    if period <= 0:
        raise ValueError(f"EMA period must be positive. Got: {period}")
    if n < period:
        return [None] * n

    # Convert prices to Decimal for precision
    decimal_prices = [Decimal(str(p)) for p in prices]
    result: List[Optional[Decimal]] = [None] * n

    # 1. Initialize seed as SMA of the first 'period' values
    seed_sma = sum(decimal_prices[:period]) / Decimal(str(period))
    result[period - 1] = seed_sma.quantize(Decimal("0.01"))

    # 2. Vector recurrence
    alpha = Decimal("2.0") / Decimal(str(period + 1))
    one_minus_alpha = Decimal("1.0") - alpha

    current_ema = seed_sma
    for i in range(period, n):
        current_ema = (decimal_prices[i] * alpha) + (current_ema * one_minus_alpha)
        result[i] = current_ema.quantize(Decimal("0.01"))

    return result


def detect_crossover(
    fast_series: Sequence[Optional[Decimal]],
    slow_series: Sequence[Optional[Decimal]],
) -> List[Optional[str]]:
    """
    Detects moving average crossovers bar by bar:
    - 'GOLDEN_CROSS': Fast line crosses strictly above Slow line.
    - 'DEATH_CROSS': Fast line crosses strictly below Slow line.
    - None: No crossover on current bar.
    """
    n = min(len(fast_series), len(slow_series))
    crossovers: List[Optional[str]] = [None] * n

    for i in range(1, n):
        curr_fast = fast_series[i]
        curr_slow = slow_series[i]
        prev_fast = fast_series[i - 1]
        prev_slow = slow_series[i - 1]

        if None in (curr_fast, curr_slow, prev_fast, prev_slow):
            continue

        # Bullish: Previous fast was <= slow, and current fast is > slow
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            crossovers[i] = "GOLDEN_CROSS"
        # Bearish: Previous fast was >= slow, and current fast is < slow
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            crossovers[i] = "DEATH_CROSS"

    return crossovers
