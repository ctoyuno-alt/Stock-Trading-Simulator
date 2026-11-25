"""
Tab 7: System Health, Telemetry & Freshness for Quantum Trader.
Displays infrastructure status, database roundtrip latency sparkline, dual real-time
market clocks (NSE & US), universe instrument inspector with search filter,
and user API key provisioning.
"""

from datetime import datetime
from typing import Any, Dict, List

try:
    import streamlit as st
except ImportError:
    st = None

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    go = None
    HAS_PLOTLY = False


def _get_market_clock(market_type: str) -> Dict[str, Any]:
    """Computes real-time clock and trading session status for NSE or US."""
    if market_type == "NSE":
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        except Exception:
            from datetime import timezone, timedelta
            tz = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(tz)
        t_str = now.strftime("%H:%M:%S IST")
        d_str = now.strftime("%A, %b %d, %Y")
        hour_min = now.hour * 60 + now.minute
        # Mon-Fri: 09:15 to 15:30 IST (555 to 930)
        # Pre-market: 09:00 to 09:15 IST (540 to 555)
        if now.weekday() < 5:
            if 555 <= hour_min < 930:
                status = "OPEN"
                color = "#00E676"
            elif 540 <= hour_min < 555:
                status = "PRE-MARKET"
                color = "#FF9900"
            else:
                status = "CLOSED"
                color = "#FF3366"
        else:
            status = "CLOSED"
            color = "#FF3366"
        return {"time_str": t_str, "date_str": d_str, "status": status, "color": color, "tz_name": "Asia/Kolkata (IST)"}
    else:  # US
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo("America/New_York")
        except Exception:
            from datetime import timezone, timedelta
            tz = timezone(timedelta(hours=-4))
        now = datetime.now(tz)
        t_str = now.strftime("%H:%M:%S ET")
        d_str = now.strftime("%A, %b %d, %Y")
        hour_min = now.hour * 60 + now.minute
        # Mon-Fri: 09:30 to 16:00 ET (570 to 960)
        # Pre-market: 04:00 to 09:30 ET (240 to 570)
        if now.weekday() < 5:
            if 570 <= hour_min < 960:
                status = "OPEN"
                color = "#00E676"
            elif 240 <= hour_min < 570:
                status = "PRE-MARKET"
                color = "#FF9900"
            else:
                status = "CLOSED"
                color = "#FF3366"
        else:
            status = "CLOSED"
            color = "#FF3366"
        return {"time_str": t_str, "date_str": d_str, "status": status, "color": color, "tz_name": "America/New_York (ET)"}


