"""
Unit Tests for Daily Circuit Breaker, Sector Concentration Caps, and Telegram Alerts.
"""

from decimal import Decimal
import unittest

from backend.app.core.notifications import TelegramNotifier
from trading.risk import (
    check_daily_circuit_breaker,
    validate_order_risk,
    validate_sector_concentration,
)


class TestRiskCircuitBreakerAndSafety(unittest.TestCase):

    def test_daily_circuit_breaker_within_safe_limits(self):
        """Verify normal trading when daily drawdown is within safe bounds (-0.5% vs -2.0% limit)."""
        starting_equity = Decimal("100000.00")
        current_equity = Decimal("99500.00")  # -0.5% loss

        is_ok, reason = check_daily_circuit_breaker(
            current_equity=current_equity,
            daily_starting_equity=starting_equity,
            max_daily_drawdown_pct=0.02,
        )
        self.assertTrue(is_ok)
        self.assertIsNone(reason)

    def test_daily_circuit_breaker_tripping_at_2pct_loss(self):
        """Verify that a 2.5% daily drawdown trips the circuit breaker."""
        starting_equity = Decimal("100000.00")
        current_equity = Decimal("97500.00")  # -2.5% loss

        is_ok, reason = check_daily_circuit_breaker(
            current_equity=current_equity,
            daily_starting_equity=starting_equity,
            max_daily_drawdown_pct=0.02,
        )
        self.assertFalse(is_ok)
        self.assertIn("DAILY CIRCUIT BREAKER TRIPPED", reason)
        self.assertIn("2.50%", reason)

    def test_sector_concentration_cap_enforcement(self):
        """
        Verify that holding 2 IT stocks (e.g. TCS and INFY) blocks entry of a 3rd IT stock (e.g. WIPRO/INFY).
        """
        # Both TCS and INFY belong to 'Information Technology'
        existing_symbols = {"TCS", "INFY"}

        # Attempting to add another IT stock should be rejected
        is_ok, reason = validate_sector_concentration(
            symbol="INFY",
            existing_symbols=existing_symbols,
            max_per_sector=2,
        )
        self.assertFalse(is_ok)
        self.assertIn("Sector concentration limit reached", reason)

        # But adding a Banking stock (e.g. HDFCBANK) must be approved
        is_bank_ok, bank_reason = validate_sector_concentration(
            symbol="HDFCBANK",
            existing_symbols=existing_symbols,
            max_per_sector=2,
        )
        self.assertTrue(is_bank_ok)
        self.assertIsNone(bank_reason)

    def test_validate_order_risk_with_circuit_breaker_and_sectors(self):
        """Verify pre-trade validation rejects when circuit breaker is tripped."""
        starting_equity = Decimal("100000.00")
        current_equity = Decimal("97000.00")  # -3.0% loss

        res = validate_order_risk(
            symbol="RELIANCE",
            side="BUY",
            quantity=10,
            entry_price=Decimal("1350.00"),
            stop_loss_price=Decimal("1300.00"),
            open_positions_count=0,
            existing_symbols=set(),
            enforce_market_hours=False,
            current_equity=current_equity,
            daily_starting_equity=starting_equity,
            max_daily_drawdown_pct=0.02,
        )
        self.assertFalse(res.is_valid)
        self.assertTrue(any("CIRCUIT BREAKER TRIPPED" in r for r in res.rejection_reasons))

    def test_telegram_notifier_unconfigured_safety(self):
        """Verify that unconfigured Telegram bot handles dispatch safely without crashing."""
        notifier = TelegramNotifier(bot_token="", chat_id="", enabled=True)
        self.assertFalse(notifier.is_configured)
        self.assertFalse(notifier.send_message("Test Ping"))

        success, err = notifier.test_connection()
        self.assertFalse(success)
        self.assertIn("missing", err.lower())


if __name__ == "__main__":
    unittest.main()
