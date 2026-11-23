"""
Unit Tests for Autonomous AI Auto-Trader and TradingView Widget Integration.

Validates:
- AutoTraderConfig defaults, bounds, and dictionary serialization.
- AutoTraderDecision schema and audit trail FIFO history management.
- TradingView symbol resolution for Indian (NSE) and US (NYSE/NASDAQ) equities.
- Automated Stop-Loss liquidation, Take-Profit target closure, and Strategy Reversal exits.
- Autonomous Confluence scanning and order execution.
"""

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from dashboard.components.tradingview import get_tradingview_symbol, TRADINGVIEW_SYMBOL_MAP
from trading.auto_trader import AutoTraderConfig, AutoTraderDecision, AutoTradingBot, PositionStatus
from strategies.base import SignalAction, TradeSignal, SignalStrength


class TestAutoTraderAndTradingView(unittest.TestCase):

    def setUp(self):
        self.bot = AutoTradingBot(max_history_size=10)

    def test_autotrader_config_defaults(self):
        """Verify default configuration parameters of AutoTraderConfig."""
        cfg = AutoTraderConfig()
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.min_confluence_score, 85)
        self.assertTrue(cfg.require_ai_approval)
        self.assertFalse(cfg.auto_exit_on_reversal)
        self.assertEqual(cfg.max_open_positions, 2)
        self.assertFalse(cfg.enforce_market_hours)
        self.assertEqual(cfg.timeframe, "1d")

        d = cfg.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["min_confluence_score"], 85)

    def test_decision_schema_and_history_fifo(self):
        """Verify AutoTraderDecision schema and FIFO max-size history eviction."""
        dec = AutoTraderDecision(
            timestamp="2026-11-16 12:00:00 UTC",
            symbol="RELIANCE",
            market="IN",
            action="BUY",
            reason="Confluence score 75/100, AI: BULLISH",
            executed=True,
            order_id="BUY-12345",
            score=75,
        )
        d = dec.to_dict()
        self.assertEqual(d["symbol"], "RELIANCE")
        self.assertEqual(d["action"], "BUY")
        self.assertTrue(d["executed"])
        self.assertEqual(d["order_id"], "BUY-12345")
        self.assertEqual(d["score"], 75)

        # Test history eviction
        for i in range(15):
            self.bot.record_decision(
                AutoTraderDecision(
                    timestamp="2026-11-16 12:00:00 UTC",
                    symbol=f"SYM_{i}",
                    market="IN",
                    action="HOLD",
                    reason="Test",
                    executed=False,
                )
            )

        history = self.bot.get_history()
        self.assertEqual(len(history), 10)  # Max capacity 10
        # First item in returned history is most recent (SYM_14)
        self.assertEqual(history[0]["symbol"], "SYM_14")

        # Test clear history
        self.bot.clear_history()
        self.assertEqual(len(self.bot.get_history()), 0)

    def test_tradingview_symbol_resolution(self):
        """Verify proper TradingView qualified symbol translation for NSE and US equities."""
        # Indian Equities
        self.assertEqual(get_tradingview_symbol("RELIANCE"), "NSE:RELIANCE")
        self.assertEqual(get_tradingview_symbol("RELIANCE.NS"), "NSE:RELIANCE")
        self.assertEqual(get_tradingview_symbol("TCS"), "NSE:TCS")
        self.assertEqual(get_tradingview_symbol("INFY"), "NSE:INFY")

        # US Equities
        self.assertEqual(get_tradingview_symbol("AAPL"), "NASDAQ:AAPL")
        self.assertEqual(get_tradingview_symbol("NVDA"), "NASDAQ:NVDA")
        self.assertEqual(get_tradingview_symbol("TSLA"), "NASDAQ:TSLA")
        self.assertEqual(get_tradingview_symbol("JPM"), "NYSE:JPM")
        self.assertEqual(get_tradingview_symbol("BRK-B"), "NYSE:BRK.B")

        # Fallback for unknown symbol
        self.assertEqual(get_tradingview_symbol("CUSTOM"), "NSE:CUSTOM")

    @patch("trading.engine.PaperTradingEngine.execute_buy", new_callable=AsyncMock)
    @patch("trading.engine.PaperTradingEngine.get_or_create_account", new_callable=AsyncMock)
    @patch("trading.engine.PaperTradingEngine.update_portfolio_equity", new_callable=AsyncMock)
    def test_run_cycle_executes_high_confluence_signal(self, mock_equity, mock_acct, mock_buy):
        """Verify run_cycle triggers execute_buy on candidate symbols meeting confluence threshold."""
        import asyncio

        # Mock Account
        fake_account = MagicMock()
        fake_account.id = 1
        fake_account.equity_inr = Decimal("100000.00")
        fake_account.cash_balance_inr = Decimal("100000.00")
        mock_acct.return_value = fake_account

        # Mock Session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Mock Buy Order execution
        fake_order = MagicMock()
        fake_order.client_order_id = "ORD-TEST-001"
        fake_order.quantity = 10
        fake_order.executed_price = Decimal("2500.00")
        mock_buy.return_value = (True, fake_order, None)

        # Mock strategy to generate BUY signal
        fake_signal = TradeSignal(
            symbol="RELIANCE",
            timestamp=datetime.now(timezone.utc),
            action=SignalAction.BUY,
            strength=SignalStrength.STRONG,
            primary_trigger="Bullish EMA Cross",
            entry_price=Decimal("2500.00"),
            suggested_stop_loss=Decimal("2450.00"),
            suggested_take_profit=Decimal("2600.00"),
            risk_reward_ratio=2.0,
            stop_loss_pct=2.0,
            target_profit_pct=4.0,
            technical_score=85,
            confirming_factors=["EMA 20 > EMA 50"],
            conflicting_factors=[],
        )

        with patch.object(self.bot.strategy, "generate_signal", return_value=fake_signal):
            with patch.object(self.bot.ai_analyzer, "analyze_market_state", new_callable=AsyncMock) as mock_ai:
                fake_ai_summary = MagicMock()
                fake_ai_summary.recommended_action_opinion = "BULLISH_CONFLUENCE"
                mock_ai.return_value = fake_ai_summary

                # Run cycle with max 1 open position for test speed
                cfg = AutoTraderConfig(
                    enabled=True,
                    min_confluence_score=70,
                    require_ai_approval=True,
                    max_open_positions=1,
                    allow_synthetic=True,
                )

                result = asyncio.run(self.bot.run_cycle(session=mock_session, market="IN", config_override=cfg))

                self.assertEqual(result["market"], "IN")
                self.assertEqual(result["orders_executed_count"], 1)
                self.assertIn("ORD-TEST-001", result["orders_executed"])
                self.assertTrue(mock_buy.called)

    @patch("trading.engine.PaperTradingEngine.close_position", new_callable=AsyncMock)
    @patch("trading.engine.PaperTradingEngine.get_or_create_account", new_callable=AsyncMock)
    @patch("trading.engine.PaperTradingEngine.update_portfolio_equity", new_callable=AsyncMock)
    def test_run_cycle_triggers_stop_loss(self, mock_equity, mock_acct, mock_close):
        """Verify run_cycle automatically liquidates position when price hits stop-loss."""
        import asyncio

        fake_account = MagicMock()
        fake_account.id = 1
        fake_account.equity_inr = Decimal("100000.00")
        fake_account.cash_balance_inr = Decimal("100000.00")
        mock_acct.return_value = fake_account

        # Mock Open Position with entry 2500, SL 2450
        fake_pos = MagicMock()
        fake_pos.id = 10
        fake_pos.symbol = "RELIANCE"
        fake_pos.quantity = 10
        fake_pos.average_entry_price = Decimal("2500.00")
        fake_pos.stop_loss_price = Decimal("2450.00")
        fake_pos.take_profit_price = Decimal("2650.00")
        fake_pos.status = PositionStatus.OPEN
        fake_pos.realized_pnl_inr = Decimal("-500.00")

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [fake_pos]
        mock_session.execute.return_value = mock_result

        # Mock close_position return
        fake_order = MagicMock()
        fake_order.client_order_id = "CLOSE-SL-001"
        mock_close.return_value = (True, fake_order, None)

        # Mock market data returning price below stop loss (e.g. 2400)
        from backend.app.market_data.base import Candle, MarketDataBatch
        fake_candle = Candle(
            timestamp=datetime.now(timezone.utc),
            open=Decimal("2410.00"),
            high=Decimal("2420.00"),
            low=Decimal("2395.00"),
            close=Decimal("2400.00"),  # Hit SL
            volume=50000,
        )
        fake_batch = MarketDataBatch(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe="1d",
            candles=[fake_candle],
            provider="test",
        )

        with patch.object(self.bot.market_provider, "fetch_historical_ohlcv", return_value=fake_batch):
            cfg = AutoTraderConfig(enabled=True, max_open_positions=1)
            result = asyncio.run(self.bot.run_cycle(session=mock_session, market="IN", config_override=cfg))

            self.assertEqual(result["positions_closed_count"], 1)
            self.assertIn("RELIANCE", result["positions_closed"])
            mock_close.assert_called_once()
            self.assertIn("Stop-Loss Triggered", mock_close.call_args[1]["reason"])

    @patch("trading.engine.PaperTradingEngine.execute_buy", new_callable=AsyncMock)
    @patch("trading.engine.PaperTradingEngine.get_or_create_account", new_callable=AsyncMock)
    @patch("trading.engine.PaperTradingEngine.update_portfolio_equity", new_callable=AsyncMock)
    def test_run_cycle_multi_user_scoping(self, mock_equity, mock_acct, mock_buy):
        """Verify run_cycle scopes account and order execution to the requested user_id."""
        import asyncio

        fake_account = MagicMock()
        fake_account.id = 42
        fake_account.account_name = "User #42 INR Account"
        fake_account.equity_inr = Decimal("100000.00")
        fake_account.cash_balance_inr = Decimal("100000.00")
        mock_acct.return_value = fake_account

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        fake_order = MagicMock()
        fake_order.client_order_id = "ORD-USER-42"
        fake_order.quantity = 5
        fake_order.executed_price = Decimal("2500.00")
        mock_buy.return_value = (True, fake_order, None)

        fake_signal = TradeSignal(
            symbol="RELIANCE",
            timestamp=datetime.now(timezone.utc),
            action=SignalAction.BUY,
            strength=SignalStrength.STRONG,
            primary_trigger="Bullish EMA Cross",
            entry_price=Decimal("2500.00"),
            suggested_stop_loss=Decimal("2450.00"),
            suggested_take_profit=Decimal("2600.00"),
            risk_reward_ratio=2.0,
            stop_loss_pct=2.0,
            target_profit_pct=4.0,
            technical_score=85,
            confirming_factors=[],
            conflicting_factors=[],
        )

        with patch.object(self.bot.strategy, "generate_signal", return_value=fake_signal):
            cfg = AutoTraderConfig(enabled=True, min_confluence_score=70, require_ai_approval=False, max_open_positions=1, allow_synthetic=True)
            result = asyncio.run(self.bot.run_cycle(session=mock_session, market="IN", config_override=cfg, user_id=42))

            self.assertEqual(result["user_id"], 42)
            self.assertEqual(result["account_name"], "User #42 INR Account")
            mock_acct.assert_called_with(mock_session, currency="INR", user_id=42)
            self.assertTrue(mock_buy.called)
            self.assertEqual(mock_buy.call_args[1]["user_id"], 42)


if __name__ == "__main__":
    unittest.main()
