"""
Unit Tests for Phase 9: Historical Backtesting Engine and Performance Analytics.
"""

from decimal import Decimal
import unittest

from backend.app.market_data.yfinance_provider import YFinanceProvider
from strategies.swing_strategy import EMAMACDSwingStrategy
from trading.backtest import BacktestEngine, BacktestResult, BacktestTrade


class TestPhase9Backtest(unittest.TestCase):

    def setUp(self):
        self.strategy = EMAMACDSwingStrategy()
        self.engine = BacktestEngine(
            strategy=self.strategy,
            initial_capital_inr=Decimal("100000.00"),
            max_risk_per_trade=0.01,
            max_allocation_per_position=0.20,
            slippage_bps=5.0,
            warmup_bars=50,
        )

    def test_backtest_warmup_requirement(self):
        """Verify backtest raises ValueError when input history is less than warmup bars (50)."""
        batch = YFinanceProvider.generate_synthetic_history("RELIANCE", days=30)
        with self.assertRaises(ValueError):
            self.engine.run("RELIANCE", batch.candles)

    def test_backtest_accounting_identity_and_execution(self):
        """
        Verify fundamental accounting identity in backtest:
        Final Equity == Initial Capital + Total Net Profit
        """
        batch = YFinanceProvider.generate_synthetic_history(
            "TCS",
            start_price=Decimal("3500.00"),
            days=120,
            trend=0.0012,
            volatility=0.012,
        )
        self.assertEqual(len(batch.candles), 120)

        result = self.engine.run("TCS", batch.candles)

        self.assertIsInstance(result, BacktestResult)
        self.assertEqual(result.symbol, "TCS")
        self.assertEqual(result.total_bars, 120)
        self.assertEqual(result.initial_capital_inr, Decimal("100000.00"))

        # Accounting identity
        expected_equity = result.initial_capital_inr + result.total_net_profit_inr
        self.assertEqual(result.final_equity_inr, expected_equity)

        # Equity curve time series matches bar count
        self.assertEqual(len(result.equity_curve), 120)

    def test_backtest_trades_audit_and_charges(self):
        """Verify all closed trades have valid exit reasons, positive charges, and duration."""
        batch = YFinanceProvider.generate_synthetic_history(
            "INFY",
            start_price=Decimal("1800.00"),
            days=150,
            trend=0.0015,
            volatility=0.015,
        )
        result = self.engine.run("INFY", batch.candles)

        if result.trades:
            for trade in result.trades:
                self.assertIsInstance(trade, BacktestTrade)
                self.assertIn(
                    trade.exit_reason,
                    ["STOP_LOSS", "TAKE_PROFIT", "STRATEGY_EXIT", "END_OF_DATA"],
                )
                self.assertGreater(trade.quantity, 0)
                self.assertGreater(trade.entry_price, Decimal("0.00"))
                self.assertGreater(trade.exit_price, Decimal("0.00"))
                self.assertGreater(trade.total_charges_inr, Decimal("0.00"))
                self.assertGreaterEqual(trade.holding_period_bars, 0)
                # Verify Net P&L = Gross P&L - Total Charges
                expected_net = trade.gross_pnl_inr - trade.total_charges_inr
                self.assertEqual(trade.net_pnl_inr, expected_net)


if __name__ == "__main__":
    unittest.main()
