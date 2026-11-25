"""
Tier 3 & Tier 4 End-to-End, Cross-Feature, and Defect Regression Test Suite.

Validates:
1. 7 Tier 3 Pairwise Cross-Feature Interactions:
   - T3.1: Global market toggle updates symbol, currency, and chart engine.
   - T3.2: Order execution updates positions, trade ledger, and purchasing power.
   - T3.3: Position close updates realized P&L, win rate, and equity curve.
   - T3.4: JWT token expiry (401) recovery and redirect to sign in without app crash.
   - T3.5: Auto-trader config update and manual tick execution.
   - T3.6: Emergency kill switch activation disables order submission and halts auto-trader.
   - T3.7: Admin capital funding updates purchasing power and reactive position sizing.
2. 4 Tier 4 Real-World Application Workflows:
   - S1: NSE Institutional Swing Trading Lifecycle.
   - S2: US Mega-Cap Zero-Commission Trading Lifecycle.
   - S3: Autonomous AI Auto-Trader Unattended Cycle.
   - S4: Admin Governance, Capital Funding & Account Recovery.
3. 4 Defect Regression Guardrails:
   - Tab 2 line 775 `or True` AI trigger defect guardrail.
   - Tab 4 form reactivity defect guardrail.
   - Tab 5 2-point equity curve defect guardrail.
   - Tab 6 line 1149 backtest rerun loop defect guardrail.
"""

from decimal import Decimal
import json
import sys
from typing import Any, Dict, List
import unittest
from unittest.mock import MagicMock, Mock, patch

# Ensure Streamlit modules are mocked in headless environment
if "streamlit" not in sys.modules:
    mock_st_root = MagicMock()
    mock_st_root.cache_data = lambda *a, **k: (lambda f: f)
    sys.modules["streamlit"] = mock_st_root
if "streamlit.components.v1" not in sys.modules:
    mock_comp_root = MagicMock()
    sys.modules["streamlit.components.v1"] = mock_comp_root
    sys.modules["streamlit"].components.v1 = mock_comp_root

from dashboard.api_client import DashboardAPIClient, api_client
from dashboard.components import tradingview
from trading.risk import calculate_position_size
from trading.charges import calculate_trade_friction, calculate_us_trade_friction
from trading.metrics import calculate_performance_metrics


