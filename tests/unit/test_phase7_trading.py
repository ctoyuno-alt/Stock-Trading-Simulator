"""
Unit Tests for Phase 7: Paper Trading Engine, 1% Risk Sizing, and Performance Metrics.
"""

from decimal import Decimal
import unittest

from backend.app.core.config import Settings
from trading.risk import calculate_position_size, validate_order_risk
from trading.metrics import calculate_performance_metrics


class TestPhase7Trading(unittest.TestCase):

    def test_position_sizing_1pct_risk_and_concentration(self):
        """
        Verify exact mathematical position sizing under 1% risk and 20% concentration limits:
        - Equity = ₹100,000.00, Cash = ₹100,000.00
        - Entry Price = ₹2,500.00, Stop Loss = ₹2,450.00 (Risk per share = ₹50.00)
        - 1% Risk Budget = ₹1,000.00 -> 1000 // 50 = 20 shares
        - 20% Capital Allocation Cap = ₹20,000.00 -> 20000 // 2500 = 8 shares
        - Final Size = min(20, 8, 40) = 8 shares
        """
        sizing = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2450.00"),
            max_risk_pct=0.01,
            max_allocation_pct=0.20,
        )

        self.assertTrue(sizing.is_approved)
        self.assertEqual(sizing.quantity, 8)
        self.assertEqual(sizing.risk_per_share_inr, Decimal("50.00"))
        self.assertEqual(sizing.total_risk_inr, Decimal("400.00"))  # 8 * 50
        self.assertEqual(sizing.capital_required_inr, Decimal("20000.00"))  # 8 * 2500
        self.assertEqual(sizing.allocation_pct, 20.0)

    def test_position_sizing_cash_constrained(self):
        """
        Verify sizing is bounded when available cash is less than risk or allocation limits:
        - Cash = ₹4,000.00, Entry = ₹2,500.00 -> Cash can only afford 1 share
        """
        sizing = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("4000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2400.00"),
            max_risk_pct=0.01,
            max_allocation_pct=0.20,
        )

        self.assertTrue(sizing.is_approved)
        self.assertEqual(sizing.quantity, 1)
        self.assertEqual(sizing.capital_required_inr, Decimal("2500.00"))

    def test_position_sizing_invalid_inputs(self):
        """Verify position sizing rejects stop loss >= entry price or zero prices."""
        sizing = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2600.00"),  # Stop loss higher than entry
        )
        self.assertFalse(sizing.is_approved)
        self.assertEqual(sizing.quantity, 0)
        self.assertIn("Stop-loss price must be strictly below", sizing.rejection_reason)

    def test_risk_validation_max_positions_and_duplicates(self):
        """Verify pre-trade risk engine rejects duplicate positions and max concurrent limits."""
        # Test duplicate symbol rejection
        res_dup = validate_order_risk(
            symbol="RELIANCE",
            side="BUY",
            quantity=10,
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2400.00"),
            open_positions_count=2,
            existing_symbols={"RELIANCE", "TCS"},
            enforce_market_hours=False,
        )
        self.assertFalse(res_dup.is_valid)
        self.assertTrue(any("already exists" in r for r in res_dup.rejection_reasons))

        # Test maximum open positions limit (5)
        res_max = validate_order_risk(
            symbol="INFY",
            side="BUY",
            quantity=10,
            entry_price=Decimal("1800.00"),
            stop_loss_price=Decimal("1700.00"),
            open_positions_count=5,  # At limit
            existing_symbols={"RELIANCE", "TCS", "HDFCBANK", "SBIN", "ITC"},
            enforce_market_hours=False,
        )
        self.assertFalse(res_max.is_valid)
        self.assertTrue(any("Maximum concurrent open positions" in r for r in res_max.rejection_reasons))

    def test_risk_validation_stop_loss_percentage(self):
        """Verify rejection when stop loss is tighter than the minimum 1.5% boundary."""
        # Entry = 2000, Stop = 1980 (1.0% distance < 1.5% minimum)
        res = validate_order_risk(
            symbol="LT",
            side="BUY",
            quantity=5,
            entry_price=Decimal("2000.00"),
            stop_loss_price=Decimal("1980.00"),
            open_positions_count=0,
            existing_symbols=set(),
            enforce_market_hours=False,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("tighter than minimum required" in r for r in res.rejection_reasons))

    def test_performance_metrics_calculation(self):
        """
        Verify institutional metrics calculation:
        Trades: +₹500, -₹200, +₹800, -₹300
        - Total = 4, Winning = 2, Losing = 2 -> Win Rate = 50.0%
        - Gross Profit = ₹1300, Gross Loss = ₹500 -> Profit Factor = 1300 / 500 = 2.60
        - Net P&L = +₹800.00
        """
        realized_pnls = [
            Decimal("500.00"),
            Decimal("-200.00"),
            Decimal("800.00"),
            Decimal("-300.00"),
        ]
        charges = [
            Decimal("45.00"),
            Decimal("40.00"),
            Decimal("55.00"),
            Decimal("42.00"),
        ]
        equity_curve = [
            Decimal("100000.00"),
            Decimal("100500.00"),
            Decimal("100300.00"),
            Decimal("101100.00"),
            Decimal("100800.00"),
        ]

        metrics = calculate_performance_metrics(
            realized_pnls=realized_pnls,
            charges_paid=charges,
            equity_curve=equity_curve,
        )

        self.assertEqual(metrics.total_trades, 4)
        self.assertEqual(metrics.winning_trades, 2)
        self.assertEqual(metrics.losing_trades, 2)
        self.assertEqual(metrics.win_rate_pct, 50.0)
        self.assertEqual(metrics.total_gross_profit_inr, Decimal("1300.00"))
        self.assertEqual(metrics.total_gross_loss_inr, Decimal("500.00"))
        self.assertEqual(metrics.profit_factor, 2.6)
        self.assertEqual(metrics.total_net_realized_pnl_inr, Decimal("800.00"))
        self.assertEqual(metrics.average_trade_pnl_inr, Decimal("200.00"))
        self.assertEqual(metrics.largest_win_inr, Decimal("800.00"))
        self.assertEqual(metrics.largest_loss_inr, Decimal("-300.00"))
        self.assertGreater(metrics.total_charges_paid_inr, Decimal("180.00"))
        # Max drawdown: Peak 101,100 -> Trough 100,800 = ₹300.00
        self.assertEqual(metrics.max_drawdown_inr, Decimal("300.00"))
        self.assertAlmostEqual(metrics.max_drawdown_pct, 0.30, places=1)


if __name__ == "__main__":
    unittest.main()
