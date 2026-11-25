"""
Modular Tabs Package for Quantum Trader Dashboard.
Exposes render_tab(api_client, state, market, symbol, timeframe) across all 8 functional areas.
"""

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

__all__ = [
    "tab_market",
    "tab_ai",
    "tab_autotrader",
    "tab_positions",
    "tab_ledger",
    "tab_backtest",
    "tab_health",
    "tab_admin",
]
