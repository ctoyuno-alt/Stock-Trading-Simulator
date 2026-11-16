"""
Volume Weighted Average Price (VWAP) Quantitative Engine.

Mathematical Formulation:
    Typical Price = (High + Low + Close) / 3.0
    Cumulative TP * Volume = sum(Typical Price_i * Volume_i)
    Cumulative Volume = sum(Volume_i)
    VWAP = Cumulative TP * Volume / Cumulative Volume

Intraday sessions: Resets at the start of each daily trading session.
Daily timeframe: Cumulative rolling or multi-session volume-weighted benchmark.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Sequence, Union


def calculate_vwap(
    highs: Sequence[Union[Decimal, float, int]],
    lows: Sequence[Union[Decimal, float, int]],
    closes: Sequence[Union[Decimal, float, int]],
    volumes: Sequence[int],
    timestamps: Optional[Sequence[datetime]] = None,
    reset_daily: bool = True,
) -> List[Optional[Decimal]]:
    """
    Calculates Volume Weighted Average Price (VWAP).
    If timestamps are provided and reset_daily is True, resets accumulation on calendar date changes.
    """
    n = len(closes)
    if not (len(highs) == len(lows) == len(closes) == len(volumes) == n):
        raise ValueError("Price and volume sequences must have identical lengths.")

    result: List[Optional[Decimal]] = [None] * n
    if n == 0:
        return result

    cum_tp_vol = Decimal("0.00")
    cum_vol = Decimal("0.00")
    prev_date = None

    for i in range(n):
        # Check session boundary reset
        if timestamps is not None and reset_daily:
            current_date = timestamps[i].date()
            if prev_date is not None and current_date != prev_date:
                cum_tp_vol = Decimal("0.00")
                cum_vol = Decimal("0.00")
            prev_date = current_date

        h = Decimal(str(highs[i]))
        l = Decimal(str(lows[i]))
        c = Decimal(str(closes[i]))
        v = Decimal(str(max(0, volumes[i])))

        typical_price = (h + l + c) / Decimal("3.0")
        cum_tp_vol += typical_price * v
        cum_vol += v

        if cum_vol > Decimal("0.00"):
            result[i] = (cum_tp_vol / cum_vol).quantize(Decimal("0.01"))
        else:
            # Fallback to typical price if zero volume
            result[i] = typical_price.quantize(Decimal("0.01"))

    return result
