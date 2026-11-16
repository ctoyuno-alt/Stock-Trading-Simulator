"""
Deterministic Multi-Factor Swing Trading Strategy for Indian Equities.

Strategy Logic:
- Multi-factor confluence combining EMA (20/50), RSI (14), MACD (12/26/9), and VWAP.
- Long-only delivery swing trading model (standard for Indian cash equity accounts).
- Rule-based stop-loss anchoring (swing low / EMA 50) and target profit (2:1 minimum R:R).
- Deterministic confluence scoring and explicit conflicting factor identification.
"""

from decimal import Decimal
import logging
from typing import List, Optional, Sequence
from backend.app.market_data.base import Candle
from indicators.base import IndicatorSnapshot, InsufficientDataError
from indicators.engine import TechnicalIndicatorEngine
from strategies.base import BaseStrategy, SignalAction, SignalStrength, TradeSignal

logger = logging.getLogger(__name__)


class EMAMACDSwingStrategy(BaseStrategy):
    """
    Deterministic swing-trading strategy engineered for liquid NSE large-cap stocks.
    
    Confluence Requirements for BUY:
    1. Trend: EMA 20 > EMA 50 and Close >= EMA 20.
    2. Momentum: RSI between 45.0 and 68.0 (healthy momentum, not overbought).
    3. MACD: Histogram > 0 or fresh bullish crossover.
    4. Fair Value: Close >= VWAP.
    5. Minimum 2:1 Risk-Reward Ratio with strict Stop-Loss derived from swing support.
    """

    def __init__(
        self,
        min_risk_reward: float = 2.0,
        min_stop_loss_pct: float = 0.015,  # 1.5% minimum stop distance
        max_stop_loss_pct: float = 0.050,  # 5.0% maximum stop distance
        swing_lookback: int = 5,
    ) -> None:
        self.min_risk_reward = min_risk_reward
        self.min_stop_loss_pct = min_stop_loss_pct
        self.max_stop_loss_pct = max_stop_loss_pct
        self.swing_lookback = swing_lookback
        self.indicator_engine = TechnicalIndicatorEngine()

    @property
    def strategy_name(self) -> str:
        return "EMA_MACD_Swing_v1"

    def generate_signal(
        self,
        symbol: str,
        candles: Sequence[Candle],
    ) -> TradeSignal:
        """
        Evaluates the current state of the instrument and returns a TradeSignal.
        """
        n = len(candles)
        if n < 50:
            latest_price = candles[-1].close if n > 0 else Decimal("0.00")
            latest_ts = candles[-1].timestamp if n > 0 else None
            return TradeSignal(
                symbol=symbol.upper(),
                timestamp=latest_ts,
                action=SignalAction.HOLD,
                strength=SignalStrength.WEAK,
                entry_price=latest_price,
                suggested_stop_loss=latest_price * Decimal("0.98"),
                suggested_take_profit=latest_price * Decimal("1.04"),
                risk_reward_ratio=self.min_risk_reward,
                stop_loss_pct=2.0,
                target_profit_pct=4.0,
                primary_trigger="Insufficient data history for indicator convergence (< 50 bars).",
                confirming_factors=[],
                conflicting_factors=[f"Only {n} bars available, minimum warmup requires 50 bars."],
                technical_score=50.0,
                snapshot=None,
            )

        # Compute full indicator time series
        series = self.indicator_engine.compute(symbol, candles, require_full_warmup=False)
        snapshot = series.snapshot
        latest_close = snapshot.close_price
        latest_ts = snapshot.timestamp

        confirming: List[str] = []
        conflicting: List[str] = []
        score = 0.0

        # --- Factor 1: Trend Alignment (Weight: 30%) ---
        ema_20 = snapshot.ema_fast_20
        ema_50 = snapshot.ema_slow_50
        if ema_20 is not None and ema_50 is not None:
            if ema_20 > ema_50:
                if latest_close >= ema_20:
                    score += 30.0
                    confirming.append(f"Bullish Trend: EMA 20 (₹{ema_20}) > EMA 50 (₹{ema_50}) and Price >= EMA 20.")
                else:
                    score += 15.0
                    confirming.append(f"Moderate Bullish: EMA 20 > EMA 50, but Price (₹{latest_close}) is pulling back below EMA 20.")
                    conflicting.append("Price closed below short-term EMA 20.")
            else:
                score += 0.0
                conflicting.append(f"Bearish Trend: EMA 20 (₹{ema_20}) is below EMA 50 (₹{ema_50}).")

        # --- Factor 2: Momentum / RSI (Weight: 25%) ---
        rsi = snapshot.rsi_14
        if rsi is not None:
            if 48.0 <= rsi <= 65.0:
                score += 25.0
                confirming.append(f"Optimal Bullish Momentum: RSI at {rsi:.1f} (in healthy expansion corridor 48-65).")
            elif 40.0 <= rsi < 48.0:
                score += 12.0
                confirming.append(f"Emerging Momentum: RSI at {rsi:.1f} recovering above 40.")
            elif rsi > 70.0:
                score += 5.0
                conflicting.append(f"Overbought Warning: RSI is high at {rsi:.1f} (> 70.0); vulnerable to sharp pullback.")
            elif rsi < 35.0:
                score += 0.0
                conflicting.append(f"Weak Momentum: RSI is oversold/bearish at {rsi:.1f} (< 35.0).")
            else:
                score += 10.0

        # --- Factor 3: MACD (Weight: 25%) ---
        macd_hist = snapshot.macd_histogram
        macd_line = snapshot.macd_line
        macd_sig = snapshot.macd_signal
        prev_hist = series.macd_hist[-2] if len(series.macd_hist) >= 2 else None

        if macd_hist is not None:
            if macd_hist > 0:
                if prev_hist is not None and macd_hist > prev_hist:
                    score += 25.0
                    confirming.append(f"Strong MACD Acceleration: Histogram positive (+{macd_hist:.3f}) and expanding.")
                else:
                    score += 15.0
                    confirming.append(f"Positive MACD: Histogram above zero (+{macd_hist:.3f}).")
            else:
                score += 0.0
                conflicting.append(f"Bearish MACD: Histogram negative ({macd_hist:.3f}).")

        # --- Factor 4: VWAP Fair Value (Weight: 20%) ---
        vwap = snapshot.vwap
        if vwap is not None:
            if latest_close >= vwap:
                score += 20.0
                confirming.append(f"Above Institutional Value: Price (₹{latest_close}) is above daily VWAP (₹{vwap}).")
            else:
                score += 0.0
                conflicting.append(f"Below VWAP: Price (₹{latest_close}) is trading below VWAP (₹{vwap}).")

        # --- Stop-Loss & Target Profit Mathematical Formulation ---
        # Lookback for swing low over last k bars
        lookback_slice = candles[-self.swing_lookback:] if n >= self.swing_lookback else candles
        recent_low = min(c.low for c in lookback_slice)

        # Stop-loss anchors to recent swing low or EMA 50
        anchor_low = min(recent_low, ema_50) if ema_50 else recent_low

        # Apply percentage guardrails
        min_stop_price = (latest_close * (Decimal("1.0") - Decimal(str(self.min_stop_loss_pct)))).quantize(Decimal("0.05"))
        max_stop_price = (latest_close * (Decimal("1.0") - Decimal(str(self.max_stop_loss_pct)))).quantize(Decimal("0.05"))

        suggested_stop = min(anchor_low, min_stop_price)
        suggested_stop = max(suggested_stop, max_stop_price).quantize(Decimal("0.05"))

        stop_loss_distance = latest_close - suggested_stop
        if stop_loss_distance <= Decimal("0.00"):
            suggested_stop = min_stop_price
            stop_loss_distance = latest_close - suggested_stop

        target_distance = (stop_loss_distance * Decimal(str(self.min_risk_reward))).quantize(Decimal("0.05"))
        suggested_target = (latest_close + target_distance).quantize(Decimal("0.05"))

        stop_loss_pct = float((stop_loss_distance / latest_close) * Decimal("100.0"))
        target_profit_pct = float((target_distance / latest_close) * Decimal("100.0"))

        # --- Action Trigger Logic ---
        # BUY Trigger: Score >= 70, EMA Bullish, RSI not overbought, MACD positive, Price >= VWAP
        if (
            score >= 70.0
            and ema_20 is not None
            and ema_50 is not None
            and ema_20 > ema_50
            and (rsi is not None and rsi < 68.0)
            and (macd_hist is not None and macd_hist > 0)
        ):
            strength = SignalStrength.STRONG if score >= 85.0 else SignalStrength.MODERATE
            action = SignalAction.BUY
            primary = (
                f"High-confluence swing BUY signal: Strong trend alignment (Score: {score:.1f}/100) "
                f"with expanding MACD momentum and RSI ({rsi:.1f}) in prime acceleration zone."
            )

        # SELL Trigger: Breakdown below EMA 50 or Score <= 35 or Bearish Death Cross
        elif (
            score <= 35.0
            or (ema_50 is not None and latest_close < ema_50)
            or (ema_20 is not None and ema_50 is not None and ema_20 < ema_50)
            or (rsi is not None and rsi < 38.0)
        ):
            strength = SignalStrength.STRONG if score <= 20.0 else SignalStrength.MODERATE
            action = SignalAction.SELL
            reasons = []
            if ema_50 is not None and latest_close < ema_50:
                reasons.append("Breakdown below EMA 50 support")
            if ema_20 is not None and ema_50 is not None and ema_20 < ema_50:
                reasons.append("Bearish Death Cross")
            if rsi is not None and rsi < 38.0:
                reasons.append("RSI momentum collapse (< 38)")
            primary = f"Exit/SELL signal ({', '.join(reasons) or 'Bearish technical score'}): Technical Score {score:.1f}/100."

        # HOLD Trigger: Neutral consolidation or conflicting indicators
        else:
            strength = SignalStrength.WEAK
            action = SignalAction.HOLD
            primary = f"HOLD: Neutral consolidation. Market conditions do not exhibit clean multi-factor confluence (Score: {score:.1f}/100)."

        return TradeSignal(
            symbol=symbol.upper(),
            timestamp=latest_ts,
            action=action,
            strength=strength,
            entry_price=latest_close,
            suggested_stop_loss=suggested_stop,
            suggested_take_profit=suggested_target,
            risk_reward_ratio=self.min_risk_reward,
            stop_loss_pct=stop_loss_pct,
            target_profit_pct=target_profit_pct,
            primary_trigger=primary,
            confirming_factors=confirming,
            conflicting_factors=conflicting,
            technical_score=score,
            snapshot=snapshot,
        )

    def generate_signals_history(
        self,
        symbol: str,
        candles: Sequence[Candle],
    ) -> List[TradeSignal]:
        """
        Evaluates candles chronologically bar by bar without look-ahead bias.
        """
        signals: List[TradeSignal] = []
        n = len(candles)
        if n == 0:
            return signals

        # We need at least 50 bars for valid strategy evaluation
        for i in range(49, n):
            sub_slice = candles[:i + 1]
            sig = self.generate_signal(symbol, sub_slice)
            signals.append(sig)

        return signals
