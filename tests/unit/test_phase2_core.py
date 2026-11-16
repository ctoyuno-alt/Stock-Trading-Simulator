"""
Unit Tests for Phase 2: Configuration, Market Schedule, and Indian Friction Calculation.
Built with standard unittest.TestCase for standalone and pytest compatibility.
"""

from datetime import datetime
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from backend.app.core.config import Settings
from backend.app.core.market_schedule import is_market_open, IST_ZONE
from trading.charges import calculate_trade_friction


class TestPhase2Core(unittest.TestCase):

    def test_settings_safety_lock(self):
        """Verify that enabling real trading throws an immediate security error."""
        with self.assertRaises(ValueError):
            Settings(ENABLE_REAL_TRADING=True)

    def test_settings_sanitized_dict(self):
        """Verify that sensitive credentials are never revealed in logging dictionaries."""
        settings = Settings(
            GEMINI_API_KEY="AIzaSySecretTestKey12345",
            POSTGRES_PASSWORD="super_secret_db_password",
        )
        sanitized = settings.sanitized_dict()
        self.assertEqual(sanitized.get("GEMINI_API_KEY") or sanitized.get("gemini_api_key"), "********")
        self.assertEqual(sanitized.get("POSTGRES_PASSWORD") or sanitized.get("postgres_password"), "********")

    def test_trading_universe_parsing(self):
        """Verify trading universe parses correctly into an uppercase list."""
        settings = Settings(TRADING_UNIVERSE="reliance.ns, tcs.ns, infy.ns")
        self.assertEqual(settings.universe_list, ["RELIANCE.NS", "TCS.NS", "INFY.NS"])

    def test_market_schedule_weekend(self):
        """Verify that Saturday and Sunday are marked as closed."""
        # Saturday
        saturday_dt = datetime(2026, 11, 21, 10, 30, tzinfo=IST_ZONE)
        is_open, reason = is_market_open(saturday_dt)
        self.assertFalse(is_open)
        self.assertIn("Saturday", reason)

        # Sunday
        sunday_dt = datetime(2026, 11, 22, 11, 0, tzinfo=IST_ZONE)
        is_open, reason = is_market_open(sunday_dt)
        self.assertFalse(is_open)
        self.assertIn("Sunday", reason)

    def test_market_schedule_holidays(self):
        """Verify that official NSE holidays are marked as closed."""
        # Republic Day 2026-01-26 (Monday)
        republic_day = datetime(2026, 1, 26, 11, 0, tzinfo=IST_ZONE)
        is_open, reason = is_market_open(republic_day)
        self.assertFalse(is_open)
        self.assertIn("Trading Holiday", reason)

    def test_market_schedule_trading_hours(self):
        """Verify market opening (09:15 IST) and closing (15:30 IST) boundaries on a regular trading weekday."""
        # Tuesday 2026-11-17
        # 08:45 IST -> Closed (Pre-market)
        pre_market = datetime(2026, 11, 17, 8, 45, tzinfo=IST_ZONE)
        is_open, reason = is_market_open(pre_market)
        self.assertFalse(is_open)
        self.assertIn("pre-open", reason.lower())

        # 10:30 IST -> Open (Regular session)
        open_market = datetime(2026, 11, 17, 10, 30, tzinfo=IST_ZONE)
        is_open, reason = is_market_open(open_market)
        self.assertTrue(is_open)
        self.assertIn("Regular Trading Session", reason)

        # 15:45 IST -> Closed (Post-market)
        post_market = datetime(2026, 11, 17, 15, 45, tzinfo=IST_ZONE)
        is_open, reason = is_market_open(post_market)
        self.assertFalse(is_open)
        self.assertIn("post-close", reason.lower())

    def test_indian_trade_friction_buy(self):
        """
        Verify detailed Indian equity delivery charges calculation for a BUY order:
        10 shares @ ₹2,500.00
        - Slippage (5 bps = 0.05%): Executed price = ₹2,501.25
        - Turnover = 10 * 2501.25 = ₹25,012.50
        - Brokerage = ₹20.00
        - STT (0.1%) = ₹25.01
        - Stamp Duty (0.015% on BUY) = ₹3.75
        - GST (18% on Brokerage + Exchange + SEBI)
        - Net cash impact == Turnover + Total Charges
        """
        breakdown = calculate_trade_friction(
            symbol="RELIANCE.NS",
            side="BUY",
            quantity=10,
            price=Decimal("2500.00"),
            slippage_bps=5.0,
        )

        self.assertEqual(breakdown.symbol, "RELIANCE.NS")
        self.assertEqual(breakdown.side, "BUY")
        self.assertGreater(breakdown.executed_price, breakdown.requested_price)
        self.assertEqual(breakdown.brokerage_inr, Decimal("20.00"))
        self.assertGreater(breakdown.stamp_duty_inr, Decimal("0.00"))
        self.assertGreater(breakdown.stt_tax_inr, Decimal("0.00"))
        self.assertGreater(breakdown.gst_inr, Decimal("0.00"))
        self.assertGreater(breakdown.total_charges_inr, Decimal("0.00"))
        self.assertEqual(breakdown.net_cash_impact_inr, breakdown.turnover + breakdown.total_charges_inr)

    def test_indian_trade_friction_sell(self):
        """
        Verify delivery charges calculation for a SELL order:
        - Executed price < requested price due to adverse slippage.
        - Stamp duty must be ZERO on SELL.
        - Net cash credited == Turnover - Total Charges.
        """
        breakdown = calculate_trade_friction(
            symbol="TCS.NS",
            side="SELL",
            quantity=5,
            price=Decimal("4000.00"),
            slippage_bps=5.0,
        )

        self.assertEqual(breakdown.symbol, "TCS.NS")
        self.assertEqual(breakdown.side, "SELL")
        self.assertLess(breakdown.executed_price, breakdown.requested_price)
        self.assertEqual(breakdown.stamp_duty_inr, Decimal("0.00"))
        self.assertEqual(breakdown.net_cash_impact_inr, breakdown.turnover - breakdown.total_charges_inr)


if __name__ == "__main__":
    unittest.main()
