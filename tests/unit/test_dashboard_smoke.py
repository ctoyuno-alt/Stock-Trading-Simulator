"""
Tier 1 & Tier 2 Smoke & Architecture Test Suite for Quantum Trader Dashboard.

Validates:
1. DashboardAPIClient transport, JSON decoding, bearer token headers, and HTTP error handling (400, 401, 403, 404, 500, 503, URLError, Timeout).
2. All methods of DashboardAPIClient across Auth, System, Market Data, Indicators, AI, Trading, Backtesting, Auto-Trader, Daemon, and Admin Control Plane.
3. Unauthenticated gate rendering, login/register forms, session state default initialization, and logout session reset.
4. Headless smoke rendering of dashboard tabs and full dashboard/app.py end-to-end execution.
"""

import io
import json
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch
import urllib.error
import urllib.request

from dashboard.api_client import DashboardAPIClient


def create_mock_streamlit(session_state=None):
    """Creates a comprehensive mock for the Streamlit module."""
    def _make_mock_container():
        m = MagicMock()
        m.columns.side_effect = lambda spec, **k: [
            _make_mock_container() for _ in (spec if isinstance(spec, (list, tuple)) else range(int(spec)))
        ]
        m.tabs.side_effect = lambda t: [_make_mock_container() for _ in t]
        m.toggle.side_effect = lambda l, value=False, **k: value
        m.text_input.side_effect = lambda l, value="", **k: value
        m.number_input.side_effect = lambda l, value=0.0, **k: float(value or 0.0)
        m.selectbox.side_effect = lambda l, options=[], index=0, **k: options[index] if options else "OPT"
        m.radio.side_effect = lambda l, options=[], index=0, **k: options[index] if options else "OPT"
        m.checkbox.side_effect = lambda l, value=False, **k: value
        m.button.return_value = False
        m.form_submit_button.return_value = False
        m.form.return_value.__enter__ = lambda s: _make_mock_container()
        m.form.return_value.__exit__ = lambda s, *a: None
        m.container.return_value.__enter__ = lambda s: _make_mock_container()
        m.container.return_value.__exit__ = lambda s, *a: None
        m.spinner.return_value.__enter__ = lambda s: None
        m.spinner.return_value.__exit__ = lambda s, *a: None
        m.expander.return_value.__enter__ = lambda s: _make_mock_container()
        m.expander.return_value.__exit__ = lambda s, *a: None
        return m

    mock_st = _make_mock_container()
    mock_st.sidebar = _make_mock_container()
    mock_st.session_state = session_state if session_state is not None else {}
    mock_st.stop = MagicMock(side_effect=SystemExit("st.stop"))
    mock_st.rerun = MagicMock()
    mock_st.cache_data = lambda *a, **k: (lambda f: f)
    mock_st.column_config = MagicMock()
    return mock_st


