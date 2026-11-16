"""
Unit Tests for Phase 4: Quantitative Technical Indicator Engine.
Validates EMA, RSI, MACD, VWAP, crossover detection, warmup boundaries, and regime states.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from backend.app.market_data.base import Candle
from backend.app.market_data.yfinance_provider import YFinanceProvider
from indicators.base import InsufficientDataError, MomentumRegime, TrendRegime, MACDState
from indicators.moving_averages import calculate_ema, detect_crossover
from indicators.momentum import calculate_rsi
from indicators.trend import calculate_macd
from indicators.volume import calculate_vwap
from indicators.engine import TechnicalIndicatorEngine, MIN_WARMUP_BARS

IST_ZONE = ZoneInfo("Asia/Kolkata")


class TestPhase4Indicators(unittest.TestCase):

    def test_ema_mathematical_precision(self):
        """
        Verify mathematical precision of EMA against hand-calculated values:
        Prices = [10, 11, 12, 13, 14, 15], Period = 5
        - Initial SMA seed at index 4 (1st 5 bars): (10+11+12+13+14)/5 = 12.00
        - alpha = 2 / (5 + 1) = 1/3 (0.33333...)
        - At index 5 (Price = 15): (15 * 1/3) + (12 * 2/3) = 5.0 + 8.0 = 13.00
        """
        prices = [Decimal("10"), Decimal("11"), Decimal("12"), Decimal("13"), Decimal("14"), Decimal("15")]
        ema = calculate_ema(prices, period=5)

        self.assertEqual(len(ema), 6)
        self.assertIsNone(ema[0])
        self.assertIsNone(ema[1])
        self.assertIsNone(ema[2])
        self.assertIsNone(ema[3])
        self.assertEqual(ema[4], Decimal("12.00"))
        self.assertEqual(ema[5], Decimal("13.00"))

    def test_ema_crossover_detection(self):
        """Verify Golden Cross and Death Cross detection."""
        # Fast moves from below slow to above slow
        fast = [Decimal("95"), Decimal("99"), Decimal("105"), Decimal("110")]
        slow = [Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")]

        crossovers = detect_crossover(fast, slow)
        self.assertEqual(crossovers[0], None)
        self.assertEqual(crossovers[1], None)
        self.assertEqual(crossovers[2], "GOLDEN_CROSS")  # 99 <= 100 -> 105 > 100
        self.assertEqual(crossovers[3], None)

        # Fast moves from above slow to below slow
        fast_rev = [Decimal("105"), Decimal("101"), Decimal("96"), Decimal("90")]
        slow_rev = [Decimal("100"), Decimal("100"), Decimal("100"), Decimal("100")]

        crossovers_rev = detect_crossover(fast_rev, slow_rev)
        self.assertEqual(crossovers_rev[2], "DEATH_CROSS")  # 101 >= 100 -> 96 < 100

    def test_rsi_bounds_and_extremes(self):
        """Verify RSI bounds in [0, 100] and response to strong upward/downward trends."""
        # Monotonically increasing prices
        bull_prices = [100.0 + i * 2.0 for i in range(30)]
        rsi_bull = calculate_rsi(bull_prices, period=14)
        self.assertEqual(len(rsi_bull), 30)
        self.assertIsNone(rsi_bull[13])
        self.assertIsNotNone(rsi_bull[14])
        # Monotonic upward should produce 100.0 RSI
        self.assertEqual(rsi_bull[-1], 100.0)

        # Monotonically decreasing prices
        bear_prices = [200.0 - i * 2.0 for i in range(30)]
        rsi_bear = calculate_rsi(bear_prices, period=14)
        self.assertEqual(rsi_bear[-1], 0.0)

        # Flat prices (zero gain, zero loss)
        flat_prices = [100.0] * 30
        rsi_flat = calculate_rsi(flat_prices, period=14)
        self.assertEqual(rsi_flat[-1], 50.0)

    def test_macd_computation_and_warmup(self):
        """Verify MACD (12, 26, 9) warmup lengths and histogram equality."""
        prices = [Decimal(str(2000.0 + (i * 5.0) + ((-1)**i * 3.0))) for i in range(50)]
        macd = calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9)

        # MACD Line requires 26 bars (index 25)
        self.assertIsNone(macd.macd_line[24])
        self.assertIsNotNone(macd.macd_line[25])

        # Signal Line requires 26 + 9 - 1 = 34 bars (index 33)
        self.assertIsNone(macd.signal_line[32])
        self.assertIsNotNone(macd.signal_line[33])

        # Histogram must equal MACD Line - Signal Line
        for i in range(34, 50):
            m = macd.macd_line[i]
            s = macd.signal_line[i]
            h = macd.histogram[i]
            self.assertIsNotNone(m)
            self.assertIsNotNone(s)
            self.assertIsNotNone(h)
            self.assertAlmostEqual(h, round(m - s, 4), places=3)

    def test_vwap_intraday_reset(self):
        """Verify VWAP formula and daily session reset."""
        day1 = datetime(2026, 11, 16, 9, 30, tzinfo=IST_ZONE)
        day1_next = datetime(2026, 11, 16, 10, 0, tzinfo=IST_ZONE)
        day2 = datetime(2026, 11, 17, 9, 30, tzinfo=IST_ZONE)

        # Bar 1: H=105, L=95, C=100 -> TP = 100, Vol = 1000 -> VWAP = 100.00
        # Bar 2: H=115, L=105, C=110 -> TP = 110, Vol = 1000 -> VWAP = (100*1000 + 110*1000)/2000 = 105.00
        # Bar 3 (Day 2 reset): H=205, L=195, C=200 -> TP = 200, Vol = 500 -> VWAP resets to 200.00
        highs = [105, 115, 205]
        lows = [95, 105, 195]
        closes = [100, 110, 200]
        vols = [1000, 1000, 500]
        tss = [day1, day1_next, day2]

        vwap = calculate_vwap(highs, lows, closes, vols, timestamps=tss, reset_daily=True)
        self.assertEqual(vwap[0], Decimal("100.00"))
        self.assertEqual(vwap[1], Decimal("105.00"))
        self.assertEqual(vwap[2], Decimal("200.00"))  # Resets on new calendar day

    def test_indicator_engine_warmup_validation(self):
        """Verify TechnicalIndicatorEngine enforces warmup rules."""
        engine = TechnicalIndicatorEngine()

        # Generate only 20 bars
        batch_short = YFinanceProvider.generate_synthetic_history("RELIANCE", days=20)
        self.assertEqual(len(batch_short.candles), 20)

        # 1. With require_full_warmup=True -> Must raise InsufficientDataError
        with self.assertRaises(InsufficientDataError):
            engine.compute("RELIANCE", batch_short.candles, require_full_warmup=True)

        # 2. With require_full_warmup=False -> Computes partial, flags is_warmed_up=False
        series_partial = engine.compute("RELIANCE", batch_short.candles, require_full_warmup=False)
        self.assertFalse(series_partial.snapshot.is_warmed_up)
        self.assertEqual(series_partial.snapshot.bars_available, 20)
        self.assertEqual(series_partial.snapshot.min_bars_required, MIN_WARMUP_BARS)

    def test_indicator_engine_full_run(self):
        """Verify TechnicalIndicatorEngine full computation with warmed-up data (80 bars)."""
        engine = TechnicalIndicatorEngine()
        batch = YFinanceProvider.generate_synthetic_history("TCS", days=80)
        self.assertEqual(len(batch.candles), 80)

        series = engine.compute("TCS", batch.candles, require_full_warmup=True)

        # Verification of snapshot
        snap = series.snapshot
        self.assertTrue(snap.is_warmed_up)
        self.assertEqual(snap.symbol, "TCS")
        self.assertIsNotNone(snap.ema_fast_20)
        self.assertIsNotNone(snap.ema_slow_50)
        self.assertIn(snap.ema_trend_regime, [TrendRegime.BULLISH, TrendRegime.BEARISH, TrendRegime.NEUTRAL])
        self.assertIsNotNone(snap.rsi_14)
        self.assertIn(snap.rsi_regime, [MomentumRegime.OVERSOLD, MomentumRegime.OVERBOUGHT, MomentumRegime.BULLISH_MOMENTUM, MomentumRegime.BEARISH_MOMENTUM, MomentumRegime.NEUTRAL])
        self.assertIsNotNone(snap.macd_line)
        self.assertIsNotNone(snap.macd_signal)
        self.assertIsNotNone(snap.macd_histogram)
        self.assertIn(snap.macd_state, [MACDState.BULLISH_CROSSOVER, MACDState.BEARISH_CROSSOVER, MACDState.BULLISH_ABOVE, MACDState.BEARISH_BELOW, MACDState.NEUTRAL])
        self.assertIsNotNone(snap.vwap)

        # Series length matches
        self.assertEqual(len(series.timestamps), 80)
        self.assertEqual(len(series.ema_fast), 80)
        self.assertEqual(len(series.ema_slow), 80)
        self.assertEqual(len(series.rsi), 80)
        self.assertEqual(len(series.macd_hist), 80)


if __name__ == "__main__":
    unittest.main()