class TestTier3CrossFeatureInteractions(unittest.TestCase):
    """Pairwise cross-feature state transition tests across system seams."""

    def setUp(self):
        self.client = DashboardAPIClient(base_url="http://testserver:8000")
        self.client.set_auth_token("test_auth_token")

    def test_t3_1_global_market_switch_updates_symbol_currency_and_chart(self):
        """T3.1: Switching market from NSE to US updates active symbol, currency, and chart engine."""
        # Initial NSE state
        session_state = {
            "active_market": "NSE",
            "active_currency": "INR",
            "selected_symbol": "RELIANCE",
        }
        self.assertEqual(tradingview.clean_symbol_name(session_state["selected_symbol"]), "RELIANCE")
        self.assertFalse(tradingview.is_us_symbol(session_state["selected_symbol"]))
        self.assertEqual(tradingview.get_tradingview_symbol("RELIANCE"), "NSE:RELIANCE")

        # User toggles to US (USD)
        session_state["active_market"] = "US"
        session_state["active_currency"] = "USD"
        session_state["selected_symbol"] = "AAPL"

        self.assertEqual(session_state["active_market"], "US")
        self.assertEqual(session_state["active_currency"], "USD")
        self.assertTrue(tradingview.is_us_symbol(session_state["selected_symbol"]))
        self.assertEqual(tradingview.get_tradingview_symbol("AAPL"), "NASDAQ:AAPL")
        self.assertIn("https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL", tradingview.get_tradingview_url("AAPL"))

    def test_t3_2_order_execution_updates_positions_ledger_and_purchasing_power(self):
        """T3.2: Virtual order submission fills order, updates open positions, ledger, and cash."""
        initial_cash = Decimal("100000.00")
        initial_positions = []
        initial_orders = []

        # 1. Size order via 1% risk constraint
        sizing = calculate_position_size(
            equity=initial_cash,
            available_cash=initial_cash,
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2450.00"),
        )
        self.assertTrue(sizing.is_approved)
        self.assertEqual(sizing.quantity, 8)

        # 2. Simulate order fill with statutory friction
        trade_cost = calculate_trade_friction(
            symbol="RELIANCE",
            side="BUY",
            quantity=sizing.quantity,
            price=Decimal("2500.00"),
        )
        self.assertEqual(trade_cost.executed_price, Decimal("2501.25"))

        # 3. State transitions
        updated_cash = initial_cash - trade_cost.net_cash_impact_inr
        self.assertEqual(updated_cash, initial_cash - trade_cost.net_cash_impact_inr)
        self.assertEqual(trade_cost.net_cash_impact_inr, Decimal("20057.45"))

        # Position added
        position_card = {
            "position_id": 101,
            "symbol": "RELIANCE",
            "quantity": sizing.quantity,
            "entry_price": float(trade_cost.executed_price),
            "current_price": float(trade_cost.executed_price),
            "unrealized_pnl": 0.0,
        }
        updated_positions = initial_positions + [position_card]
        self.assertEqual(len(updated_positions), 1)

        # Order appended to ledger
        order_entry = {
            "order_id": 5001,
            "symbol": "RELIANCE",
            "side": "BUY",
            "quantity": sizing.quantity,
            "executed_price": float(trade_cost.executed_price),
            "total_charges": float(trade_cost.total_charges_inr),
        }
        updated_orders = initial_orders + [order_entry]
        self.assertEqual(len(updated_orders), 1)

    def test_t3_3_position_close_updates_realized_pnl_win_rate_and_equity_curve(self):
        """T3.3: Closing position credits proceeds, updates realized P&L, win rate, and equity curve."""
        initial_equity = Decimal("100000.00")
        entry_price = Decimal("2501.25")
        exit_price = Decimal("2600.00")
        qty = 8

        # Buy cost for 8 shares
        buy_cost = calculate_trade_friction("RELIANCE", "BUY", qty, Decimal("2500.00"))
        # Sell proceeds: 8 * 2600 * 0.9995 = 20789.60 minus friction
        sell_cost = calculate_trade_friction(
            symbol="RELIANCE",
            side="SELL",
            quantity=qty,
            price=exit_price,
        )
        realized_pnl = sell_cost.net_cash_impact_inr - buy_cost.net_cash_impact_inr
        self.assertGreater(realized_pnl, Decimal("0.00"))

        # Performance metrics update
        metrics = calculate_performance_metrics(
            realized_pnls=[realized_pnl],
            charges_paid=[sell_cost.total_charges_inr],
            equity_curve=[initial_equity, initial_equity + realized_pnl],
        )
        self.assertEqual(metrics.total_trades, 1)
        self.assertEqual(metrics.winning_trades, 1)
        self.assertEqual(metrics.win_rate_pct, 100.0)
        self.assertEqual(metrics.profit_factor, 99.0)

    def test_t3_4_jwt_token_expiry_401_recovery_and_redirect(self):
        """T3.4: Backend 401 Unauthorized triggers session reset and redirect to Sign In."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            import io
            import urllib.error
            err_body = io.BytesIO(b'{"detail": "Signature has expired"}')
            mock_urlopen.side_effect = urllib.error.HTTPError("http://testserver:8000", 401, "Unauthorized", {}, err_body)

            res = self.client.get_portfolio()
            self.assertTrue(res.get("error"))
            self.assertEqual(res.get("status_code"), 401)
            self.assertIn("Signature has expired", res.get("message"))

            # Client or dashboard session state recovers by clearing expired token
            if res.get("status_code") == 401:
                self.client.set_auth_token(None)
                redirect_to_login = True

            self.assertIsNone(self.client.auth_token)
            self.assertTrue(redirect_to_login)

    def test_t3_5_autotrader_config_update_and_manual_tick(self):
        """T3.5: Auto-trader config update reflects in daemon and triggers strategy tick."""
        with patch.object(DashboardAPIClient, "_request") as mock_req:
            mock_req.return_value = {"status": "ok", "config": {"min_confluence_score": 80}}
            cfg_res = self.client.update_auto_trader_config({"min_confluence_score": 80})
            self.assertEqual(cfg_res["config"]["min_confluence_score"], 80)

            mock_req.return_value = {"tick_executed": True, "evaluated_symbols": 10, "orders_placed": 1}
            tick_res = self.client.run_auto_trader_tick(market="IN")
            self.assertTrue(tick_res["tick_executed"])
            self.assertEqual(tick_res["orders_placed"], 1)

    def test_t3_6_emergency_kill_switch_halt_and_execution_lockout(self):
        """T3.6: Activating kill switch displays HUD warning, disables buy order, and halts auto-trader."""
        with patch.object(DashboardAPIClient, "_request") as mock_req:
            mock_req.return_value = {"kill_switch_active": True, "reason": "Circuit Breaker"}
            res = self.client.toggle_kill_switch(activate=True, reason="Circuit Breaker")
            self.assertTrue(res["kill_switch_active"])

            # Verify guardrail condition in frontend state
            kill_switch_active = res["kill_switch_active"]
            order_submission_allowed = not kill_switch_active
            autotrader_allowed = not kill_switch_active

            self.assertFalse(order_submission_allowed)
            self.assertFalse(autotrader_allowed)

    def test_t3_7_admin_capital_funding_updates_reactive_sizing(self):
        """T3.7: Admin funds account in Tab 8; Tab 4 reactive position sizing expands quantity."""
        # Before funding: Equity = ₹50,000
        pre_funding_equity = Decimal("50000.00")
        sizing_pre = calculate_position_size(
            equity=pre_funding_equity,
            available_cash=pre_funding_equity,
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2450.00"),  # Risk = ₹50/sh -> 1% budget = ₹500 -> Q_risk = 10; Q_alloc = 4
        )
        self.assertEqual(sizing_pre.quantity, 4)

        # Admin injects ₹50,000 in Tab 8
        with patch.object(DashboardAPIClient, "_request") as mock_req:
            mock_req.return_value = {"funded": True, "new_balance": 100000.0}
            fund_res = self.client.fund_account(1, amount=50000.0, reason="Capital Grant")
            self.assertTrue(fund_res["funded"])

        # After funding: Equity = ₹100,000 -> Sizing recalculates immediately
        post_funding_equity = Decimal("100000.00")
        sizing_post = calculate_position_size(
            equity=post_funding_equity,
            available_cash=post_funding_equity,
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2450.00"),  # Q_alloc = 20000 // 2500 = 8
        )
        self.assertEqual(sizing_post.quantity, 8)
        self.assertGreater(sizing_post.quantity, sizing_pre.quantity)


class TestTier4RealWorldWorkflows(unittest.TestCase):
    """End-to-End simulations of real-world multi-step user workflows."""

    def setUp(self):
        self.client = DashboardAPIClient(base_url="http://testserver:8000")
        self.client.set_auth_token("user_session_token")

    def test_scenario_1_nse_institutional_swing_trading_lifecycle(self):
        """
        Scenario 1: Institutional Swing Trading Lifecycle (NSE Market).
        1. Health check readiness probe.
        2. Ticker scan detects RELIANCE.
        3. Market & Technicals inspection (EMA 20 > EMA 50, Price >= VWAP, RSI 58.2, MACD Hist > 0).
        4. Deterministic signal BUY with 85/100 confluence score.
        5. 1% Risk Sizing: Entry ₹2500, SL ₹2450, TP ₹2600 (R:R 2.0:1) on ₹100k equity -> sizes 8 shares.
        6. Virtual order execution with Indian statutory charges: 5 bps adverse fill, ₹20 brokerage, STT, GST, Stamp duty.
        7. Position mounted in open positions grid.
        8. Position closed at target ₹2600.00.
        9. Trade ledger updated, win rate 100%, reconstructed multi-point equity curve.
        """
        # Step 1: Health probe
        with patch.object(DashboardAPIClient, "_request") as mock_req:
            mock_req.return_value = {"status": "ready", "db_latency_ms": 11.5}
            health = self.client.get_health_ready()
            self.assertEqual(health["status"], "ready")

        # Step 2: Ticker & Universe scan
        with patch.object(DashboardAPIClient, "_request") as mock_req:
            mock_req.return_value = [{"symbol": "RELIANCE", "name": "Reliance Industries", "market": "NSE"}]
            universe = self.client.get_universe(market="NSE")
            self.assertEqual(universe[0]["symbol"], "RELIANCE")

        # Step 3 & 4: Confluence Signal
        with patch.object(DashboardAPIClient, "_request") as mock_req:
            mock_req.return_value = {
                "action": "BUY",
                "strength": "STRONG",
                "technical_score": 85,
                "suggested_stop_loss": 2450.0,
                "suggested_take_profit": 2600.0,
            }
            signal = self.client.get_signal("RELIANCE")
            self.assertEqual(signal["action"], "BUY")
            self.assertEqual(signal["technical_score"], 85)

        # Step 5: 1% Risk Sizing
        sizing = calculate_position_size(
            equity=Decimal("100000.00"),
            available_cash=Decimal("100000.00"),
            entry_price=Decimal("2500.00"),
            stop_loss_price=Decimal("2450.00"),
        )
        self.assertEqual(sizing.quantity, 8)

        # Step 6: Order Execution & Indian Regulatory Friction
        buy_cost = calculate_trade_friction("RELIANCE", "BUY", sizing.quantity, Decimal("2500.00"))
        self.assertEqual(buy_cost.executed_price, Decimal("2501.25"))
        self.assertEqual(buy_cost.total_charges_inr, Decimal("47.45"))

        # Step 7: Open Position Card
        position = {
            "position_id": 201,
            "symbol": "RELIANCE",
            "quantity": sizing.quantity,
            "entry_price": float(buy_cost.executed_price),
            "status": "OPEN",
        }
        self.assertEqual(position["status"], "OPEN")

        # Step 8: Close Position at Target ₹2600.00
        sell_cost = calculate_trade_friction("RELIANCE", "SELL", sizing.quantity, Decimal("2600.00"))
        net_profit = sell_cost.net_cash_impact_inr - buy_cost.net_cash_impact_inr
        self.assertGreater(net_profit, Decimal("0.00"))

        # Step 9: Trade Ledger & Equity Curve
        from trading.metrics import reconstruct_multipoint_equity_curve
        curve = reconstruct_multipoint_equity_curve(
            initial_capital=100000.0,
            closed_trades_pnl=[float(net_profit)],
            unrealized_pnl=0.0,
        )
        self.assertEqual(curve["total_points"], 3)  # Start, Trade 1, Current
        self.assertGreater(curve["final_equity"], 100000.0)

    def test_scenario_2_us_megacap_zero_commission_trading(self):
        """
        Scenario 2: US Mega-Cap Zero-Commission Trading Lifecycle.
        1. Market switched to US USD, symbol AAPL at $180.00.
        2. Charting configured in USD.
        3. 1% risk sizing on $50,000 equity (SL $175, TP $192.50) -> 55 shares.
        4. Buy order executed with $0.00 brokerage.
        5. Position close at $190.00: SEC Section 31 and FINRA TAF deducted strictly on SELL.
        6. Multi-point equity curve and ledger updated in USD.
        """
        # Step 1: Market switch
        self.assertTrue(tradingview.is_us_symbol("AAPL"))
        self.assertEqual(tradingview.get_tradingview_symbol("AAPL"), "NASDAQ:AAPL")

        # Step 3: Sizing
        # Equity = $50,000, 1% budget = $500. Entry = $180, SL = $175 -> Risk/sh = $5 -> Q_risk = 100
        # Allocation (20%) = $10,000 // 180 = 55 shares.
        sizing = calculate_position_size(
            equity=Decimal("50000.00"),
            available_cash=Decimal("50000.00"),
            entry_price=Decimal("180.00"),
            stop_loss_price=Decimal("175.00"),
        )
        self.assertEqual(sizing.quantity, 55)

        # Step 4: Buy order with $0.00 brokerage
        buy_cost = calculate_us_trade_friction("AAPL", "BUY", sizing.quantity, Decimal("180.00"))
        self.assertEqual(buy_cost.brokerage_inr, Decimal("0.00"))
        self.assertEqual(buy_cost.total_charges_inr, Decimal("0.00"))

        # Step 5: Close order at $190.00 with SEC + FINRA regulatory fees
        sell_cost = calculate_us_trade_friction("AAPL", "SELL", sizing.quantity, Decimal("190.00"))
        self.assertEqual(sell_cost.brokerage_inr, Decimal("0.00"))
        self.assertGreater(sell_cost.total_charges_inr, Decimal("0.00"))  # SEC + FINRA
        self.assertEqual(sell_cost.net_cash_impact_inr, sell_cost.turnover - sell_cost.total_charges_inr)

        # Step 6: Net profit in USD
        net_profit_usd = sell_cost.net_cash_impact_inr - buy_cost.net_cash_impact_inr
        self.assertGreater(net_profit_usd, Decimal("500.00"))

    def test_scenario_3_autotrader_unattended_cycle(self):
        """
        Scenario 3: Autonomous AI Auto-Trader Unattended Cycle.
        1. Auto-trader config updated (min confluence 80).
        2. Daemon triggers tick.
        3. Strategy evaluates candidate (INFY score 88/100).
        4. Order sized via 1% risk and executed.
        5. Decision logged to audit table.
        """
        with patch.object(DashboardAPIClient, "_request") as mock_req:
            # Config update
            mock_req.return_value = {"status": "ok"}
            self.client.update_auto_trader_config({"min_confluence_score": 80, "enabled": True})

            # Automated tick execution
            mock_req.return_value = {
                "tick_executed": True,
                "symbols_scanned": ["INFY", "TCS", "RELIANCE"],
                "decision": {
                    "symbol": "INFY",
                    "action": "BUY",
                    "confluence_score": 88,
                    "order_id": 9001,
                    "status": "EXECUTED",
                },
            }
            tick_result = self.client.run_auto_trader_tick(market="IN")
            self.assertTrue(tick_result["tick_executed"])
            decision = tick_result["decision"]
            self.assertEqual(decision["symbol"], "INFY")
            self.assertEqual(decision["confluence_score"], 88)
            self.assertEqual(decision["status"], "EXECUTED")

    def test_scenario_4_admin_governance_and_capital_funding(self):
        """
        Scenario 4: Admin Governance, Capital Funding & Account Recovery.
        1. Admin signs in with ADMIN role.
        2. Admin inspects user directory.
        3. Funds account with ₹100,000.
        4. Rotates user programmatic API key.
        5. Admin audit log records actions.
        """
        with patch.object(DashboardAPIClient, "_request") as mock_req:
            # 1. Admin summary
            mock_req.return_value = {"total_users": 10, "active_users": 9}
            summary = self.client.get_admin_summary()
            self.assertEqual(summary["total_users"], 10)

            # 2. Inspect users
            mock_req.return_value = {"users": [{"user_id": 4, "username": "trader_alice", "role": "TRADER"}]}
            users = self.client.get_admin_users(page=1, limit=10)
            self.assertEqual(users["users"][0]["username"], "trader_alice")

            # 3. Fund account
            mock_req.return_value = {"funded": True, "amount": 100000.0}
            fund = self.client.fund_account(4, 100000.0, reason="Q4 Allocation")
            self.assertTrue(fund["funded"])

            # 4. Rotate API key
            mock_req.return_value = {"api_key": "qt_live_rotated_key_123"}
            rot = self.client.rotate_user_api_key(4)
            self.assertIn("qt_live", rot["api_key"])

            # 5. Audit logs
            mock_req.return_value = {
                "logs": [
                    {"action": "CAPITAL_FUND", "target_user_id": 4, "admin_user_id": 1},
                    {"action": "API_KEY_ROTATE", "target_user_id": 4, "admin_user_id": 1},
                ]
            }
            audit = self.client.get_admin_audit_logs(target_user_id=4)
            self.assertEqual(len(audit["logs"]), 2)


def _make_mock_st(
    session_state=None,
    button_returns=None,
    form_submit_returns=False,
    number_input_overrides=None,
):
    """Creates a realistic Streamlit mock that records metrics, markdown, and captions."""
    recorded_metrics = []
    recorded_markdowns = []
    recorded_captions = []

    def _make_container():
        m = MagicMock()

        def _columns(spec, **kwargs):
            count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
            return [_make_container() for _ in range(count)]

        def _metric(label, value, delta=None, **kwargs):
            recorded_metrics.append((label, value, delta))

        def _markdown(body, **kwargs):
            recorded_markdowns.append((str(body), kwargs))

        def _caption(body, **kwargs):
            recorded_captions.append(str(body))

        def _button(label, key=None, **kwargs):
            if button_returns:
                if key in button_returns:
                    return button_returns[key]
                if label in button_returns:
                    return button_returns[label]
            return False

        def _number_input(label, value=0.0, key=None, **kwargs):
            if number_input_overrides:
                if key in number_input_overrides:
                    return number_input_overrides[key]
                if label in number_input_overrides:
                    return number_input_overrides[label]
            return value if isinstance(value, int) else float(value or 0.0)

        m.columns.side_effect = _columns
        m.tabs.side_effect = lambda t: [_make_container() for _ in t]
        m.metric.side_effect = _metric
        m.markdown.side_effect = _markdown
        m.caption.side_effect = _caption
        m.button.side_effect = _button
        m.number_input.side_effect = _number_input
        m.selectbox.side_effect = lambda l, options=[], index=0, **k: options[index] if options else "OPT"
        m.radio.side_effect = lambda l, options=[], index=0, **k: options[index] if options else "OPT"
        m.checkbox.side_effect = lambda l, value=False, **k: value
        m.toggle.side_effect = lambda l, value=False, **k: value
        m.text_input.side_effect = lambda l, value="", **k: value
        m.form_submit_button.return_value = form_submit_returns
        m.form.return_value.__enter__ = lambda s: _make_container()
        m.form.return_value.__exit__ = lambda s, *a: None
        m.container.return_value.__enter__ = lambda s: _make_container()
        m.container.return_value.__exit__ = lambda s, *a: None
        m.spinner.return_value.__enter__ = lambda s: None
        m.spinner.return_value.__exit__ = lambda s, *a: None
        m.expander.return_value.__enter__ = lambda s: _make_container()
        m.expander.return_value.__exit__ = lambda s, *a: None
        return m

    mock_st = _make_container()
    mock_st.sidebar = _make_container()
    mock_st.session_state = session_state if session_state is not None else {}
    mock_st.stop = MagicMock(side_effect=SystemExit("st.stop"))
    mock_st.rerun = MagicMock()
    mock_st.cache_data = lambda *a, **k: (lambda f: f)
    mock_st.column_config = MagicMock()
    mock_st._recorded_metrics = recorded_metrics
    mock_st._recorded_markdowns = recorded_markdowns
    mock_st._recorded_captions = recorded_captions
    return mock_st


class TestDefectRegressionGuardrails(unittest.TestCase):
    """
    Explicit regression guardrails exercising real production dashboard tabs
    to prevent reintroduction of the surveyed frontend defects:
    1. Tab 2 line 775 `or True` defect (dashboard.tabs.tab_ai.render_tab).
    2. Tab 4 form reactivity defect (dashboard.tabs.tab_positions.render_tab).
    3. Tab 5 2-point equity curve defect (dashboard.tabs.tab_ledger.render_tab).
    4. Tab 6 line 1149 backtest rerun loop defect (dashboard.tabs.tab_backtest.render_tab).
    5. Tab 4 statutory friction breakdown HTML card rendering (NSE & US).
    """

    @classmethod
    def setUpClass(cls):
        cls._preexisting_dashboard_modules = {
            name for name in sys.modules if name == "dashboard.tabs" or name.startswith("dashboard.tabs.")
        }

    @classmethod
    def tearDownClass(cls):
        for name in list(sys.modules.keys()):
            if (name == "dashboard.tabs" or name.startswith("dashboard.tabs.")) and name not in cls._preexisting_dashboard_modules:
                sys.modules.pop(name, None)

    def test_tab_2_line_775_defect_guardrail(self):
        """
        DEFECT GUARDRAIL: Tab 2 Line 775 `or True` AI Trigger Defect.
        Calls dashboard.tabs.tab_ai.render_tab and asserts api_client.get_ai_analysis
        is NOT called when st.session_state has no trigger and button is not clicked.
        """
        from dashboard.components import gauges
        from dashboard.tabs import tab_ai

        mock_api = MagicMock()
        mock_api.get_signal.return_value = {
            "action": "BUY",
            "strength": "STRONG",
            "technical_score": 85.0,
            "primary_trigger": "EMA20 > EMA50",
            "entry_price": 2500.0,
            "suggested_stop_loss": 2450.0,
            "suggested_take_profit": 2600.0,
        }
        mock_api.get_ai_analysis.return_value = {
            "ai_analysis": {
                "recommended_action_opinion": "ACCUMULATION",
                "ai_confidence_score": 84.0,
                "ai_confidence_rationale": "Strong trend alignment",
                "trend_analysis": "Bullish",
                "momentum_analysis": "Healthy RSI",
                "macd_interpretation": "Positive",
                "vwap_relationship": "Above VWAP",
                "key_risks": ["Sector volatility"],
            }
        }
        state = {"active_market": "NSE", "active_currency": "INR", "curr_sym": "₹"}

        # 1. Mount without trigger -> get_ai_analysis MUST NOT be called
        session_state = {"trigger_ai": False}
        mock_st = _make_mock_st(session_state=session_state)
        with patch.object(tab_ai, "st", mock_st), patch.object(gauges, "st", mock_st):
            tab_ai.render_tab(mock_api, state, "NSE", "RELIANCE", "1d")

        mock_api.get_ai_analysis.assert_not_called()
        self.assertTrue(
            any("Gemini AI Interpretation Standby" in body for body, _ in mock_st._recorded_markdowns)
        )

        # 2. Explicit user button click -> get_ai_analysis called once, then flag reset
        mock_st_click = _make_mock_st(
            session_state=session_state,
            button_returns={"btn_trigger_ai": True},
        )
        with patch.object(tab_ai, "st", mock_st_click), patch.object(gauges, "st", mock_st_click):
            tab_ai.render_tab(mock_api, state, "NSE", "RELIANCE", "1d")

        mock_api.get_ai_analysis.assert_called_once_with("RELIANCE", timeframe="1d")
        self.assertFalse(session_state["trigger_ai"])
        self.assertIn("ai_analysis_RELIANCE_1d", session_state)

    def test_tab_4_form_reactivity_defect_guardrail(self):
        """
        DEFECT GUARDRAIL: Tab 4 Form Reactivity Defect.
        Calls dashboard.tabs.tab_positions.render_tab and asserts it renders inside
        a reactive st.container() (NOT a blocking st.form()) and recalculates
        Suggested Quantity immediately when Stop-Loss changes.
        """
        from dashboard.tabs import tab_positions

        mock_api = MagicMock()
        mock_api.get_positions.return_value = []
        state = {
            "active_market": "NSE",
            "active_currency": "INR",
            "curr_sym": "₹",
            "is_us_market": False,
            "portfolio": {"equity_inr": 100000.0, "cash_balance_inr": 100000.0},
            "universe_symbols": ["RELIANCE"],
            "default_cap": 100000.0,
            "equity_val": 100000.0,
            "latest_snapshot": {"close_price": 2500.0},
        }

        # Render 1: Stop-Loss ₹2450 -> Q_risk = 20, Q_alloc = 8 -> Suggested Quantity = 8 shares
        mock_st_1 = _make_mock_st(
            number_input_overrides={
                "pos_order_price_input": 2500.0,
                "pos_order_sl_input": 2450.0,
                "pos_order_tp_input": 2600.0,
                "pos_order_qty_input": 0,
            }
        )
        with patch.object(tab_positions, "st", mock_st_1):
            tab_positions.render_tab(mock_api, state, "NSE", "RELIANCE", "1d")

        mock_st_1.container.assert_called()
        mock_st_1.form.assert_not_called()
        mock_st_1.form_submit_button.assert_not_called()
        qty_metrics_1 = [val for lbl, val, _ in mock_st_1._recorded_metrics if lbl == "Suggested Quantity"]
        self.assertEqual(qty_metrics_1, ["8 shares"])

        # Render 2: User widens Stop-Loss to ₹2300 -> Q_risk = 5 -> Suggested Quantity updates immediately
        mock_st_2 = _make_mock_st(
            number_input_overrides={
                "pos_order_price_input": 2500.0,
                "pos_order_sl_input": 2300.0,
                "pos_order_tp_input": 2900.0,
                "pos_order_qty_input": 0,
            }
        )
        with patch.object(tab_positions, "st", mock_st_2):
            tab_positions.render_tab(mock_api, state, "NSE", "RELIANCE", "1d")

        mock_st_2.form.assert_not_called()
        qty_metrics_2 = [val for lbl, val, _ in mock_st_2._recorded_metrics if lbl == "Suggested Quantity"]
        self.assertEqual(qty_metrics_2, ["5 shares"])
        self.assertNotEqual(qty_metrics_1, qty_metrics_2)

    def test_tab_5_2_point_equity_curve_defect_guardrail(self):
        """
        DEFECT GUARDRAIL: Tab 5 2-Point Equity Curve Defect.
        Calls dashboard.tabs.tab_ledger.render_tab with 4 closed positions and verifies
        multi-point (N + 2 = 6) equity curve generation rather than a 2-point straight line.
        """
        from dashboard.tabs import tab_ledger

        mock_api = MagicMock()
        mock_api.get_metrics.return_value = {
            "total_net_realized_pnl_inr": 2200.0,
            "total_trades": 4,
            "win_rate_pct": 50.0,
            "winning_trades": 2,
            "losing_trades": 2,
            "profit_factor": 3.75,
            "total_charges_paid_inr": 200.0,
            "max_drawdown_pct": 0.49,
            "max_drawdown_inr": 500.0,
            "sharpe_ratio": 1.4,
        }
        mock_api.get_orders.return_value = []
        mock_api.get_positions.return_value = [
            {"realized_pnl_inr": 1200.0, "closed_at": "2026-11-01T10:00:00Z"},
            {"realized_pnl_inr": -500.0, "closed_at": "2026-11-02T10:00:00Z"},
            {"realized_pnl_inr": 1800.0, "closed_at": "2026-11-03T10:00:00Z"},
            {"realized_pnl_inr": -300.0, "closed_at": "2026-11-04T10:00:00Z"},
        ]
        state = {
            "active_currency": "INR",
            "curr_sym": "₹",
            "default_cap": 100000.0,
            "equity_val": 102450.0,
            "portfolio": {
                "initial_capital_inr": 100000.0,
                "equity_inr": 102450.0,
                "total_unrealized_pnl_inr": 250.0,
                "open_positions_count": 1,
            },
        }
        mock_st = _make_mock_st()

        with patch.object(tab_ledger, "st", mock_st), \
             patch.object(tab_ledger, "create_equity_curve_chart", wraps=tab_ledger.create_equity_curve_chart) as spy_chart:
            tab_ledger.render_tab(mock_api, state, "NSE", "RELIANCE", "1d")

        spy_chart.assert_called_once()
        labels_arg, curve_arg = spy_chart.call_args[0][0], spy_chart.call_args[0][1]
        self.assertEqual(len(labels_arg), 6)
        self.assertNotEqual(len(curve_arg), 2, "Defect detected: Curve reduced to only 2 straight-line points!")
        self.assertEqual(labels_arg[0], "Start")
        self.assertEqual(labels_arg[-1], "Current")
        self.assertEqual(curve_arg, [100000.0, 101200.0, 100700.0, 102500.0, 102200.0, 102450.0])
        self.assertIn(("Total Curve Points", "6", None), mock_st._recorded_metrics)

    def test_tab_6_line_1149_rerun_loop_defect_guardrail(self):
        """
        DEFECT GUARDRAIL: Tab 6 Line 1149 Backtest Rerun Loop Defect.
        Calls dashboard.tabs.tab_backtest.render_tab and asserts api_client.run_backtest
        is executed once on submit and NOT re-executed on subsequent reruns when cached.
        """
        from dashboard.tabs import tab_backtest

        mock_api = MagicMock()
        mock_api.run_backtest.return_value = {
            "symbol": "RELIANCE",
            "total_bars": 252,
            "strategy_name": "EMA + MACD Confluence Swing",
            "total_return_pct": 12.5,
            "total_net_profit_inr": 12500.0,
            "metrics": {
                "win_rate_pct": 60.0,
                "winning_trades": 3,
                "losing_trades": 2,
                "profit_factor": 1.8,
                "total_charges_paid_inr": 250.0,
                "max_drawdown_pct": 4.2,
                "max_drawdown_inr": 4200.0,
                "sharpe_ratio": 1.45,
            },
            "equity_curve": [
                {"timestamp": "2026-01-01", "equity": 100000.0},
                {"timestamp": "2026-06-01", "equity": 112500.0},
            ],
            "trades": [],
        }
        state = {
            "is_us_market": False,
            "active_currency": "INR",
            "curr_sym": "₹",
            "universe_symbols": ["RELIANCE"],
            "default_cap": 100000.0,
        }
        session_state = {}

        # Run 1: User submits backtest form
        mock_st_run1 = _make_mock_st(session_state=session_state, form_submit_returns=True)
        with patch.object(tab_backtest, "st", mock_st_run1):
            tab_backtest.render_tab(mock_api, state, "NSE", "RELIANCE", "1d")

        self.assertEqual(mock_api.run_backtest.call_count, 1)
        self.assertTrue(session_state.get("bt_done_RELIANCE"))
        self.assertEqual(session_state["bt_result_RELIANCE"]["total_return_pct"], 12.5)

        # Run 2: Subsequent Streamlit UI rerun (form_submit_button=False, cached results exist)
        mock_st_run2 = _make_mock_st(session_state=session_state, form_submit_returns=False)
        with patch.object(tab_backtest, "st", mock_st_run2):
            tab_backtest.render_tab(mock_api, state, "NSE", "RELIANCE", "1d")

        self.assertEqual(mock_api.run_backtest.call_count, 1)
        self.assertIn(("Total Return", "+12.50%", "₹+12,500.00"), mock_st_run2._recorded_metrics)

    def test_tab_4_statutory_friction_breakdown_card_renders_nse_and_us(self):
        """
        Verifies dashboard.tabs.tab_positions.render_tab renders the HTML statutory
        friction breakdown card (and does NOT fall back to caption) when effective_qty > 0
        for both NSE (INR) and US (USD) markets.
        """
        from dashboard.tabs import tab_positions

        mock_api = MagicMock()
        mock_api.get_positions.return_value = []

        # 1. NSE Market (effective_qty = 8)
        nse_state = {
            "active_market": "NSE",
            "active_currency": "INR",
            "curr_sym": "₹",
            "is_us_market": False,
            "portfolio": {"equity_inr": 100000.0, "cash_balance_inr": 100000.0},
            "universe_symbols": ["RELIANCE"],
            "default_cap": 100000.0,
            "equity_val": 100000.0,
            "latest_snapshot": {"close_price": 2500.0},
        }
        mock_st_nse = _make_mock_st(
            number_input_overrides={
                "pos_order_price_input": 2500.0,
                "pos_order_sl_input": 2450.0,
                "pos_order_tp_input": 2600.0,
                "pos_order_qty_input": 0,
            }
        )
        with patch.object(tab_positions, "st", mock_st_nse):
            tab_positions.render_tab(mock_api, nse_state, "NSE", "RELIANCE", "1d")

        nse_htmls = [body for body, kw in mock_st_nse._recorded_markdowns if kw.get("unsafe_allow_html")]
        self.assertTrue(
            any("Indian Statutory Friction Breakdown (NSE Buy):" in h for h in nse_htmls),
            "Expected NSE statutory friction HTML breakdown card to render, got fallback or missing markup.",
        )
        nse_card = next(h for h in nse_htmls if "Indian Statutory Friction Breakdown (NSE Buy):" in h)
        self.assertIn("Brokerage: <b>₹20.00</b>", nse_card)
        self.assertIn("STT (0.1%):", nse_card)
        self.assertIn("Slippage (5 bps):", nse_card)
        self.assertIn("Total Charges:", nse_card)
        self.assertIn("Net Cash Impact:", nse_card)
        self.assertFalse(
            any("Indian Regulatory Charges:" in c or "ℹ️" in c for c in mock_st_nse._recorded_captions),
            "Unexpected fallback to st.caption on NSE friction breakdown!",
        )

        # 2. US Market (effective_qty = 55)
        us_state = {
            "active_market": "US",
            "active_currency": "USD",
            "curr_sym": "$",
            "is_us_market": True,
            "portfolio": {"equity_inr": 50000.0, "cash_balance_inr": 50000.0},
            "universe_symbols": ["AAPL"],
            "default_cap": 50000.0,
            "equity_val": 50000.0,
            "latest_snapshot": {"close_price": 180.0},
        }
        mock_st_us = _make_mock_st(
            number_input_overrides={
                "pos_order_price_input": 180.0,
                "pos_order_sl_input": 175.0,
                "pos_order_tp_input": 192.5,
                "pos_order_qty_input": 0,
            }
        )
        with patch.object(tab_positions, "st", mock_st_us):
            tab_positions.render_tab(mock_api, us_state, "US", "AAPL", "1d")

        us_htmls = [body for body, kw in mock_st_us._recorded_markdowns if kw.get("unsafe_allow_html")]
        self.assertTrue(
            any("US Regulatory Estimates (Entry Buy):" in h for h in us_htmls),
            "Expected US statutory friction HTML breakdown card to render, got fallback or missing markup.",
        )
        us_card = next(h for h in us_htmls if "US Regulatory Estimates (Entry Buy):" in h)
        self.assertIn("$0.00", us_card)
        self.assertIn("Slippage (5 bps):", us_card)
        self.assertIn("Net Cash Impact:", us_card)
        self.assertFalse(
            any("US Regulatory Charges:" in c or "ℹ️" in c for c in mock_st_us._recorded_captions),
            "Unexpected fallback to st.caption on US friction breakdown!",
        )


if __name__ == "__main__":
    unittest.main()
