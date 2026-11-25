"""
Quantum Trader — Institutional AI Paper Trading Platform.
Main Streamlit Orchestrator delegating to modular auth, components, and tabs.
"""

from datetime import datetime
from pathlib import Path
import sys
import streamlit as st

_APP_ROOT = str(Path(__file__).resolve().parent.parent)
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from dashboard.api_client import api_client
from dashboard.styles import inject_custom_css
from dashboard.auth import render_auth_screen, handle_logout
from dashboard.components.ticker import render_ticker_tape
from dashboard.components.header import render_top_header
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

# 1. Page Configuration & Institutional Theming
st.set_page_config(
    page_title="Quantum Trader — Institutional AI Paper Trading",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_custom_css()

# 2. Authentication Gate (halts via st.stop() if unauthenticated)
current_user = render_auth_screen(api_client)

# 3. Context & Global Status
user_role = str((current_user.get("role") if isinstance(current_user, dict) else None) or "trader")
is_admin = user_role.lower() == "admin"
system_status = api_client.get_system_status()
if not isinstance(system_status, dict):
    system_status = {}
health_ready = api_client.get_health_ready()
if not isinstance(health_ready, dict):
    health_ready = {}
kill_switch_active = system_status.get("safety_guardrails", {}).get("kill_switch_active", False)

# 4. Sidebar Controls & Market Navigation
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <span style="font-size: 24px;">⚡</span>
            <div>
                <div class="sidebar-brand-title">QUANTUM TRADER</div>
                <div style="font-size: 11px; color: #8F9CAE;">AI Quantitative Trading Station</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    username_display = str((current_user.get("username") if isinstance(current_user, dict) else None) or "User")
    st.markdown(
        f"""
        <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-weight: 600; font-size: 13px; color: #F8FAFC;">👤 {username_display}</div>
                <div style="font-size: 10px; color: #8F9CAE; font-family: 'JetBrains Mono', monospace;">ROLE: {user_role.upper()}</div>
            </div>
            <span class="status-pill {'pill-paper' if is_admin else 'pill-daemon'}">{user_role.upper()}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("🚪 Sign Out", use_container_width=True, key="btn_sidebar_signout"):
        handle_logout(api_client)

    st.divider()

    market_choice = st.radio(
        "Active Market / Exchange",
        ["🇮🇳 India (NSE) - INR (₹)", "🇺🇸 US (NYSE/NASDAQ) - USD ($)"],
        index=0,
    )
    is_us_market = "US" in market_choice
    active_market = "US" if is_us_market else "IN"
    active_currency = "USD" if is_us_market else "INR"
    curr_sym = "$" if is_us_market else "₹"

    if is_us_market:
        is_open = system_status.get("us_market_open", False)
        clock_time = system_status.get("et_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S ET"))
        badge_text = "US MARKET OPEN" if is_open else "US MARKET CLOSED"
        clock_label = f"ET: {clock_time}"
    else:
        is_open = system_status.get("market_open", False)
        clock_time = system_status.get("ist_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"))
        badge_text = "NSE MARKET OPEN" if is_open else "NSE MARKET CLOSED"
        clock_label = f"IST: {clock_time}"

    pill_cls = "pill-open" if is_open else "pill-closed"
    st.markdown(
        f'<span class="status-pill {pill_cls}">● {badge_text}</span> <span class="status-pill pill-paper">VIRTUAL</span>',
        unsafe_allow_html=True,
    )
    st.caption(clock_label)

    st.divider()

    universe = api_client.get_universe(market=active_market)
    if not isinstance(universe, list):
        universe = []
    all_universe_symbols = [inst["symbol"] for inst in universe] or (
        ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V"]
        if is_us_market
        else ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "LT", "TATAMOTORS"]
    )
    sym_to_name = {inst["symbol"]: inst.get("company_name", "") for inst in universe}

    if not is_us_market and len(all_universe_symbols) > 15:
        top_bluechips = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "LT", "TATAMOTORS"]
        scope = st.radio(
            "Universe Scope",
            [f"🏛️ All NSE Equities ({len(all_universe_symbols):,})", "🔥 Top Liquid Blue-Chips (10)"],
            index=0,
            horizontal=False,
        )
        if "Top Liquid" in scope:
            universe_symbols = [s for s in top_bluechips if s in all_universe_symbols]
        else:
            universe_symbols = all_universe_symbols
    else:
        universe_symbols = all_universe_symbols

    portfolio = api_client.get_portfolio(currency=active_currency)
    if not isinstance(portfolio, dict):
        portfolio = {}

    selected_symbol = st.selectbox(
        f"Select Instrument ({len(universe_symbols):,} Available)",
        options=universe_symbols,
        index=0,
        format_func=lambda s: f"{s} — {sym_to_name.get(s, '')}" if sym_to_name.get(s) else s,
    )
    timeframe = st.selectbox("Timeframe", options=["1d", "1h", "15m"], index=0)

    st.markdown("#### **Live Monitoring Mode**")
    auto_refresh = st.toggle("🔴 Auto-Refresh Live Stream", value=False)
    refresh_rate = 10
    auto_trade_on_refresh = False
    if auto_refresh:
        refresh_rate = st.select_slider(
            "Refresh Interval",
            options=[5, 10, 15, 30, 60],
            value=10,
            format_func=lambda s: f"{s}s",
        )
        auto_trade_on_refresh = st.checkbox("🤖 Auto-Manage Positions & AI Trades on Refresh", value=True)
        st.caption(f"⚡ Live polling active ({refresh_rate}s interval)")

    st.divider()

    default_cap = 25000.0 if is_us_market else 100000.0
    equity_val = portfolio.get("equity_inr", default_cap)
    cash_val = portfolio.get("cash_balance_inr", default_cap)
    open_count = portfolio.get("open_positions_count", 0)
    total_pnl = portfolio.get("total_pnl_inr", 0.0)

    st.markdown(f"#### **Portfolio Snapshot ({active_currency})**")
    col_s1, col_s2 = st.columns(2)
    col_s1.metric("Equity", f"{curr_sym}{equity_val:,.2f}")
    col_s2.metric("Cash", f"{curr_sym}{cash_val:,.2f}")
    st.metric("Total P&L", f"{curr_sym}{total_pnl:+,.2f}", delta=f"{portfolio.get('return_on_initial_capital_pct', 0.0):+.2f}%")
    st.caption(f"Active Positions: {open_count} / 2 max (Min-Risk Guardrail)")

    st.divider()

    st.markdown("#### **Safety Controls**")
    if not is_admin:
        st.caption("🔒 *Kill switch and account reset are restricted to Administrator accounts.*")
    else:
        if kill_switch_active:
            st.error("⚠️ KILL SWITCH ACTIVE - Order placement halted")
            if st.button("Deactivate Kill Switch", use_container_width=True):
                api_client.toggle_kill_switch(activate=False, reason="User toggled off in dashboard")
                st.rerun()
        else:
            st.success("Operational - Virtual trading allowed")
            if st.button("ACTIVATE EMERGENCY KILL SWITCH", type="primary", use_container_width=True):
                api_client.toggle_kill_switch(activate=True, reason="User activated emergency stop")
                st.rerun()

        st.divider()
        with st.expander("🔄 Reset Virtual Account (Clean Slate)"):
            st.caption(f"Clears existing orders/positions and resets starting capital to {curr_sym}{default_cap:,.2f} for fresh trading with real market prices.")
            if st.button(f"Confirm Reset to {curr_sym}{default_cap:,.0f}", use_container_width=True, type="secondary"):
                res = api_client.reset_paper_account(currency=active_currency, initial_capital=default_cap)
                if res and res.get("error"):
                    st.error(f"Reset failed: {res.get('message')}")
                else:
                    st.success(f"Account successfully reset to {curr_sym}{default_cap:,.2f}!")
                    st.rerun()

# 5. Shared State Assembly
state = {
    "current_user": current_user,
    "user_role": user_role,
    "is_admin": is_admin,
    "is_us_market": is_us_market,
    "active_market": active_market,
    "active_currency": active_currency,
    "curr_sym": curr_sym,
    "is_open": is_open,
    "system_status": system_status,
    "health_ready": health_ready,
    "kill_switch_active": kill_switch_active,
    "universe": universe,
    "universe_symbols": universe_symbols,
    "sym_to_name": sym_to_name,
    "portfolio": portfolio,
    "default_cap": default_cap,
    "equity_val": equity_val,
    "cash_val": cash_val,
    "open_count": open_count,
    "total_pnl": total_pnl,
    "auto_refresh": auto_refresh,
    "refresh_rate": refresh_rate,
    "auto_trade_on_refresh": auto_trade_on_refresh,
}

# 6. Top Streaming Ticker Marquee & Institutional Header
render_ticker_tape(api_client, market=active_market)
render_top_header(state, api_client=api_client)

# 7. Tab Declarations & Modular Rendering
tab_specs = [
    ("📊 Market & Technicals", tab_market.render_tab),
    ("🧠 AI Confluence Analysis", tab_ai.render_tab),
    ("🤖 Autonomous AI Auto-Trader", tab_autotrader.render_tab),
    ("💼 Positions & Execution", tab_positions.render_tab),
    ("📜 Trade Ledger & Performance", tab_ledger.render_tab),
    ("🧪 Historical Backtest", tab_backtest.render_tab),
    ("🛡️ System Health & Freshness", tab_health.render_tab),
]
if is_admin:
    tab_specs.append(("👤 Admin User & Account Management", tab_admin.render_tab))

tab_containers = st.tabs([title for title, _ in tab_specs])
for container, (_, render_fn) in zip(tab_containers, tab_specs):
    with container:
        render_fn(api_client, state, active_market, selected_symbol, timeframe)

# 8. Background Polling & Live Stream Loop
if auto_refresh:
    import time
    if auto_trade_on_refresh and not kill_switch_active:
        api_client.run_auto_trader_tick(market=active_market, timeframe=timeframe)
    time.sleep(refresh_rate)
    st.rerun()
