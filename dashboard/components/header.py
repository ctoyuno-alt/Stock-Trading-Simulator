"""
Institutional Top Header App Bar for Quantum Trader.
"""

import textwrap
from typing import Any, Dict, Optional

try:
    import streamlit as st
except ImportError:
    st = None


def render_top_header(state: Dict[str, Any], api_client: Optional[Any] = None) -> None:
    """
    Renders the institutional top app bar (.top-app-bar) with branding,
    session badge, daemon status capsule, and simulation pill.
    """
    current_user = state.get("current_user") or {}
    if not isinstance(current_user, dict):
        current_user = {}
    user_role = str(state.get("user_role") or current_user.get("role") or "trader")
    username = str(current_user.get("username") or "trader")
    is_admin = state.get("is_admin", False)
    is_us_market = state.get("is_us_market", False)
    active_market = state.get("active_market", "US" if is_us_market else "NSE")
    active_currency = state.get("active_currency", "USD" if is_us_market else "INR")
    is_open = state.get("is_open", False)

    client = api_client or state.get("api_client")
    daemon_info = state.get("daemon_info")
    if daemon_info is None and client and hasattr(client, "get_daemon_status"):
        try:
            daemon_info = client.get_daemon_status()
        except Exception:
            daemon_info = {"is_running": False}
    if not isinstance(daemon_info, dict):
        daemon_info = {"is_running": False}

    market_header_text = "US Equities (NYSE/NASDAQ)" if is_us_market else "Indian Equities (NSE/BSE)"
    daemon_active = daemon_info.get("is_running", False)
    daemon_badge_class = "pill-open" if daemon_active else "pill-closed"
    daemon_badge_text = "24/7 DAEMON: ACTIVE" if daemon_active else "24/7 DAEMON: STANDBY"
    session_badge_class = "pill-open" if is_open else "pill-closed"
    session_badge_text = f"{active_market} SESSION: OPEN" if is_open else f"{active_market} SESSION: CLOSED"
    user_badge_text = f"👤 {username.upper()} ({user_role.upper()})"

    header_html = textwrap.dedent(f"""
<div class="top-app-bar">
    <div>
        <div class="brand-title">
            <span>⚡ QUANTUM TRADER</span>
            <span class="status-pill pill-paper">{market_header_text}</span>
        </div>
        <div class="brand-sub">Institutional Quantitative Analytics • Multi-Factor Confluence Strategy • Broker Independent ({active_currency})</div>
    </div>
    <div class="status-capsules">
        <span class="status-pill {'pill-paper' if is_admin else 'pill-daemon'}">{user_badge_text}</span>
        <span class="status-pill {session_badge_class}">● {session_badge_text}</span>
        <span class="status-pill {daemon_badge_class}">● {daemon_badge_text}</span>
        <span class="status-pill pill-paper">VIRTUAL SIMULATION</span>
    </div>
</div>
""").strip()
    st.markdown(header_html, unsafe_allow_html=True)
