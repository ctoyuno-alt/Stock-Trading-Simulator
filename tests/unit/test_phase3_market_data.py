"""
Unit Tests for Phase 3: Market Data Provider, Universe Manager, and Data Validation Engine.
Uses standard unittest.TestCase for standalone and pytest compatibility.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from backend.app.market_data.base import Candle, MarketDataBatch
from backend.app.market_data.universe import UniverseManager, DEFAULT_UNIVERSE
from backend.app.market_data.yfinance_provider import YFinanceProvider
from backend.app.market_data.storage import MarketDataStorage, HAS_PANDAS

IST_ZONE = ZoneInfo("Asia/Kolkata")


class TestPhase3MarketData(unittest.TestCase):

    def setUp(self):
        self.universe = UniverseManager()
        self.provider = YFinanceProvider()

    def test_universe_symbols_and_tick_sizes(self):
        """Verify the 10 liquid NSE stocks are configured with standard ₹0.05 tick size."""
        symbols = self.universe.get_symbols("IN")
        self.assertEqual(len(symbols), 10)
        expected = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "LT", "TATAMOTORS"]
        for sym in expected:
            self.assertIn(sym, symbols)
            inst = self.universe.get_instrument(sym)
            self.assertIsNotNone(inst)
            self.assertEqual(inst.tick_size, Decimal("0.05"))
            self.assertEqual(inst.lot_size, 1)
            self.assertEqual(inst.currency, "INR")
            self.assertEqual(inst.exchange, "NSE")
            self.assertTrue(inst.yfinance_ticker.endswith(".NS"))

    def test_symbol_normalization(self):
        """Verify symbols normalize cleanly regardless of case and .NS/.BO suffixes."""
        self.assertEqual(self.universe.normalize_symbol("reliance.ns"), "RELIANCE")
        self.assertEqual(self.universe.normalize_symbol("  TCS.NS  "), "TCS")
        self.assertEqual(self.universe.normalize_symbol("infy.bo"), "INFY")
        self.assertEqual(self.universe.normalize_symbol("HDFCBANK"), "HDFCBANK")

        self.assertEqual(self.universe.get_yfinance_ticker("reliance"), "RELIANCE.NS")
        self.assertEqual(self.universe.get_yfinance_ticker("tcs.ns"), "TCS.NS")

    def test_valid_data_batch_validation(self):
        """Verify that a compliant candle batch passes data validation with 0 anomalies."""
        now = datetime.now(timezone.utc)
        candles = [
            Candle(
                timestamp=now - timedelta(days=2),
                open=Decimal("2500.00"),
                high=Decimal("2550.00"),
                low=Decimal("2480.00"),
                close=Decimal("2520.00"),
                volume=1000000,
                vwap=Decimal("2515.00"),
            ),
            Candle(
                timestamp=now - timedelta(days=1),
                open=Decimal("2525.00"),
                high=Decimal("2560.00"),
                low=Decimal("2510.00"),
                close=Decimal("2540.00"),
                volume=1200000,
                vwap=Decimal("2535.00"),
            ),
        ]

        batch = MarketDataBatch(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe="1d",
            candles=candles,
            provider="yfinance",
            is_delayed=True,
            delay_minutes=15,
        )

        validation = self.provider.validate_batch(batch)
        self.assertTrue(validation.is_valid)
        self.assertEqual(len(validation.anomalies_detected), 0)
        self.assertEqual(validation.total_candles, 2)
        self.assertTrue(batch.is_delayed)
        self.assertEqual(batch.delay_minutes, 15)
        self.assertIn("DATA NOTICE", batch.data_source_disclaimer)

    def test_data_validation_anomaly_detection(self):
        """Verify that corrupt data (High < Low, negative price, negative volume) is flagged."""
        now = datetime.now(timezone.utc)
        corrupted_candles = [
            # Anomaly 1: High < Low
            Candle(
                timestamp=now - timedelta(days=3),
                open=Decimal("2500.00"),
                high=Decimal("2400.00"),  # High is lower than Low
                low=Decimal("2450.00"),
                close=Decimal("2480.00"),
                volume=50000,
            ),
            # Anomaly 2: Negative price
            Candle(
                timestamp=now - timedelta(days=2),
                open=Decimal("-10.00"),
                high=Decimal("2500.00"),
                low=Decimal("-15.00"),
                close=Decimal("2400.00"),
                volume=50000,
            ),
            # Anomaly 3: Negative volume
            Candle(
                timestamp=now - timedelta(days=1),
                open=Decimal("2500.00"),
                high=Decimal("2550.00"),
                low=Decimal("2480.00"),
                close=Decimal("2520.00"),
                volume=-100,
            ),
        ]

        batch = MarketDataBatch(
            symbol="TCS",
            exchange="NSE",
            timeframe="1d",
            candles=corrupted_candles,
            provider="test_provider",
        )

        validation = self.provider.validate_batch(batch)
        self.assertFalse(validation.is_valid)
        self.assertGreaterEqual(len(validation.anomalies_detected), 3)

    def test_chronological_ordering_anomaly(self):
        """Verify that out-of-order or duplicate timestamps are flagged."""
        now = datetime.now(timezone.utc)
        out_of_order_candles = [
            Candle(
                timestamp=now - timedelta(days=1),
                open=Decimal("2500.00"),
                high=Decimal("2550.00"),
                low=Decimal("2480.00"),
                close=Decimal("2520.00"),
                volume=10000,
            ),
            Candle(
                timestamp=now - timedelta(days=2),  # Earlier timestamp placed after later timestamp
                open=Decimal("2520.00"),
                high=Decimal("2530.00"),
                low=Decimal("2510.00"),
                close=Decimal("2525.00"),
                volume=10000,
            ),
        ]

        batch = MarketDataBatch(
            symbol="INFY",
            exchange="NSE",
            timeframe="1d",
            candles=out_of_order_candles,
            provider="test_provider",
        )

        validation = self.provider.validate_batch(batch)
        self.assertFalse(validation.is_valid)
        self.assertTrue(any("chronological" in a.lower() or "timestamp" in a.lower() for a in validation.anomalies_detected))

    def test_synthetic_history_generator(self):
        """Verify deterministic synthetic generator produces 100% valid candles."""
        batch = YFinanceProvider.generate_synthetic_history("RELIANCE", days=50)
        self.assertEqual(batch.symbol, "RELIANCE")
        self.assertEqual(len(batch.candles), 50)
        self.assertIsNotNone(batch.validation)
        self.assertTrue(batch.validation.is_valid)
        self.assertEqual(len(batch.validation.anomalies_detected), 0)

        # Check conversion to structured representation
        converted = MarketDataStorage.candles_to_dataframe(batch.candles)
        if HAS_PANDAS:
            import pandas as pd
            self.assertIsInstance(converted, pd.DataFrame)
            self.assertEqual(len(converted), 50)
            self.assertTrue((converted["high"] >= converted["low"]).all())
        else:
            self.assertIsInstance(converted, list)
            self.assertEqual(len(converted), 50)
            self.assertTrue(all(row["high"] >= row["low"] for row in converted))


if __name__ == "__main__":
    unittest.main()
