"""
Relative Strength Index (RSI) Quantitative Engine.

Mathematical Formulation (J. Welles Wilder Jr. Smoothed RSI):
    Change_t = Price_t - Price_{t-1}
    Gain_t = max(Change_t, 0)
    Loss_t = max(-Change_t, 0)

    First AvgGain and AvgLoss (at t = period) = SMA of initial gains/losses.
    Subsequent:
        AvgGain_t = (AvgGain_{t-1} * (period - 1) + Gain_t) / period
        AvgLoss_t = (AvgLoss_{t-1} * (period - 1) + Loss_t) / period

    RS = AvgGain_t / AvgLoss_t
    RSI = 100.0 - (100.0 / (1.0 + RS))
"""

from decimal import Decimal
from typing import List, Optional, Sequence, Union


def calculate_rsi(
    prices: Sequence[Union[Decimal, float, int]],
    period: int = 14,
) -> List[Optional[float]]:
    """
    Calculates Wilder's Smoothed Relative Strength Index (RSI).
    Returns None for indices < period.
    Output is bounded in [0.0, 100.0].
    """
    n = len(prices)
    if period <= 0:
        raise ValueError(f"RSI period must be positive. Got: {period}")
    if n <= period:
        return [None] * n

    float_prices = [float(p) for p in prices]
    result: List[Optional[float]] = [None] * n

    gains = [0.0] * n
    losses = [0.0] * n

    for i in range(1, n):
        diff = float_prices[i] - float_prices[i - 1]
        if diff > 0:
            gains[i] = diff
        else:
            losses[i] = -diff

    # First average gain/loss at index = period (Wilder initial seed)
    avg_gain = sum(gains[1:period + 1]) / float(period)
    avg_loss = sum(losses[1:period + 1]) / float(period)

    if avg_loss == 0.0:
        result[period] = 100.0 if avg_gain > 0 else 50.0
    else:
        rs = avg_gain / avg_loss
        result[period] = round(100.0 - (100.0 / (1.0 + rs)), 2)

    # Wilder's Smoothing for subsequent bars
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / float(period)
        avg_loss = (avg_loss * (period - 1) + losses[i]) / float(period)

        if avg_loss == 0.0:
            result[i] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            result[i] = round(100.0 - (100.0 / (1.0 + rs)), 2)

    return result
