"""
Unit Test Suite for US Stock Exchange (NYSE & NASDAQ) Capabilities.

Validates:
1. US Universe (10 mega-caps: AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, BRK-B, JPM, V).
2. US Market Trading Schedule, Session Timings (09:30 - 16:00 ET), Weekends, and US Federal Holidays.
3. US Regulatory Charges (Zero Brokerage, SEC Section 31 Fee, FINRA TAF, Adverse Slippage).
4. Market routing in unified trade friction calculations.
5. US Position Sizing in USD.
"""

from datetime import datetime, date, time
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from backend.app.market_data.universe import UniverseManager, DEFAULT_US_UNIVERSE
from backend.app.core.market_schedule import (
    ET_ZONE,
    is_us_market_open,
    is_market_open,
    US_HOLIDAYS,
)
from trading.charges import (
    calculate_us_trade_friction,
    calculate_market_trade_friction,
    calculate_trade_friction,
)
from trading.risk import calculate_position_size, validate_order_risk


class TestUSMarketSupport(unittest.TestCase):
    """Test suite verifying US market data, timings, fees, and execution logic."""

    def setUp(self):
        self.universe = UniverseManager()

    def test_us_universe_membership_and_metadata(self):
        """Verify the 10 liquid US mega-caps are registered with standard $0.01 tick size."""
        us_symbols = self.universe.get_symbols(market="US")
        self.assertEqual(len(us_symbols), 10)

        expected_us = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V"]
        for sym in expected_us:
            self.assertIn(sym, us_symbols)
            inst = self.universe.get_instrument(sym)
            self.assertIsNotNone(inst)
            self.assertEqual(inst.currency, "USD")
            self.assertEqual(inst.market, "US")
            self.assertEqual(inst.tick_size, Decimal("0.01"))
            self.assertEqual(inst.lot_size, 1)
            self.assertIn(inst.exchange, ("NASDAQ", "NYSE"))
            self.assertEqual(self.universe.get_market_for_symbol(sym), "US")

    def test_us_symbol_normalization(self):
        """Verify normalization for US symbols (e.g. lowercase, BRK.B variations)."""
        self.assertEqual(self.universe.normalize_symbol("aapl"), "AAPL")
        self.assertEqual(self.universe.normalize_symbol("  msft  "), "MSFT")
        self.assertEqual(self.universe.normalize_symbol("brk.b"), "BRK-B")
        self.assertEqual(self.universe.normalize_symbol("BRK/B"), "BRK-B")
        self.assertEqual(self.universe.get_yfinance_ticker("AAPL"), "AAPL")
        self.assertEqual(self.universe.get_yfinance_ticker("BRK-B"), "BRK-B")

    def test_us_market_hours_open(self):
        """Verify US market is reported open on regular trading days between 09:30 and 16:00 ET."""
        # Regular trading Wednesday at 11:00 AM ET (not a holiday)
        test_time = datetime(2026, 4, 15, 11, 0, 0, tzinfo=ET_ZONE)
        is_open, reason = is_us_market_open(test_time)
        self.assertTrue(is_open)
        self.assertIn("OPEN", reason)

        # Multi-market wrapper call
        is_open_wrapped, _ = is_market_open(test_time, market="US")
        self.assertTrue(is_open_wrapped)

    def test_us_market_hours_closed_pre_and_post(self):
        """Verify US market reports closed before 09:30 ET and after 16:00 ET."""
        # 09:00 AM ET (Pre-market)
        pre_time = datetime(2026, 4, 15, 9, 0, 0, tzinfo=ET_ZONE)
        is_open, reason = is_us_market_open(pre_time)
        self.assertFalse(is_open)
        self.assertIn("pre-open", reason)

        # 16:30 ET (After-hours)
        post_time = datetime(2026, 4, 15, 16, 30, 0, tzinfo=ET_ZONE)
        is_open, reason = is_us_market_open(post_time)
        self.assertFalse(is_open)
        self.assertIn("post-close", reason)

    def test_us_market_weekends_and_holidays(self):
        """Verify weekend and US Federal Holiday closures."""
        # Saturday
        saturday = datetime(2026, 4, 18, 12, 0, 0, tzinfo=ET_ZONE)
        is_open, reason = is_us_market_open(saturday)
        self.assertFalse(is_open)
        self.assertIn("Saturday", reason)

        # Thanksgiving Day 2026 (Nov 26, 2026)
        thanksgiving = datetime(2026, 11, 26, 11, 0, 0, tzinfo=ET_ZONE)
        is_open, reason = is_us_market_open(thanksgiving)
        self.assertFalse(is_open)
        self.assertIn("Holiday", reason)

    def test_us_trade_friction_buy_zero_commission(self):
        """Verify US buy order execution: adverse slippage applied, zero brokerage, zero SEC/FINRA fees."""
        # Buy 100 shares of AAPL @ $200.00
        cost = calculate_us_trade_friction(
            symbol="AAPL",
            side="BUY",
            quantity=100,
            price=Decimal("200.00"),
            slippage_bps=5.0,  # 0.05%
        )
        self.assertEqual(cost.symbol, "AAPL")
        self.assertEqual(cost.side, "BUY")
        self.assertEqual(cost.quantity, 100)
        # Executed price = 200 * (1 + 0.0005) = 200.10
        self.assertEqual(cost.executed_price, Decimal("200.10"))
        self.assertEqual(cost.turnover, Decimal("20010.00"))
        # Buy side US charges are 0
        self.assertEqual(cost.brokerage_inr, Decimal("0.00"))
        self.assertEqual(cost.stt_tax_inr, Decimal("0.00"))           # SEC fee = 0 on buy
        self.assertEqual(cost.exchange_turnover_inr, Decimal("0.00"))  # FINRA fee = 0 on buy
        self.assertEqual(cost.total_charges_inr, Decimal("0.00"))
        # Net cash deducted = turnover + total charges = 20010.00
        self.assertEqual(cost.net_cash_impact_inr, Decimal("20010.00"))

    def test_us_trade_friction_sell_sec_and_finra_fees(self):
        """Verify US sell order execution: adverse slippage, SEC Section 31 and FINRA TAF fees applied."""
        # Sell 100 shares of MSFT @ $400.00
        cost = calculate_us_trade_friction(
            symbol="MSFT",
            side="SELL",
            quantity=100,
            price=Decimal("400.00"),
            slippage_bps=5.0,  # 0.05%
        )
        self.assertEqual(cost.symbol, "MSFT")
        self.assertEqual(cost.side, "SELL")
        # Executed price = 400 * (1 - 0.0005) = 399.80
        self.assertEqual(cost.executed_price, Decimal("399.80"))
        self.assertEqual(cost.turnover, Decimal("39980.00"))

        # SEC Fee: 39980 * 0.0000278 = 1.111444 -> $1.11
        self.assertGreaterEqual(cost.stt_tax_inr, Decimal("0.01"))
        # FINRA TAF: 100 * 0.000166 = 0.0166 -> $0.02
        self.assertGreaterEqual(cost.exchange_turnover_inr, Decimal("0.01"))
        self.assertEqual(cost.brokerage_inr, Decimal("0.00"))

        expected_total = cost.stt_tax_inr + cost.exchange_turnover_inr
        self.assertEqual(cost.total_charges_inr, expected_total)
        # Net cash credited = turnover - total charges
        self.assertEqual(cost.net_cash_impact_inr, cost.turnover - expected_total)

    def test_unified_trade_friction_routing(self):
        """Verify calculate_market_trade_friction routes automatically based on symbol."""
        # Indian equity should include ₹20 brokerage, STT, etc.
        in_cost = calculate_market_trade_friction(
            symbol="RELIANCE",
            side="BUY",
            quantity=10,
            price=Decimal("2800.00"),
        )
        self.assertEqual(in_cost.brokerage_inr, Decimal("20.00"))
        self.assertGreater(in_cost.stt_tax_inr, Decimal("0.00"))

        # US equity should route to US friction with 0 brokerage
        us_cost = calculate_market_trade_friction(
            symbol="NVDA",
            side="BUY",
            quantity=50,
            price=Decimal("130.00"),
        )
        self.assertEqual(us_cost.brokerage_inr, Decimal("0.00"))
        self.assertEqual(us_cost.total_charges_inr, Decimal("0.00"))

    def test_us_position_sizing_in_usd(self):
        """Verify 1% risk position sizing works accurately with USD virtual capital."""
        # $25,000 USD equity, 1% risk budget = $250 USD
        # Entry = $200.00, Stop Loss = $195.00 ($5 risk per share)
        # Max shares allowed by risk = 250 // 5 = 50 shares
        sizing = calculate_position_size(
            equity=Decimal("25000.00"),
            available_cash=Decimal("25000.00"),
            entry_price=Decimal("200.00"),
            stop_loss_price=Decimal("195.00"),
            max_risk_pct=0.01,
            max_allocation_pct=0.50,  # 50% max allocation
        )
        self.assertTrue(sizing.is_approved)
        self.assertEqual(sizing.quantity, 50)
        self.assertEqual(sizing.capital_required_inr, Decimal("10000.00"))  # $10,000 capital
        self.assertEqual(sizing.total_risk_inr, Decimal("250.00"))          # $250 risk


if __name__ == "__main__":
    unittest.main()