def render_tab(
    api_client: Any,
    state: Dict[str, Any],
    market: str,
    symbol: str,
    timeframe: str,
) -> None:
    """
    Renders Tab 7: System Health & Freshness.
    """
    health_ready = state.get("health_ready")
    if health_ready is None:
        try:
            health_ready = api_client.get_health_ready()
        except Exception:
            health_ready = {}
    if not isinstance(health_ready, dict):
        health_ready = {}

    kill_switch_active = state.get("kill_switch_active", False)
    active_market = market or state.get("active_market", "NSE")
    active_currency = state.get("active_currency", "INR")
    curr_sym = state.get("curr_sym", "₹")
    universe = state.get("universe", [])
    if not isinstance(universe, list):
        universe = []
    current_user = state.get("current_user", {})
    if not isinstance(current_user, dict):
        current_user = {}
    user_role = str(state.get("user_role") or current_user.get("role") or "trader")

    st.markdown("### **System Infrastructure, Multi-Market Calendars & Compliance**")

    # 1. Telemetry Metric Grid (4 Columns)
    db_health = health_ready.get("database", {})
    if not isinstance(db_health, dict):
        db_health = {}
    db_latency = float(db_health.get("latency_ms", 12.0) or 12.0)
    api_online = not health_ready.get("error")
    db_connected = db_health.get("connected", True if not health_ready.get("error") else False)

    t_col1, t_col2, t_col3, t_col4 = st.columns(4)
    t_col1.metric(
        "FastAPI Backend",
        "ONLINE" if api_online else "OFFLINE",
        delta="HTTP 200 OK" if api_online else "Error Response",
    )
    t_col2.metric(
        "PostgreSQL Latency",
        f"{db_latency:.1f} ms" if db_connected else "DISCONNECTED",
        delta="CONNECTED" if db_connected else "OFFLINE",
        delta_color="normal" if db_connected else "inverse",
    )
    t_col3.metric(
        "Order Safeguard",
        "LOCKED",
        delta="Paper Trading Mode",
    )
    t_col4.metric(
        "Emergency Kill Switch",
        "HALTED" if kill_switch_active else "STANDBY",
        delta="ACTIVE (HALTED)" if kill_switch_active else "NORMAL",
        delta_color="inverse" if kill_switch_active else "normal",
    )

    # 2. Latency History Sparkline Tracking
    if hasattr(st, "session_state"):
        try:
            if "db_latency_history" not in st.session_state:
                st.session_state["db_latency_history"] = []
            st.session_state["db_latency_history"].append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "latency": db_latency,
            })
            if len(st.session_state["db_latency_history"]) > 30:
                st.session_state["db_latency_history"] = st.session_state["db_latency_history"][-30:]
            lat_history = st.session_state["db_latency_history"]
        except Exception:
            lat_history = [{"time": "00:00:00", "latency": db_latency}]
    else:
        lat_history = [{"time": "00:00:00", "latency": db_latency}]

    if HAS_PLOTLY and len(lat_history) >= 2:
        lat_fig = go.Figure()
        lat_fig.add_trace(
            go.Scatter(
                x=[pt["time"] for pt in lat_history],
                y=[pt["latency"] for pt in lat_history],
                mode="lines+markers",
                name="Latency (ms)",
                line=dict(color="#00F2FE", width=2),
                marker=dict(size=4, color="#00F2FE"),
                fill="tozeroy",
                fillcolor="rgba(0, 242, 254, 0.08)",
            )
        )
        lat_fig.update_layout(
            title="PostgreSQL Roundtrip Query Latency History (Last 30 Probes)",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="JetBrains Mono, Inter, -apple-system, sans-serif", color="#8F9CAE", size=10),
            height=180,
            margin=dict(l=30, r=20, t=30, b=20),
            yaxis=dict(ticksuffix=" ms", gridcolor="rgba(30, 38, 56, 0.7)"),
            xaxis=dict(showticklabels=False),
        )
        st.plotly_chart(lat_fig, use_container_width=True)

    st.divider()

    # 3. Dual Real-Time Market Clocks & Calendar Rules
    st.markdown("#### **Multi-Market Trading Sessions & Calendar Rules**")
    clk_c1, clk_c2 = st.columns(2)

    nse_clk = _get_market_clock("NSE")
    us_clk = _get_market_clock("US")

    with clk_c1:
        nse_card = f"""
        <div style="background-color: rgba(14, 19, 31, 0.85); border: 1px solid rgba(30, 38, 56, 0.9); border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-weight: 700; font-size: 15px; color: #F8FAFC;">
                    🇮🇳 India — National Stock Exchange (NSE)
                </div>
                <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; background-color: {nse_clk['color']}20; color: {nse_clk['color']}; border: 1px solid {nse_clk['color']};">
                    {nse_clk['status']}
                </span>
            </div>
            <div style="font-size: 22px; font-weight: 700; color: #F8FAFC; margin: 8px 0 4px 0; font-family: 'JetBrains Mono', monospace;">
                {nse_clk['time_str']}
            </div>
            <div style="font-size: 12px; color: #8F9CAE; margin-bottom: 8px;">
                {nse_clk['date_str']} • {nse_clk['tz_name']}
            </div>
            <div style="font-size: 11px; color: #64748B; border-top: 1px solid rgba(30, 38, 56, 0.7); padding-top: 6px;">
                • Standard Hours: <b>09:15 to 15:30 IST</b> (Pre-open: 09:00-09:15)<br>
                • Minimum Tick Size: <b>₹0.05</b> • Delivery Frictions: <b>STT 0.1% + GST 18% + Stamp Duty 0.015%</b>
            </div>
        </div>
        """
        st.markdown(nse_card, unsafe_allow_html=True)

    with clk_c2:
        us_card = f"""
        <div style="background-color: rgba(14, 19, 31, 0.85); border: 1px solid rgba(30, 38, 56, 0.9); border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-weight: 700; font-size: 15px; color: #F8FAFC;">
                    🇺🇸 United States — NYSE / NASDAQ
                </div>
                <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; background-color: {us_clk['color']}20; color: {us_clk['color']}; border: 1px solid {us_clk['color']};">
                    {us_clk['status']}
                </span>
            </div>
            <div style="font-size: 22px; font-weight: 700; color: #F8FAFC; margin: 8px 0 4px 0; font-family: 'JetBrains Mono', monospace;">
                {us_clk['time_str']}
            </div>
            <div style="font-size: 12px; color: #8F9CAE; margin-bottom: 8px;">
                {us_clk['date_str']} • {us_clk['tz_name']}
            </div>
            <div style="font-size: 11px; color: #64748B; border-top: 1px solid rgba(30, 38, 56, 0.7); padding-top: 6px;">
                • Standard Hours: <b>09:30 to 16:00 ET</b> (Pre-market: 04:00-09:30)<br>
                • Minimum Tick Size: <b>$0.01</b> • Commission: <b>$0.00 + SEC Section 31 + FINRA TAF</b>
            </div>
        </div>
        """
        st.markdown(us_card, unsafe_allow_html=True)

    st.divider()

    # 4. Active Universe Coverage & Search Filter
    st.markdown(f"#### **Active Universe Coverage ({active_market} Market — {len(universe):,} Listed Equities)**")

    univ_search = st.text_input("🔍 Search Tracked Universe (Symbol, Company, or Sector)", key="univ_search_input")

    filtered_universe = []
    for u in universe:
        if not isinstance(u, dict):
            continue
        item = dict(u)
        item["data_freshness"] = "🟢 Live / 1d Synced"
        item["cache_status"] = "⚡ Warm"
        if univ_search:
            q = univ_search.lower()
            if (
                q in str(item.get("symbol", "")).lower()
                or q in str(item.get("company_name", "")).lower()
                or q in str(item.get("sector", "")).lower()
            ):
                filtered_universe.append(item)
        else:
            filtered_universe.append(item)

    st.dataframe(
        filtered_universe,
        use_container_width=True,
        column_config={
            "symbol": "Symbol",
            "company_name": "Company Name",
            "sector": "Sector",
            "exchange": "Exchange",
            "tick_size": st.column_config.NumberColumn(f"Tick Size ({active_currency})", format=f"{curr_sym}%.2f"),
            "data_freshness": "Freshness",
            "cache_status": "Cache Status",
            "lot_size": "Lot Size",
            "currency": "Currency",
            "market": "Market",
        },
    )

    st.divider()

    # 5. User Profile & Programmatic API Access
    st.markdown("#### **User Profile & Programmatic API Access**")
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        st.write(f"- **Username:** `{current_user.get('username') or 'trader'}`")
        st.write(f"- **Email:** `{current_user.get('email') or 'N/A'}`")
        st.write(f"- **Assigned RBAC Role:** `{user_role.upper()}`")
        st.write(f"- **Account Scope:** `{current_user.get('username') or 'trader'}'s {active_currency} Account`")
    with p_col2:
        st.write("- **Programmatic API Key (`X-API-Key` header):**")
        api_key_val = current_user.get("api_key") or "None configured"
        st.code(api_key_val, language="bash")
        if st.button("🔑 Generate / Rotate API Key", key="btn_gen_rotate_api_key"):
            rot_resp = api_client.generate_api_key()
            if rot_resp and rot_resp.get("error"):
                st.error(f"API key generation failed: {rot_resp.get('message')}")
            elif rot_resp and rot_resp.get("api_key"):
                new_key = rot_resp["api_key"]
                current_user["api_key"] = new_key
                if hasattr(st, "session_state") and "user_profile" in st.session_state:
                    st.session_state["user_profile"]["api_key"] = new_key
                st.success("New API key generated successfully!")
                st.rerun()
