"""
Unit Tests for Phase 5: Deterministic Multi-Factor Swing Trading Strategy.
Validates signal generation, confluence scoring, stop-loss & take-profit bounds, and warmup checks.
"""

from datetime import datetime
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from backend.app.market_data.yfinance_provider import YFinanceProvider
from strategies.base import SignalAction, SignalStrength, TradeSignal
from strategies.swing_strategy import EMAMACDSwingStrategy

IST_ZONE = ZoneInfo("Asia/Kolkata")


class TestPhase5Strategy(unittest.TestCase):

    def setUp(self):
        self.strategy = EMAMACDSwingStrategy(min_risk_reward=2.0)

    def test_insufficient_warmup_produces_hold(self):
        """Verify that candle history with fewer than 50 bars produces a safe HOLD signal."""
        batch = YFinanceProvider.generate_synthetic_history("RELIANCE", days=30)
        self.assertEqual(len(batch.candles), 30)

        signal = self.strategy.generate_signal("RELIANCE", batch.candles)
        self.assertEqual(signal.action, SignalAction.HOLD)
        self.assertEqual(signal.strength, SignalStrength.WEAK)
        self.assertIn("Insufficient data", signal.primary_trigger)
        self.assertTrue(any("minimum warmup" in c for c in signal.conflicting_factors))

    def test_bullish_uptrend_produces_buy(self):
        """
        Verify that a consistent upward trending series produces BUY signals
        with high confluence (Score >= 70.0), strict risk-reward ratio, and valid stop loss.
        """
        batch = YFinanceProvider.generate_synthetic_history(
            "TCS",
            start_price=Decimal("3500.00"),
            days=80,
            trend=0.0012,
            volatility=0.012,
        )
        self.assertEqual(len(batch.candles), 80)

        signals = self.strategy.generate_signals_history("TCS", batch.candles)
        buy_signals = [s for s in signals if s.action == SignalAction.BUY]

        self.assertGreater(len(buy_signals), 0, "Expected at least one BUY signal in trending history.")

        # Test attributes of the triggered BUY signal
        signal = buy_signals[0]
        self.assertEqual(signal.action, SignalAction.BUY)
        self.assertIn(signal.strength, [SignalStrength.STRONG, SignalStrength.MODERATE])
        self.assertGreaterEqual(signal.technical_score, 70.0)
        self.assertGreater(len(signal.confirming_factors), 0)

        # Stop loss and take profit validation
        self.assertLess(signal.suggested_stop_loss, signal.entry_price)
        self.assertGreater(signal.suggested_take_profit, signal.entry_price)
        self.assertGreaterEqual(signal.risk_reward_ratio, 2.0)
        # Stop loss distance must be at least 1.5%
        self.assertGreaterEqual(signal.stop_loss_pct, 1.49)
        # Take profit distance must be at least 2x stop loss distance
        self.assertGreaterEqual(signal.target_profit_pct, signal.stop_loss_pct * 1.99)

    def test_bearish_downtrend_produces_sell(self):
        """
        Verify that a steep downward trending series (EMA20 < EMA50, collapsed RSI, negative MACD)
        produces a SELL signal.
        """
        # Generate 100 days with strong negative trend (-0.004 daily)
        batch = YFinanceProvider.generate_synthetic_history(
            "INFY",
            start_price=Decimal("1800.00"),
            days=100,
            trend=-0.004,
            volatility=0.010,
        )
        self.assertEqual(len(batch.candles), 100)

        signal = self.strategy.generate_signal("INFY", batch.candles)
        self.assertEqual(signal.action, SignalAction.SELL)
        self.assertLessEqual(signal.technical_score, 50.0)
        self.assertGreater(len(signal.conflicting_factors), 0)

    def test_signals_history_generation(self):
        """
        Verify generate_signals_history evaluates bars sequentially without look-ahead bias:
        For 80 bars, signals should be generated for bars 50 to 80 (31 signals total).
        """
        batch = YFinanceProvider.generate_synthetic_history("HDFCBANK", days=80)
        signals = self.strategy.generate_signals_history("HDFCBANK", batch.candles)

        self.assertEqual(len(signals), 31)  # 80 - 50 + 1 = 31 bars evaluated
        for s in signals:
            self.assertIsInstance(s, TradeSignal)
            self.assertEqual(s.symbol, "HDFCBANK")
            self.assertIn(s.action, [SignalAction.BUY, SignalAction.SELL, SignalAction.HOLD])
            self.assertGreater(s.entry_price, Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
