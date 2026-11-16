"""
FastAPI Backend API Client for Streamlit Dashboard.

Provides robust communication with the quantitative backend service,
including automatic URL resolution (Docker internal network vs localhost),
timeout handling, error wrapping, and offline resilience.
"""

import json
import os
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

# Resolve backend URL from environment
BACKEND_BASE_URL = os.environ.get("BACKEND_INTERNAL_URL") or os.environ.get("BACKEND_URL") or "http://localhost:8000"


class DashboardAPIClient:
    """Client for querying the FastAPI quantitative paper-trading service."""

    def __init__(self, base_url: str = BACKEND_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = 10  # 10s default timeout

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        req_timeout = timeout or self.timeout
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        data_bytes = None
        if payload is not None:
            data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                status_code = resp.status
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            err_msg = f"HTTP {exc.code}: {exc.reason}"
            try:
                err_detail = json.loads(body).get("detail", body)
                err_msg = f"{err_msg} - {err_detail}"
            except Exception:
                pass
            return {"error": True, "status_code": exc.code, "message": err_msg}
        except urllib.error.URLError as exc:
            return {
                "error": True,
                "status_code": 503,
                "message": f"Backend connection failed at {self.base_url}: {str(exc.reason)}",
            }
        except Exception as exc:
            return {"error": True, "status_code": 500, "message": f"Unexpected client error: {str(exc)}"}

    # --- System & Health ---
    def get_system_status(self) -> Dict[str, Any]:
        return self._request("GET", "/api/v1/system/status")

    def get_health_ready(self) -> Dict[str, Any]:
        return self._request("GET", "/health/ready")

    def toggle_kill_switch(self, activate: bool, reason: str = "Dashboard User Toggle") -> Dict[str, Any]:
        return self._request("POST", "/api/v1/system/kill-switch", {"activate": activate, "reason": reason})

    # --- Market Data & Universe ---
    def get_universe(self, market: Optional[str] = None) -> List[Dict[str, Any]]:
        path = f"/api/v1/market-data/universe?market={market}" if market else "/api/v1/market-data/universe"
        resp = self._request("GET", path)
        return resp if isinstance(resp, list) else []

    def get_candles(self, symbol: str, timeframe: str = "1d", period: str = "6mo") -> Dict[str, Any]:
        return self._request("GET", f"/api/v1/market-data/candles/{symbol}?timeframe={timeframe}&period={period}")

    # --- Indicators ---
    def get_indicators(self, symbol: str, timeframe: str = "1d") -> Dict[str, Any]:
        return self._request("GET", f"/api/v1/indicators/{symbol}?timeframe={timeframe}&include_series=true")

    # --- Strategy Signals ---
    def get_signal(self, symbol: str, timeframe: str = "1d") -> Dict[str, Any]:
        return self._request("GET", f"/api/v1/strategies/signal/{symbol}?timeframe={timeframe}")

    def scan_signals(self, timeframe: str = "1d", market: Optional[str] = None) -> Dict[str, Any]:
        path = f"/api/v1/strategies/signals?timeframe={timeframe}&market={market}" if market else f"/api/v1/strategies/signals?timeframe={timeframe}"
        return self._request("GET", path)

    # --- AI Analysis ---
    def get_ai_analysis(self, symbol: str, timeframe: str = "1d") -> Dict[str, Any]:
        return self._request("POST", f"/api/v1/ai/analyze/{symbol}", {"timeframe": timeframe}, timeout=20)

    # --- Trading & Portfolio ---
    def get_portfolio(self, currency: str = "INR") -> Dict[str, Any]:
        return self._request("GET", f"/api/v1/trading/portfolio?currency={currency}")

    def get_positions(self, status_filter: Optional[str] = None, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        params = []
        if status_filter:
            params.append(f"status_filter={status_filter}")
        if currency:
            params.append(f"currency={currency}")
        query = f"?{'&'.join(params)}" if params else ""
        resp = self._request("GET", f"/api/v1/trading/positions{query}")
        return resp if isinstance(resp, list) else []

    def get_orders(self, limit: int = 50, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        query = f"?limit={limit}&currency={currency}" if currency else f"?limit={limit}"
        resp = self._request("GET", f"/api/v1/trading/orders{query}")
        return resp if isinstance(resp, list) else []

    def get_metrics(self, currency: str = "INR") -> Dict[str, Any]:
        return self._request("GET", f"/api/v1/trading/metrics?currency={currency}")

    # --- Backtesting ---
    def run_backtest(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        initial_capital_inr: float = 100000.0,
        max_risk_per_trade: float = 0.01,
        slippage_bps: float = 5.0,
    ) -> Dict[str, Any]:
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "period": period,
            "initial_capital_inr": initial_capital_inr,
            "max_risk_per_trade": max_risk_per_trade,
            "slippage_bps": slippage_bps,
        }
        return self._request("POST", "/api/v1/backtest/run", payload, timeout=30)

    def place_buy_order(
        self,
        symbol: str,
        price: float,
        stop_loss_price: float,
        take_profit_price: Optional[float] = None,
        quantity: Optional[int] = None,
        enforce_market_hours: bool = False,
        reason: str = "Dashboard Virtual Entry",
    ) -> Dict[str, Any]:
        payload = {
            "symbol": symbol,
            "price": price,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "quantity": quantity,
            "enforce_market_hours": enforce_market_hours,
            "reason": reason,
        }
        return self._request("POST", "/api/v1/trading/orders/buy", payload)

    def close_position(self, position_id: int, exit_price: float, reason: str = "Dashboard Close") -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/trading/positions/{position_id}/close",
            {"exit_price": exit_price, "reason": reason},
        )


api_client = DashboardAPIClient()