class TestDashboardAPIClientTransport(unittest.TestCase):
    """Tests the low-level HTTP transport and error wrapping of DashboardAPIClient."""

    def setUp(self):
        self.client = DashboardAPIClient(base_url="http://testserver:8000")

    @patch("urllib.request.urlopen")
    def test_request_success_json_decoding(self, mock_urlopen):
        """Successful HTTP 200 response decodes JSON body into dict."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok", "value": 42}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = self.client._request("GET", "/test/path")
        self.assertEqual(result, {"status": "ok", "value": 42})

    @patch("urllib.request.urlopen")
    def test_request_attaches_bearer_token(self, mock_urlopen):
        """Sets Authorization: Bearer <token> header when auth_token is configured."""
        self.client.set_auth_token("secret_jwt_xyz")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.client._request("GET", "/test/protected")
        req_arg = mock_urlopen.call_args[0][0]
        self.assertEqual(req_arg.headers.get("Authorization"), "Bearer secret_jwt_xyz")
        self.assertEqual(req_arg.headers.get("Content-type"), "application/json")

    @patch("urllib.request.urlopen")
    def test_request_serializes_post_payload(self, mock_urlopen):
        """Serializes dict payload into valid JSON bytes for POST requests."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"created": true}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        payload = {"symbol": "RELIANCE", "price": 2500.0}
        self.client._request("POST", "/test/order", payload=payload)
        req_arg = mock_urlopen.call_args[0][0]
        self.assertEqual(json.loads(req_arg.data.decode("utf-8")), payload)
        self.assertEqual(req_arg.get_method(), "POST")

    @patch("urllib.request.urlopen")
    def test_request_empty_body_returns_empty_dict(self, mock_urlopen):
        """Empty HTTP 204 or empty response body returns empty dict."""
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.read.return_value = b""
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = self.client._request("DELETE", "/test/resource/1")
        self.assertEqual(result, {})

    @patch("urllib.request.urlopen")
    def test_http_400_bad_request(self, mock_urlopen):
        """HTTP 400 returns error dict with parsed detail."""
        err_body = io.BytesIO(b'{"detail": "Invalid quantity: must be positive"}')
        http_err = urllib.error.HTTPError("http://testserver:8000", 400, "Bad Request", {}, err_body)
        mock_urlopen.side_effect = http_err

        result = self.client._request("POST", "/test/bad")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 400)
        self.assertIn("Invalid quantity", result.get("message", ""))

    @patch("urllib.request.urlopen")
    def test_http_401_unauthorized(self, mock_urlopen):
        """HTTP 401 returns error dict indicating unauthorized credentials."""
        err_body = io.BytesIO(b'{"detail": "Could not validate credentials"}')
        http_err = urllib.error.HTTPError("http://testserver:8000", 401, "Unauthorized", {}, err_body)
        mock_urlopen.side_effect = http_err

        result = self.client._request("GET", "/test/unauthorized")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 401)
        self.assertIn("Could not validate credentials", result.get("message", ""))

    @patch("urllib.request.urlopen")
    def test_http_403_forbidden(self, mock_urlopen):
        """HTTP 403 returns error dict with forbidden role access message."""
        err_body = io.BytesIO(b'{"detail": "Admin privilege required"}')
        http_err = urllib.error.HTTPError("http://testserver:8000", 403, "Forbidden", {}, err_body)
        mock_urlopen.side_effect = http_err

        result = self.client._request("GET", "/test/admin-only")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 403)
        self.assertIn("Admin privilege required", result.get("message", ""))

    @patch("urllib.request.urlopen")
    def test_http_404_not_found(self, mock_urlopen):
        """HTTP 404 returns error dict with resource missing notice."""
        err_body = io.BytesIO(b'{"detail": "Symbol NOTFOUND not tracked in universe"}')
        http_err = urllib.error.HTTPError("http://testserver:8000", 404, "Not Found", {}, err_body)
        mock_urlopen.side_effect = http_err

        result = self.client._request("GET", "/test/missing")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 404)
        self.assertIn("Symbol NOTFOUND not tracked", result.get("message", ""))

    @patch("urllib.request.urlopen")
    def test_http_500_internal_server_error(self, mock_urlopen):
        """HTTP 500 returns error dict with status 500."""
        err_body = io.BytesIO(b'{"detail": "Database connection pool exhausted"}')
        http_err = urllib.error.HTTPError("http://testserver:8000", 500, "Internal Server Error", {}, err_body)
        mock_urlopen.side_effect = http_err

        result = self.client._request("GET", "/test/crash")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 500)
        self.assertIn("Database connection pool", result.get("message", ""))

    @patch("urllib.request.urlopen")
    def test_http_503_service_unavailable(self, mock_urlopen):
        """HTTP 503 returns error dict indicating upstream unavailable."""
        err_body = io.BytesIO(b'{"detail": "Downstream market data gateway offline"}')
        http_err = urllib.error.HTTPError("http://testserver:8000", 503, "Service Unavailable", {}, err_body)
        mock_urlopen.side_effect = http_err

        result = self.client._request("GET", "/test/unavailable")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 503)

    @patch("urllib.request.urlopen")
    def test_url_error_network_failure(self, mock_urlopen):
        """urllib.error.URLError wraps gracefully with status 503 and friendly error message."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused [Errno 111]")

        result = self.client._request("GET", "/test/down")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 503)
        self.assertIn("Backend connection failed", result.get("message", ""))

    @patch("urllib.request.urlopen")
    def test_timeout_and_unexpected_exception(self, mock_urlopen):
        """Unexpected TimeoutError or generic exception wraps with status 500."""
        mock_urlopen.side_effect = TimeoutError("Request timed out after 10 seconds")

        result = self.client._request("GET", "/test/slow")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 500)
        self.assertIn("Unexpected client error", result.get("message", ""))

    @patch("urllib.request.urlopen")
    def test_non_json_error_body(self, mock_urlopen):
        """HTTP error with non-JSON HTML body parses without unhandled JSONDecodeError."""
        err_body = io.BytesIO(b"<html><body>502 Bad Gateway</body></html>")
        http_err = urllib.error.HTTPError("http://testserver:8000", 502, "Bad Gateway", {}, err_body)
        mock_urlopen.side_effect = http_err

        result = self.client._request("GET", "/test/gateway-error")
        self.assertTrue(result.get("error"))
        self.assertEqual(result.get("status_code"), 502)
        self.assertIn("HTTP 502: Bad Gateway", result.get("message", ""))


class TestDashboardAPIClientAuthEndpoints(unittest.TestCase):
    """Tests all Auth & Identity endpoints of DashboardAPIClient."""

    def setUp(self):
        self.client = DashboardAPIClient(base_url="http://testserver:8000")

    @patch.object(DashboardAPIClient, "_request")
    def test_login_success_stores_jwt(self, mock_req):
        """Successful login returns response and sets internal auth token."""
        mock_req.return_value = {"access_token": "token_abc123", "token_type": "bearer"}
        res = self.client.login("trader_bob", "Secr3t!P@ss")
        self.assertEqual(res["access_token"], "token_abc123")
        self.assertEqual(self.client.auth_token, "token_abc123")
        mock_req.assert_called_once_with(
            "POST", "/api/v1/auth/login", {"username": "trader_bob", "password": "Secr3t!P@ss"}
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_login_failure_does_not_set_jwt(self, mock_req):
        """Failed login returns error dict and leaves auth token as None."""
        mock_req.return_value = {"error": True, "status_code": 401, "message": "Invalid password"}
        res = self.client.login("trader_bob", "WrongPass")
        self.assertTrue(res.get("error"))
        self.assertIsNone(self.client.auth_token)

    @patch.object(DashboardAPIClient, "_request")
    def test_register_success_stores_jwt(self, mock_req):
        """Successful registration stores returned access token."""
        mock_req.return_value = {"access_token": "token_new_user", "username": "newbie"}
        res = self.client.register("newbie", "newbie@quantumtrader.io", "StrongP@ss1")
        self.assertEqual(res["access_token"], "token_new_user")
        self.assertEqual(self.client.auth_token, "token_new_user")
        mock_req.assert_called_once_with(
            "POST",
            "/api/v1/auth/register",
            {"username": "newbie", "email": "newbie@quantumtrader.io", "password": "StrongP@ss1"},
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_get_me(self, mock_req):
        """get_me queries /api/v1/auth/me."""
        mock_req.return_value = {"username": "admin", "role": "ADMIN"}
        res = self.client.get_me()
        self.assertEqual(res["role"], "ADMIN")
        mock_req.assert_called_once_with("GET", "/api/v1/auth/me")

    @patch.object(DashboardAPIClient, "_request")
    def test_generate_api_key(self, mock_req):
        """generate_api_key sends POST to /api/v1/auth/api-key."""
        mock_req.return_value = {"api_key": "qt_live_999", "created_at": "2026-11-23"}
        res = self.client.generate_api_key()
        self.assertEqual(res["api_key"], "qt_live_999")
        mock_req.assert_called_once_with("POST", "/api/v1/auth/api-key")

    @patch.object(DashboardAPIClient, "_request")
    def test_forgot_password(self, mock_req):
        """forgot_password sends username/email to /api/v1/auth/forgot-password."""
        mock_req.return_value = {"message": "Recovery token generated"}
        res = self.client.forgot_password("trader_bob")
        self.assertEqual(res["message"], "Recovery token generated")
        mock_req.assert_called_once_with(
            "POST", "/api/v1/auth/forgot-password", {"username_or_email": "trader_bob"}
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_reset_password(self, mock_req):
        """reset_password sends recovery token and new password."""
        mock_req.return_value = {"message": "Password reset successful"}
        res = self.client.reset_password("token_reset_123", "BrandNewP@ssw0rd")
        self.assertEqual(res["message"], "Password reset successful")
        mock_req.assert_called_once_with(
            "POST", "/api/v1/auth/reset-password", {"token": "token_reset_123", "new_password": "BrandNewP@ssw0rd"}
        )


class TestDashboardAPIClientSystemAndMarket(unittest.TestCase):
    """Tests System Health, Market Data, Indicators, and Signals endpoints."""

    def setUp(self):
        self.client = DashboardAPIClient(base_url="http://testserver:8000")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_system_status(self, mock_req):
        """get_system_status queries /api/v1/system/status."""
        mock_req.return_value = {"status": "operational", "kill_switch_active": False}
        res = self.client.get_system_status()
        self.assertEqual(res["status"], "operational")
        mock_req.assert_called_once_with("GET", "/api/v1/system/status")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_health_ready(self, mock_req):
        """get_health_ready queries /health/ready probe."""
        mock_req.return_value = {"status": "ready", "db_latency_ms": 14.2}
        res = self.client.get_health_ready()
        self.assertEqual(res["status"], "ready")
        mock_req.assert_called_once_with("GET", "/health/ready")

    @patch.object(DashboardAPIClient, "_request")
    def test_toggle_kill_switch_activate(self, mock_req):
        """toggle_kill_switch sends activate=True and reason."""
        mock_req.return_value = {"kill_switch_active": True}
        res = self.client.toggle_kill_switch(activate=True, reason="Volatility Breached")
        self.assertTrue(res["kill_switch_active"])
        mock_req.assert_called_once_with(
            "POST", "/api/v1/system/kill-switch", {"activate": True, "reason": "Volatility Breached"}
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_toggle_kill_switch_deactivate(self, mock_req):
        """toggle_kill_switch sends activate=False."""
        mock_req.return_value = {"kill_switch_active": False}
        res = self.client.toggle_kill_switch(activate=False, reason="System Restored")
        self.assertFalse(res["kill_switch_active"])
        mock_req.assert_called_once_with(
            "POST", "/api/v1/system/kill-switch", {"activate": False, "reason": "System Restored"}
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_get_universe_default(self, mock_req):
        """get_universe with default arguments queries base universe path."""
        mock_req.return_value = [{"symbol": "RELIANCE"}]
        res = self.client.get_universe()
        self.assertEqual(len(res), 1)
        mock_req.assert_called_once_with("GET", "/api/v1/market-data/universe")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_universe_with_filters(self, mock_req):
        """get_universe formats query string with market, scan_only, search, and limit."""
        mock_req.return_value = [{"symbol": "AAPL"}]
        res = self.client.get_universe(market="US", scan_only=True, search="AAP", limit=10)
        self.assertEqual(res[0]["symbol"], "AAPL")
        mock_req.assert_called_once_with(
            "GET", "/api/v1/market-data/universe?market=US&scan_only=true&search=AAP&limit=10"
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_get_universe_returns_list_on_error(self, mock_req):
        """get_universe returns empty list when backend returns an error dict."""
        mock_req.return_value = {"error": True, "status_code": 500}
        res = self.client.get_universe()
        self.assertEqual(res, [])

    @patch.object(DashboardAPIClient, "_request")
    def test_get_candles(self, mock_req):
        """get_candles formats symbol, timeframe, and period."""
        mock_req.return_value = {"candles": [{"close": 2500}]}
        res = self.client.get_candles("RELIANCE", timeframe="1h", period="1mo")
        self.assertEqual(res["candles"][0]["close"], 2500)
        mock_req.assert_called_once_with(
            "GET", "/api/v1/market-data/candles/RELIANCE?timeframe=1h&period=1mo"
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_get_indicators(self, mock_req):
        """get_indicators requests technical series overlays."""
        mock_req.return_value = {"rsi": 55.4, "ema_fast": [2500]}
        res = self.client.get_indicators("INFY", timeframe="1d")
        self.assertEqual(res["rsi"], 55.4)
        mock_req.assert_called_once_with(
            "GET", "/api/v1/indicators/INFY?timeframe=1d&include_series=true"
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_get_signal(self, mock_req):
        """get_signal fetches deterministic strategy signal."""
        mock_req.return_value = {"action": "BUY", "technical_score": 82}
        res = self.client.get_signal("TCS", timeframe="1d")
        self.assertEqual(res["action"], "BUY")
        mock_req.assert_called_once_with("GET", "/api/v1/strategies/signal/TCS?timeframe=1d")

    @patch.object(DashboardAPIClient, "_request")
    def test_scan_signals(self, mock_req):
        """scan_signals queries multi-symbol scanner with market filter."""
        mock_req.return_value = {"signals": [{"symbol": "RELIANCE", "action": "BUY"}]}
        res = self.client.scan_signals(timeframe="1d", market="NSE")
        self.assertEqual(len(res["signals"]), 1)
        mock_req.assert_called_once_with("GET", "/api/v1/strategies/signals?timeframe=1d&market=NSE")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_ai_analysis(self, mock_req):
        """get_ai_analysis sends POST request with extended 20s timeout."""
        mock_req.return_value = {"ai_analysis": {"recommended_action_opinion": "BUY"}}
        res = self.client.get_ai_analysis("RELIANCE", timeframe="1d")
        self.assertEqual(res["ai_analysis"]["recommended_action_opinion"], "BUY")
        mock_req.assert_called_once_with(
            "POST", "/api/v1/ai/analyze/RELIANCE", {"timeframe": "1d"}, timeout=20
        )


class TestDashboardAPIClientTradingAndAutoTrader(unittest.TestCase):
    """Tests Trading, Execution, Portfolio, Backtest, and Auto-Trader endpoints."""

    def setUp(self):
        self.client = DashboardAPIClient(base_url="http://testserver:8000")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_portfolio(self, mock_req):
        """get_portfolio queries portfolio endpoint with currency."""
        mock_req.return_value = {"cash_balance": 100000.0, "total_equity": 105000.0}
        res = self.client.get_portfolio(currency="INR")
        self.assertEqual(res["cash_balance"], 100000.0)
        mock_req.assert_called_once_with("GET", "/api/v1/trading/portfolio?currency=INR")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_positions(self, mock_req):
        """get_positions builds query with status_filter and currency."""
        mock_req.return_value = [{"position_id": 1, "symbol": "RELIANCE", "quantity": 10}]
        res = self.client.get_positions(status_filter="OPEN", currency="INR")
        self.assertEqual(len(res), 1)
        mock_req.assert_called_once_with("GET", "/api/v1/trading/positions?status_filter=OPEN&currency=INR")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_orders(self, mock_req):
        """get_orders queries order history with limit and currency."""
        mock_req.return_value = [{"order_id": 101, "symbol": "AAPL"}]
        res = self.client.get_orders(limit=25, currency="USD")
        self.assertEqual(len(res), 1)
        mock_req.assert_called_once_with("GET", "/api/v1/trading/orders?limit=25&currency=USD")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_metrics(self, mock_req):
        """get_metrics queries performance metrics."""
        mock_req.return_value = {"win_rate_pct": 70.0, "sharpe_ratio": 1.85}
        res = self.client.get_metrics(currency="INR")
        self.assertEqual(res["win_rate_pct"], 70.0)
        mock_req.assert_called_once_with("GET", "/api/v1/trading/metrics?currency=INR")

    @patch.object(DashboardAPIClient, "_request")
    def test_place_buy_order(self, mock_req):
        """place_buy_order posts complete virtual order spec."""
        mock_req.return_value = {"order_id": 501, "status": "FILLED"}
        res = self.client.place_buy_order(
            symbol="RELIANCE",
            price=2500.0,
            stop_loss_price=2450.0,
            take_profit_price=2600.0,
            quantity=8,
            enforce_market_hours=False,
            reason="Swing Signal",
        )
        self.assertEqual(res["status"], "FILLED")
        mock_req.assert_called_once_with(
            "POST",
            "/api/v1/trading/orders/buy",
            {
                "symbol": "RELIANCE",
                "price": 2500.0,
                "stop_loss_price": 2450.0,
                "take_profit_price": 2600.0,
                "quantity": 8,
                "enforce_market_hours": False,
                "reason": "Swing Signal",
            },
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_close_position(self, mock_req):
        """close_position posts exit price to position close endpoint."""
        mock_req.return_value = {"position_id": 12, "status": "CLOSED", "realized_pnl": 500.0}
        res = self.client.close_position(position_id=12, exit_price=2600.0, reason="Target Reached")
        self.assertEqual(res["status"], "CLOSED")
        mock_req.assert_called_once_with(
            "POST",
            "/api/v1/trading/positions/12/close",
            {"exit_price": 2600.0, "reason": "Target Reached"},
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_run_backtest(self, mock_req):
        """run_backtest posts simulation parameters with 30s timeout."""
        mock_req.return_value = {"total_return_pct": 14.5, "win_rate_pct": 65.0}
        res = self.client.run_backtest(
            symbol="RELIANCE",
            timeframe="1d",
            period="1y",
            initial_capital_inr=100000.0,
            max_risk_per_trade=0.01,
            slippage_bps=5.0,
        )
        self.assertEqual(res["total_return_pct"], 14.5)
        mock_req.assert_called_once_with(
            "POST",
            "/api/v1/backtest/run",
            {
                "symbol": "RELIANCE",
                "timeframe": "1d",
                "period": "1y",
                "initial_capital_inr": 100000.0,
                "max_risk_per_trade": 0.01,
                "slippage_bps": 5.0,
            },
            timeout=30,
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_auto_trader_endpoints(self, mock_req):
        """Tests auto-trader status, config update, manual tick, and history reset."""
        mock_req.return_value = {"is_running": True}
        self.client.get_auto_trader_status()
        mock_req.assert_called_with("GET", "/api/v1/auto-trader/status")

        cfg = {"min_confluence_score": 75, "require_ai_approval": True}
        self.client.update_auto_trader_config(cfg)
        mock_req.assert_called_with("POST", "/api/v1/auto-trader/config", cfg)

        self.client.run_auto_trader_tick(market="IN", timeframe="1d", enforce_market_hours=False)
        mock_req.assert_called_with(
            "POST",
            "/api/v1/auto-trader/tick?market=IN",
            {"market": "IN", "timeframe": "1d", "enforce_market_hours": False},
            timeout=30,
        )

        self.client.clear_auto_trader_history()
        mock_req.assert_called_with("POST", "/api/v1/auto-trader/clear-history")

        self.client.reset_paper_account(currency="INR", initial_capital=100000.0)
        mock_req.assert_called_with(
            "POST",
            "/api/v1/trading/reset-account",
            {"currency": "INR", "initial_capital": 100000.0},
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_daemon_endpoints(self, mock_req):
        """Tests background daemon status, start, stop, GTT orders, and notifications."""
        mock_req.return_value = {"running": True}
        self.client.get_daemon_status()
        mock_req.assert_called_with("GET", "/api/v1/auto-trader/daemon/status")

        self.client.start_daemon(interval_seconds=45)
        mock_req.assert_called_with("POST", "/api/v1/auto-trader/daemon/start?interval_seconds=45")

        self.client.stop_daemon()
        mock_req.assert_called_with("POST", "/api/v1/auto-trader/daemon/stop")

        mock_req.return_value = [{"id": 1, "symbol": "INFY"}]
        gtt = self.client.get_gtt_orders(symbol="INFY")
        self.assertEqual(len(gtt), 1)
        mock_req.assert_called_with("GET", "/api/v1/auto-trader/gtt-orders?symbol=INFY")

        self.client.test_telegram_notification(bot_token="tok_123", chat_id="chat_456")
        mock_req.assert_called_with(
            "POST",
            "/api/v1/auto-trader/notifications/test",
            {"bot_token": "tok_123", "chat_id": "chat_456"},
        )


class TestDashboardAPIClientAdminEndpoints(unittest.TestCase):
    """Tests all administrative endpoints of DashboardAPIClient."""

    def setUp(self):
        self.client = DashboardAPIClient(base_url="http://testserver:8000")
        self.client.set_auth_token("admin_jwt_token")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_admin_users(self, mock_req):
        """get_admin_users sends paginated query with role and status filters."""
        mock_req.return_value = {"users": [], "total": 0}
        self.client.get_admin_users(page=1, limit=20, role="TRADER", is_active=True, search="bob")
        mock_req.assert_called_once_with(
            "GET", "/api/v1/admin/users?page=1&limit=20&role=trader&is_active=true&search=bob"
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_get_admin_user_details(self, mock_req):
        """get_admin_user_details queries user by ID."""
        mock_req.return_value = {"user_id": 3, "username": "alice"}
        res = self.client.get_admin_user_details(3)
        self.assertEqual(res["user_id"], 3)
        mock_req.assert_called_once_with("GET", "/api/v1/admin/users/3")

    @patch.object(DashboardAPIClient, "_request")
    def test_update_user_role(self, mock_req):
        """update_user_role patches user role."""
        mock_req.return_value = {"success": True}
        self.client.update_user_role(3, "ADMIN")
        mock_req.assert_called_once_with("PATCH", "/api/v1/admin/users/3/role", {"role": "ADMIN"})

    @patch.object(DashboardAPIClient, "_request")
    def test_toggle_user_status(self, mock_req):
        """toggle_user_status patches user active flag with audit reason."""
        mock_req.return_value = {"success": True}
        self.client.toggle_user_status(3, is_active=False, reason="Compliance Flag")
        mock_req.assert_called_once_with(
            "PATCH", "/api/v1/admin/users/3/status", {"is_active": False, "reason": "Compliance Flag"}
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_fund_account(self, mock_req):
        """fund_account posts capital injection amount and reason."""
        mock_req.return_value = {"funded": True}
        self.client.fund_account(10, amount=50000.0, reason="Seed Capital")
        mock_req.assert_called_once_with(
            "POST", "/api/v1/admin/accounts/10/fund", {"amount": 50000.0, "reason": "Seed Capital"}
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_reset_account_admin(self, mock_req):
        """reset_account_admin posts wipe request with initial capital."""
        mock_req.return_value = {"reset": True}
        self.client.reset_account_admin(10, initial_capital=100000.0, reason="Quarterly Wipe")
        mock_req.assert_called_once_with(
            "POST",
            "/api/v1/admin/accounts/10/reset",
            {"initial_capital": 100000.0, "reason": "Quarterly Wipe"},
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_delete_account_admin(self, mock_req):
        """delete_account_admin sends DELETE request."""
        mock_req.return_value = {"archived": True}
        self.client.delete_account_admin(10)
        mock_req.assert_called_once_with("DELETE", "/api/v1/admin/accounts/10")

    @patch.object(DashboardAPIClient, "_request")
    def test_rotate_and_revoke_api_key(self, mock_req):
        """rotate_user_api_key and revoke_user_api_key send corresponding POST requests."""
        mock_req.return_value = {"key": "qt_new"}
        self.client.rotate_user_api_key(5)
        mock_req.assert_called_with("POST", "/api/v1/admin/users/5/api-key/rotate")

        self.client.revoke_user_api_key(5)
        mock_req.assert_called_with("POST", "/api/v1/admin/users/5/api-key/revoke")

    @patch.object(DashboardAPIClient, "_request")
    def test_admin_reset_user_password(self, mock_req):
        """admin_reset_user_password sends PUT request with new password and reason."""
        mock_req.return_value = {"updated": True}
        self.client.admin_reset_user_password(5, "NewSecurePassword#1", reason="User Request")
        mock_req.assert_called_once_with(
            "PUT",
            "/api/v1/admin/users/5/password",
            {"new_password": "NewSecurePassword#1", "reason": "User Request"},
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_get_admin_audit_logs(self, mock_req):
        """get_admin_audit_logs formats pagination and action filters."""
        mock_req.return_value = {"logs": [], "total": 0}
        self.client.get_admin_audit_logs(page=1, limit=50, action="ROLE_UPDATE", target_user_id=7)
        mock_req.assert_called_once_with(
            "GET", "/api/v1/admin/audit-logs?page=1&limit=50&action=ROLE_UPDATE&target_user_id=7"
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_get_admin_summary(self, mock_req):
        """get_admin_summary queries administrative summary metrics."""
        mock_req.return_value = {"total_users": 5, "active_users": 5}
        res = self.client.get_admin_summary()
        self.assertEqual(res["total_users"], 5)
        mock_req.assert_called_once_with("GET", "/api/v1/admin/summary")


class TestDashboardAuthGateAndSessionState(unittest.TestCase):
    """Tests the unauthenticated gate, forms, and session state behavior."""

    def test_unauthenticated_gate_mounts_auth_forms_and_stops(self):
        """When auth_token is absent, auth gate renders login form and invokes st.stop()."""
        mock_st = create_mock_streamlit(session_state={})
        mock_tv = MagicMock()

        with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_tv}):
            if "dashboard.app" in sys.modules:
                del sys.modules["dashboard.app"]

            with self.assertRaises(SystemExit):
                import dashboard.app

            # Verify st.stop() was called to prevent unauthenticated rendering of trading tabs
            self.assertTrue(mock_st.stop.called)

    def test_authenticated_admin_renders_admin_tab(self):
        """When authenticated with ADMIN role, the Admin User & Account tab is mounted."""
        session = {
            "auth_token": "valid_admin_jwt",
            "user_profile": {"username": "superuser", "role": "admin"},
            "selected_symbol": "RELIANCE",
            "timeframe": "1d",
            "active_market": "NSE",
            "active_currency": "INR",
        }
        mock_st = create_mock_streamlit(session_state=session)
        mock_tv = MagicMock()

        # Provide mock client methods
        from dashboard.api_client import api_client
        with patch.object(api_client, "get_system_status", return_value={"safety_guardrails": {"kill_switch_active": False}, "status": "operational"}), \
             patch.object(api_client, "get_health_ready", return_value={"status": "ready", "db_latency_ms": 10.0}), \
             patch.object(api_client, "get_portfolio", return_value={"cash_balance": 100000.0, "total_equity": 100000.0, "unrealized_pnl": 0.0, "realized_pnl": 0.0, "initial_capital_inr": 100000.0}), \
             patch.object(api_client, "get_universe", return_value=[{"symbol": "RELIANCE", "name": "Reliance", "market": "NSE"}]), \
             patch.object(api_client, "get_candles", return_value={"candles": [{"timestamp": "2026-11-23T10:00:00Z", "open": 2500, "high": 2520, "low": 2490, "close": 2510, "volume": 1000}]}), \
             patch.object(api_client, "get_indicators", return_value={"rsi": 55.0, "macd_line": [1.0], "macd_signal": [0.8], "macd_hist": [0.2], "timestamps": ["2026-11-23T10:00:00Z"], "ema_fast": [2505], "ema_slow": [2500], "vwap": [2508]}), \
             patch.object(api_client, "get_signal", return_value={"action": "BUY", "strength": "STRONG", "technical_score": 85, "primary_trigger": "Trend", "suggested_stop_loss": 2450, "suggested_take_profit": 2600, "stop_loss_pct": 2.0, "target_profit_pct": 4.0, "confirming_factors": [], "conflicting_factors": []}), \
             patch.object(api_client, "get_positions", return_value=[]), \
             patch.object(api_client, "get_orders", return_value=[]), \
             patch.object(api_client, "get_metrics", return_value={"sharpe_ratio": 1.5, "win_rate_pct": 65.0, "max_drawdown_pct": 5.0, "profit_factor": 1.8}), \
             patch.object(api_client, "get_auto_trader_status", return_value={"is_running": False, "active_positions": 0, "total_trades": 0, "config": {"enabled": False, "min_confluence_score": 70, "require_ai_approval": True}}), \
             patch.object(api_client, "get_daemon_status", return_value={"running": False}), \
             patch.object(api_client, "get_gtt_orders", return_value=[]), \
             patch.object(api_client, "get_admin_users", return_value={"users": [], "total": 0}), \
             patch.object(api_client, "get_admin_summary", return_value={"total_users": 1, "active_users": 1, "active_accounts": 1, "total_capital_inr": 100000.0, "total_capital_usd": 10000.0, "audit_events_count": 0}), \
             patch.object(api_client, "get_admin_audit_logs", return_value={"logs": [], "total": 0}), \
             patch.object(api_client, "get_ai_analysis", return_value={"ai_analysis": {"recommended_action_opinion": "FAVORS_PATIENCE", "ai_confidence_score": 80.0}}):

            with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_tv}):
                if "dashboard.app" in sys.modules:
                    del sys.modules["dashboard.app"]
                import dashboard.app

                # Verify st.tabs was called with Admin tab included in tab titles list
                tabs_call_args = mock_st.tabs.call_args[0][0]
                self.assertTrue(any("Admin" in title for title in tabs_call_args))

    def test_authenticated_trader_hides_admin_tab(self):
        """When authenticated with TRADER role, the Admin tab is hidden from tab list."""
        session = {
            "auth_token": "valid_trader_jwt",
            "user_profile": {"username": "trader_jane", "role": "trader"},
            "selected_symbol": "RELIANCE",
            "timeframe": "1d",
            "active_market": "NSE",
            "active_currency": "INR",
        }
        mock_st = create_mock_streamlit(session_state=session)
        mock_tv = MagicMock()

        from dashboard.api_client import api_client
        with patch.object(api_client, "get_system_status", return_value={"safety_guardrails": {"kill_switch_active": False}, "status": "operational"}), \
             patch.object(api_client, "get_health_ready", return_value={"status": "ready", "db_latency_ms": 10.0}), \
             patch.object(api_client, "get_portfolio", return_value={"cash_balance": 100000.0, "total_equity": 100000.0, "unrealized_pnl": 0.0, "realized_pnl": 0.0, "initial_capital_inr": 100000.0}), \
             patch.object(api_client, "get_universe", return_value=[{"symbol": "RELIANCE", "name": "Reliance", "market": "NSE"}]), \
             patch.object(api_client, "get_candles", return_value={"candles": [{"timestamp": "2026-11-23T10:00:00Z", "open": 2500, "high": 2520, "low": 2490, "close": 2510, "volume": 1000}]}), \
             patch.object(api_client, "get_indicators", return_value={"rsi": 55.0, "macd_line": [1.0], "macd_signal": [0.8], "macd_hist": [0.2], "timestamps": ["2026-11-23T10:00:00Z"], "ema_fast": [2505], "ema_slow": [2500], "vwap": [2508]}), \
             patch.object(api_client, "get_signal", return_value={"action": "BUY", "strength": "STRONG", "technical_score": 85, "primary_trigger": "Trend", "suggested_stop_loss": 2450, "suggested_take_profit": 2600, "stop_loss_pct": 2.0, "target_profit_pct": 4.0, "confirming_factors": [], "conflicting_factors": []}), \
             patch.object(api_client, "get_positions", return_value=[]), \
             patch.object(api_client, "get_orders", return_value=[]), \
             patch.object(api_client, "get_metrics", return_value={"sharpe_ratio": 1.5, "win_rate_pct": 65.0, "max_drawdown_pct": 5.0, "profit_factor": 1.8}), \
             patch.object(api_client, "get_auto_trader_status", return_value={"is_running": False, "active_positions": 0, "total_trades": 0, "config": {"enabled": False, "min_confluence_score": 70, "require_ai_approval": True}}), \
             patch.object(api_client, "get_daemon_status", return_value={"running": False}), \
             patch.object(api_client, "get_gtt_orders", return_value=[]), \
             patch.object(api_client, "get_ai_analysis", return_value={"ai_analysis": {"recommended_action_opinion": "FAVORS_PATIENCE", "ai_confidence_score": 80.0}}):

            with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_tv}):
                if "dashboard.app" in sys.modules:
                    del sys.modules["dashboard.app"]
                import dashboard.app

                tabs_call_args = mock_st.tabs.call_args[0][0]
                self.assertFalse(any("Admin" in title for title in tabs_call_args))


class TestDashboardHeadlessFullAppExecution(unittest.TestCase):
    """End-to-End headless execution tests across different market contexts."""

    def _setup_api_client_mocks(self, api_client, is_us=False):
        sym = "AAPL" if is_us else "RELIANCE"
        mkt = "US" if is_us else "NSE"
        curr = "USD" if is_us else "INR"
        price = 180.0 if is_us else 2500.0

        api_client.get_system_status = MagicMock(return_value={"safety_guardrails": {"kill_switch_active": False}, "status": "operational"})
        api_client.get_health_ready = MagicMock(return_value={"status": "ready", "db_latency_ms": 12.0})
        api_client.get_portfolio = MagicMock(return_value={"cash_balance": 50000.0, "total_equity": 50000.0, "unrealized_pnl": 0.0, "realized_pnl": 0.0, "initial_capital_inr": 50000.0})
        api_client.get_universe = MagicMock(return_value=[{"symbol": sym, "name": sym, "market": mkt}])
        api_client.get_candles = MagicMock(return_value={"candles": [{"timestamp": "2026-11-23T10:00:00Z", "open": price, "high": price + 5, "low": price - 5, "close": price + 2, "volume": 5000}]})
        api_client.get_indicators = MagicMock(return_value={"rsi": 55.0, "macd_line": [1.0], "macd_signal": [0.8], "macd_hist": [0.2], "timestamps": ["2026-11-23T10:00:00Z"], "ema_fast": [price], "ema_slow": [price - 2], "vwap": [price + 1]})
        api_client.get_signal = MagicMock(return_value={"action": "BUY", "strength": "STRONG", "technical_score": 85, "primary_trigger": "Trend", "suggested_stop_loss": price - 10, "suggested_take_profit": price + 20, "stop_loss_pct": 2.0, "target_profit_pct": 4.0, "confirming_factors": [], "conflicting_factors": []})
        api_client.get_positions = MagicMock(return_value=[])
        api_client.get_orders = MagicMock(return_value=[])
        api_client.get_metrics = MagicMock(return_value={"sharpe_ratio": 1.5, "win_rate_pct": 65.0, "max_drawdown_pct": 5.0, "profit_factor": 1.8})
        api_client.get_auto_trader_status = MagicMock(return_value={"is_running": False, "active_positions": 0, "total_trades": 0, "config": {"enabled": False, "min_confluence_score": 70, "require_ai_approval": True}})
        api_client.get_daemon_status = MagicMock(return_value={"running": False})
        api_client.get_gtt_orders = MagicMock(return_value=[])
        api_client.get_admin_users = MagicMock(return_value={"users": [], "total": 0})
        api_client.get_admin_summary = MagicMock(return_value={"total_users": 1, "active_users": 1, "active_accounts": 1, "total_capital_inr": 100000.0, "total_capital_usd": 10000.0, "audit_events_count": 0})
        api_client.get_admin_audit_logs = MagicMock(return_value={"logs": [], "total": 0})
        api_client.get_ai_analysis = MagicMock(return_value={"ai_analysis": {"recommended_action_opinion": "FAVORS_PATIENCE", "ai_confidence_score": 80.0}})

    def test_headless_app_execution_nse_market(self):
        """Executes full dashboard/app.py in headless mode for Indian Equities."""
        session = {
            "auth_token": "valid_admin_jwt",
            "user_profile": {"username": "admin", "role": "admin"},
            "selected_symbol": "RELIANCE",
            "timeframe": "1d",
            "active_market": "NSE",
            "active_currency": "INR",
        }
        mock_st = create_mock_streamlit(session_state=session)
        mock_tv = MagicMock()

        from dashboard.api_client import api_client
        self._setup_api_client_mocks(api_client, is_us=False)

        with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_tv}):
            if "dashboard.app" in sys.modules:
                del sys.modules["dashboard.app"]
            import dashboard.app
            self.assertIn("dashboard.app", sys.modules)

    def test_headless_app_execution_none_user_role(self):
        """Executes full dashboard/app.py when user_profile has None role and username."""
        session = {
            "auth_token": "valid_token",
            "user_profile": {"username": None, "role": None},
            "selected_symbol": "RELIANCE",
            "timeframe": "1d",
            "active_market": "NSE",
            "active_currency": "INR",
        }
        mock_st = create_mock_streamlit(session_state=session)
        mock_tv = MagicMock()

        from dashboard.api_client import api_client
        self._setup_api_client_mocks(api_client, is_us=False)

        with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_tv}):
            if "dashboard.app" in sys.modules:
                del sys.modules["dashboard.app"]
            import dashboard.app
            self.assertIn("dashboard.app", sys.modules)

    def test_headless_app_execution_us_market(self):
        """Executes full dashboard/app.py in headless mode for US Mega-Caps."""
        session = {
            "auth_token": "valid_admin_jwt",
            "user_profile": {"username": "admin", "role": "admin"},
            "selected_symbol": "AAPL",
            "timeframe": "1d",
            "active_market": "US",
            "active_currency": "USD",
        }
        mock_st = create_mock_streamlit(session_state=session)
        mock_tv = MagicMock()

        from dashboard.api_client import api_client
        self._setup_api_client_mocks(api_client, is_us=True)

        with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_tv}):
            if "dashboard.app" in sys.modules:
                del sys.modules["dashboard.app"]
            import dashboard.app
            self.assertIn("dashboard.app", sys.modules)


class TestModularArchitectureAndContracts(unittest.TestCase):
    """Validates Milestone 1 modularization, uniform tab signatures, and slim orchestrator."""

    def setUp(self):
        self.mock_st = create_mock_streamlit()
        self.mock_tv = MagicMock()

    def test_module_imports(self):
        """Verifies dashboard.styles, dashboard.auth, components, and all 8 tabs import cleanly."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            import dashboard.styles as styles
            import dashboard.auth as auth
            import dashboard.components.ticker as ticker
            import dashboard.components.header as header
            import dashboard.components.charts as charts
            import dashboard.components.tradingview as tv
            from dashboard.tabs import (
                tab_market,
                tab_ai,
                tab_autotrader,
                tab_positions,
                tab_ledger,
                tab_backtest,
                tab_health,
                tab_admin,
            )
            self.assertTrue(hasattr(styles, "inject_custom_css"))
            self.assertTrue(hasattr(auth, "render_auth_screen"))
            self.assertTrue(hasattr(ticker, "render_ticker_tape"))
            self.assertTrue(hasattr(header, "render_top_header"))
            self.assertTrue(hasattr(charts, "create_candlestick_with_indicators"))
            self.assertTrue(hasattr(tv, "render_tradingview_chart"))

    def test_render_tab_signatures(self):
        """Verifies that every one of the 8 tabs adheres to the uniform interface contract."""
        import inspect
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import (
                tab_market,
                tab_ai,
                tab_autotrader,
                tab_positions,
                tab_ledger,
                tab_backtest,
                tab_health,
                tab_admin,
            )
            tabs = [
                tab_market,
                tab_ai,
                tab_autotrader,
                tab_positions,
                tab_ledger,
                tab_backtest,
                tab_health,
                tab_admin,
            ]
            expected_params = ["api_client", "state", "market", "symbol", "timeframe"]
            for tab_module in tabs:
                self.assertTrue(hasattr(tab_module, "render_tab"), f"{tab_module.__name__} missing render_tab")
                sig = inspect.signature(tab_module.render_tab)
                param_names = list(sig.parameters.keys())
                self.assertEqual(
                    param_names,
                    expected_params,
                    f"{tab_module.__name__}.render_tab signature mismatch: {param_names} != {expected_params}",
                )

    def test_dashboard_app_line_count(self):
        """Verifies dashboard/app.py is refactored into an orchestrator with strictly < 300 lines."""
        from pathlib import Path
        app_path = Path(__file__).resolve().parent.parent.parent / "dashboard" / "app.py"
        with open(app_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        line_count = len(lines)
        self.assertLess(line_count, 300, f"dashboard/app.py has {line_count} lines, which exceeds the 300-line limit!")


class TestDesignSystemAndComponents(unittest.TestCase):
    """Validates Bloomberg/TradingView design tokens, CSS injection, and components."""

    def setUp(self):
        self.mock_st = create_mock_streamlit()
        self.mock_tv = MagicMock()

    def test_styles_tokens_and_css_injection(self):
        """Verifies institutional design tokens exist and inject_custom_css calls st.markdown."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.styles import (
                COLOR_OBSIDIAN,
                COLOR_SLATE_SURFACE,
                COLOR_AMBER,
                COLOR_GREEN,
                COLOR_RED,
                COLOR_CYAN,
                COLOR_PURPLE,
                INSTITUTIONAL_CSS,
                inject_custom_css,
            )
            self.assertEqual(COLOR_OBSIDIAN, "#080B11")
            self.assertEqual(COLOR_AMBER, "#FF9900")
            self.assertEqual(COLOR_GREEN, "#00E676")
            self.assertEqual(COLOR_RED, "#FF3366")
            self.assertIn("#080B11", INSTITUTIONAL_CSS)
            self.assertIn("#FF9900", INSTITUTIONAL_CSS)

            inject_custom_css()
            self.assertTrue(self.mock_st.markdown.called)

    def test_metric_card_html(self):
        """Verifies metric_card HTML generator output with delta and subtext."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.styles import metric_card
            html = metric_card("TOTAL EQUITY", "₹125,000.00", delta="+2.50%", delta_positive=True, subtext="10 Trades")
            self.assertIn("TOTAL EQUITY", html)
            self.assertIn("₹125,000.00", html)
            self.assertIn("+2.50%", html)
            self.assertIn("#00E676", html)
            self.assertIn("10 Trades", html)

            html_neg = metric_card("DRAWDOWN", "₹5,000.00", delta="-4.00%", delta_positive=False)
            self.assertIn("#FF3366", html_neg)

    def test_badge_and_pnl_helpers(self):
        """Verifies badge, pnl_pill, and order_badge HTML helpers."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.styles import badge, pnl_pill, order_badge
            b_bull = badge("BUY", variant="bullish")
            self.assertIn("pill-bullish", b_bull)
            b_bear = badge("SELL", variant="bearish")
            self.assertIn("pill-bearish", b_bear)

            pill_pos = pnl_pill(1250.50, pct=1.25, currency="₹")
            self.assertIn("pill-bullish", pill_pos)
            self.assertIn("+₹1,250.50", pill_pos)

            pill_neg = pnl_pill(-450.00, pct=-0.45, currency="$")
            self.assertIn("pill-bearish", pill_neg)
            self.assertIn("$-450.00", pill_neg)

            ob_buy = order_badge("BUY")
            self.assertIn("pill-bullish", ob_buy)
            ob_sell = order_badge("SELL")
            self.assertIn("pill-bearish", ob_sell)

    def test_ticker_quotes_fallback(self):
        """Verifies fetch_ticker_quotes fallback returns 9 key instruments when client is None."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.components.ticker import fetch_ticker_quotes, DEFAULT_SNAPSHOTS
            quotes = fetch_ticker_quotes(None)
            self.assertEqual(len(quotes), 9)
            symbols = [q["symbol"] for q in quotes]
            for expected in ["NIFTY 50", "SENSEX", "RELIANCE", "TCS", "HDFCBANK", "AAPL", "NVDA", "MSFT", "TSLA"]:
                self.assertIn(expected, symbols)

    def test_charts_defensive_none_inputs(self):
        """Verifies charts module handles None and empty inputs defensively without throwing."""
        from dashboard.components.charts import (
            create_candlestick_with_indicators,
            create_rsi_chart,
            create_equity_curve_chart,
        )
        self.assertIsNone(create_candlestick_with_indicators(None))
        self.assertIsNone(create_candlestick_with_indicators({}))
        self.assertIsNone(create_candlestick_with_indicators({"candles": []}))
        self.assertIsNone(create_rsi_chart([], []))
        self.assertIsNone(create_equity_curve_chart([], []))


class TestTabMountingAndResilience(unittest.TestCase):
    """Directly invokes render_tab on each of the 8 tabs with mocked client and state."""

    def setUp(self):
        self.mock_st = create_mock_streamlit()
        self.mock_tv = MagicMock()
        self.client = MagicMock(spec=DashboardAPIClient)
        # Baseline successful return values
        self.client.get_candles.return_value = {
            "candles": [
                {"timestamp": "2026-11-23T10:00:00Z", "open": 2500, "high": 2520, "low": 2490, "close": 2510, "volume": 1000}
            ]
        }
        self.client.get_indicators.return_value = {
            "latest_snapshot": {"close_price": 2510, "rsi_14": 55.0, "ema_fast_20": 2505, "ema_slow_50": 2500},
            "rsi": [55.0],
            "timestamps": ["2026-11-23T10:00:00Z"],
        }
        self.client.get_signal.return_value = {
            "action": "BUY",
            "strength": "STRONG",
            "technical_score": 85,
            "primary_trigger": "Trend",
            "entry_price": 2510,
            "suggested_stop_loss": 2450,
            "suggested_take_profit": 2600,
        }
        self.client.get_ai_analysis.return_value = {
            "ai_analysis": {"recommended_action_opinion": "BUY", "ai_confidence_score": 85.0}
        }
        self.client.get_auto_trader_status.return_value = {"config": {"enabled": False}, "recent_decisions": []}
        self.client.get_daemon_status.return_value = {"is_running": False}
        self.client.get_gtt_orders.return_value = []
        self.client.get_positions.return_value = []
        self.client.get_metrics.return_value = {"win_rate_pct": 60.0, "profit_factor": 1.5}
        self.client.get_orders.return_value = []
        self.client.run_backtest.return_value = {
            "symbol": "RELIANCE",
            "total_bars": 100,
            "strategy_name": "MultiFactor",
            "total_return_pct": 12.5,
            "total_net_profit_inr": 12500.0,
            "metrics": {},
            "equity_curve": [{"timestamp": "2026-11-23T10:00:00Z", "equity": 100000.0}],
            "trades": [],
        }
        self.client.get_health_ready.return_value = {"database": {"connected": True, "latency_ms": 10}}
        self.client.get_admin_summary.return_value = {"total_users": 5, "active_accounts": 5}
        self.client.get_admin_users.return_value = {"users": []}
        self.client.get_admin_audit_logs.return_value = {"logs": []}

        self.state = {
            "current_user": {"username": "admin", "role": "admin", "id": 1},
            "user_role": "admin",
            "is_admin": True,
            "is_us_market": False,
            "active_market": "NSE",
            "active_currency": "INR",
            "curr_sym": "₹",
            "is_open": True,
            "portfolio": {"cash_balance_inr": 100000.0, "equity_inr": 100000.0, "total_pnl_inr": 0.0},
            "universe_symbols": ["RELIANCE", "TCS"],
            "universe": [{"symbol": "RELIANCE", "company_name": "Reliance", "exchange": "NSE"}],
            "default_cap": 100000.0,
            "equity_val": 100000.0,
        }

    def test_all_tabs_render_cleanly(self):
        """Directly calls render_tab on all 8 tabs with valid state."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import (
                tab_market,
                tab_ai,
                tab_autotrader,
                tab_positions,
                tab_ledger,
                tab_backtest,
                tab_health,
                tab_admin,
            )
            for mod in [tab_market, tab_ai, tab_autotrader, tab_positions, tab_ledger, tab_backtest, tab_health, tab_admin]:
                mod.render_tab(self.client, self.state, "NSE", "RELIANCE", "1d")

    def test_tabs_error_payload_resilience(self):
        """Passes error responses from client to tabs to verify graceful fallback without unhandled exceptions."""
        error_client = MagicMock(spec=DashboardAPIClient)
        error_client.get_candles.return_value = {"error": True, "message": "Failed"}
        error_client.get_indicators.return_value = {"error": True, "message": "Failed"}
        error_client.get_signal.return_value = {"error": True, "message": "Failed"}
        error_client.get_ai_analysis.return_value = {"error": True, "message": "Failed"}
        error_client.get_auto_trader_status.return_value = {"error": True, "message": "Failed"}
        error_client.get_daemon_status.return_value = {"error": True, "message": "Failed"}
        error_client.get_gtt_orders.return_value = []
        error_client.get_positions.return_value = []
        error_client.get_metrics.return_value = {"error": True, "message": "Failed"}
        error_client.get_orders.return_value = []
        error_client.run_backtest.return_value = {"error": True, "message": "Failed"}
        error_client.get_health_ready.return_value = {"error": True, "message": "Failed"}
        error_client.get_admin_summary.return_value = {"error": True, "message": "Failed"}
        error_client.get_admin_users.return_value = {"error": True, "message": "Failed"}
        error_client.get_admin_audit_logs.return_value = {"error": True, "message": "Failed"}

        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import (
                tab_market,
                tab_ai,
                tab_autotrader,
                tab_positions,
                tab_ledger,
                tab_backtest,
                tab_health,
                tab_admin,
            )
            for mod in [tab_market, tab_ai, tab_autotrader, tab_positions, tab_ledger, tab_backtest, tab_health, tab_admin]:
                mod.render_tab(error_client, self.state, "NSE", "RELIANCE", "1d")

    def test_tab_autotrader_none_current_user(self):
        """Verifies Tab 3 renders cleanly when state['current_user'] is explicitly None."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import tab_autotrader
            adversarial_state = dict(self.state)
            adversarial_state["current_user"] = None
            # Must not raise AttributeError
            tab_autotrader.render_tab(self.client, adversarial_state, "NSE", "RELIANCE", "1d")

    def test_tab_ledger_none_active_currency(self):
        """Verifies Tab 5 renders cleanly when state['active_currency'] is explicitly None."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import tab_ledger
            adversarial_state = dict(self.state)
            adversarial_state["active_currency"] = None
            # Must not raise AttributeError: 'NoneType' object has no attribute 'lower'
            tab_ledger.render_tab(self.client, adversarial_state, "NSE", "RELIANCE", "1d")

    def test_tab_admin_none_role_in_current_user(self):
        """Verifies Tab 8 safely rejects access when current_user has {'role': None}."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import tab_admin
            adversarial_state = dict(self.state)
            adversarial_state["is_admin"] = False
            adversarial_state["user_role"] = None
            adversarial_state["current_user"] = {"username": "adversary", "role": None}
            # Must not raise AttributeError: 'NoneType' object has no attribute 'lower'
            tab_admin.render_tab(self.client, adversarial_state, "NSE", "RELIANCE", "1d")

    def test_tab_health_none_user_role_and_none_current_user_role(self):
        """Verifies Tab 7 handles None user_role, None current_user, and None role without AttributeError."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import tab_health
            for adv_user in [{"username": "alice", "role": None}, None, {"username": None, "role": None}, {}]:
                adv_state = dict(self.state)
                adv_state["user_role"] = None
                adv_state["current_user"] = adv_user
                # Must not raise AttributeError: 'NoneType' object has no attribute 'upper'
                tab_health.render_tab(self.client, adv_state, "NSE", "RELIANCE", "1d")

    def test_header_adversarial_none_states(self):
        """Verifies header.render_top_header handles None current_user, None user_role, and None username."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.components import header
            for adv_state in [
                {"current_user": None, "user_role": None},
                {"current_user": {"username": None, "role": None}, "user_role": None},
                {"current_user": "not_a_dict", "user_role": None},
                {"current_user": {}, "user_role": None},
            ]:
                # Must not raise AttributeError: 'NoneType' object has no attribute 'get' or 'upper'
                header.render_top_header(adv_state, api_client=self.client)

    def test_tab_market_none_timeframe(self):
        """Verifies Tab 1 handles timeframe=None and empty string timeframe without crashing."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import tab_market
            for tf in [None, ""]:
                # Must not raise AttributeError: 'NoneType' object has no attribute 'upper'
                tab_market.render_tab(self.client, self.state, "NSE", "RELIANCE", tf)

    def test_tab_market_adversarial_none_symbol(self):
        """Verifies Tab 1 handles symbol=None and empty string symbol without crashing."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import tab_market
            for sym in [None, "", "   "]:
                tab_market.render_tab(self.client, self.state, "NSE", sym, "1d")

    def test_tab_ai_adversarial_none_timeframe_and_symbol(self):
        """Verifies Tab 2 handles timeframe=None, symbol=None, and empty inputs without crashing."""
        with patch.dict(sys.modules, {"streamlit": self.mock_st, "streamlit.components.v1": self.mock_tv}):
            from dashboard.tabs import tab_ai
            for tf in [None, "", "1d"]:
                for sym in [None, "RELIANCE"]:
                    tab_ai.render_tab(self.client, self.state, "NSE", sym, tf)


if __name__ == "__main__":
    unittest.main()
