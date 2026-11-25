"""
Tab 3: Autonomous AI Auto-Trader for Quantum Trader.
Provides autonomous trade execution controls, risk configuration parameters,
real-time decision audit trails, 24/7 daemon management, and GTT bracket orders.
"""

import math
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except ImportError:
    st = None


def render_tab(
    api_client: Any,
    state: Dict[str, Any],
    market: str,
    symbol: str,
    timeframe: str,
) -> None:
    """
    Renders Tab 3: Autonomous AI Auto-Trader.
    Uniform interface contract adhering to dashboard/app.py.
    """
    current_user = state.get("current_user", {})
    if not isinstance(current_user, dict):
        current_user = {}
    active_market = market or state.get("active_market", "NSE")
    active_currency = state.get("active_currency", "INR")
    curr_sym = state.get("curr_sym", "₹")

    # FIX DEFECT: Normalize market code ("NSE" -> "IN", "US" -> "US")
    # Backend routes and daemon telemetry require "IN" or "US" strictly.
    market_code = "IN" if str(active_market).upper() in ("NSE", "IN") else "US"

    st.markdown(f"### **🤖 Autonomous AI Auto-Trading Engine ({active_market} Market — {active_currency})**")
    active_account_label = (
        f"{current_user.get('username')}'s Account" if current_user.get("username") else "Primary Account"
    )
    st.caption(
        f"Fully automated, hands-free order execution powered by quantitative confluence & Gemini AI. "
        f"Currently trading in: **{active_account_label}** ({active_currency}). "
        "24/7 background daemon actively manages all registered accounts."
    )

    # Fetch Auto-Trader Status from Backend
    bot_status = api_client.get_auto_trader_status() if api_client else {}
    if not isinstance(bot_status, dict):
        bot_status = {}
    bot_cfg = bot_status.get("config", {}) if isinstance(bot_status.get("config"), dict) else {}
    last_cycle = bot_status.get("last_cycle_at") or "Never"
    is_bot_enabled = bot_cfg.get("enabled", False)

    # Fetch Daemon Status for Live Telemetry
    daemon_data = api_client.get_daemon_status() if api_client else {}
    if not isinstance(daemon_data, dict):
        daemon_data = {}
    d_running = daemon_data.get("is_running", False)
    markets_status = daemon_data.get("markets_status") or {}
    m_status = (markets_status.get(market_code) or {}) if isinstance(markets_status, dict) else {}
    if not isinstance(m_status, dict):
        m_status = {}
    m_open = m_status.get("is_open", False)
    m_reason = m_status.get("reason", "Off hours")

    # =========================================================================
    # 1. Top Live Telemetry Banner (5 KPI Columns)
    # =========================================================================
    stat_c1, stat_c2, stat_c3, stat_c4, stat_c5 = st.columns(5)
    stat_c1.metric("Auto-Trader", "🟢 ACTIVE" if is_bot_enabled else "⏸️ STANDBY")
    stat_c2.metric("24/7 Daemon", "🟢 RUNNING" if d_running else "⏸️ STOPPED")
    stat_c3.metric(
        f"{active_market} Session",
        "🟢 OPEN" if m_open else "🔴 CLOSED",
        delta=None if m_open else m_reason,
    )
    min_score = bot_cfg.get("min_confluence_score") or 85
    ai_gate_status = "🔒 REQUIRED" if bot_cfg.get("require_ai_approval", True) else "🔓 BYPASSED"
    stat_c4.metric("Confluence & Gate", f"{min_score}/100", delta=ai_gate_status)
    clean_last_cycle = last_cycle.split(".")[0].replace("T", " ") if "." in last_cycle else last_cycle
    stat_c5.metric("Last Heartbeat", clean_last_cycle)

    st.divider()

    # =========================================================================
    # 2. Master Controls & Settings Form
    # =========================================================================
    col_ctrl_left, col_ctrl_right = st.columns([1, 1])

    with col_ctrl_left:
        st.markdown("#### **Execution Controls & Master Switch**")
        new_enabled = st.toggle("Enable Autonomous Auto-Trading", value=is_bot_enabled, key="bot_master_toggle")
        if new_enabled != is_bot_enabled and api_client:
            api_client.update_auto_trader_config({"enabled": new_enabled})
            st.rerun()

        if is_bot_enabled:
            st.success("🤖 AI Auto-Trader is **ACTIVE**. Orders will trigger automatically when high-confluence signals are detected.")
        else:
            st.info("⏸️ AI Auto-Trader is on **STANDBY**. You can run a single cycle manually using the button below.")

        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("⚡ Run AI Auto-Trade Cycle Now", type="primary", use_container_width=True, key="btn_run_autotrade_cycle"):
                if api_client:
                    with st.spinner(f"Scanning {active_market} universe for {active_account_label}, verifying AI gates, and managing positions..."):
                        tick_res = api_client.run_auto_trader_tick(market=market_code, timeframe=timeframe)
                    if tick_res and tick_res.get("error"):
                        st.error(f"Auto-Trader cycle failed: {tick_res.get('message')}")
                    elif tick_res:
                        cycle = (tick_res.get("cycle_result") or {}) if isinstance(tick_res, dict) else {}
                        if not isinstance(cycle, dict):
                            cycle = {}
                        n_exec = cycle.get("orders_executed_count", 0)
                        n_closed = cycle.get("positions_closed_count", 0)
                        target_acc = cycle.get("account_name", active_account_label)
                        st.success(f"Cycle completed for {target_acc}! Executed: {n_exec} orders | Closed: {n_closed} positions.")
                        st.rerun()
        with col_act2:
            if st.button("🗑️ Clear Decision Log", use_container_width=True, key="btn_clear_autotrade_history"):
                if api_client:
                    api_client.clear_auto_trader_history()
                    st.rerun()

        # Quick Manual Daemon Toggles
        st.markdown("##### **24/7 Daemon Quick Control**")
        d_btn_col1, d_btn_col2 = st.columns(2)
        with d_btn_col1:
            if not d_running:
                if st.button("🚀 Start 24/7 Daemon", type="secondary", use_container_width=True, key="btn_start_daemon_quick"):
                    if api_client:
                        api_client.start_daemon(interval_seconds=30)
                        st.rerun()
            else:
                if st.button("⏹️ Stop Daemon", type="secondary", use_container_width=True, key="btn_stop_daemon_quick"):
                    if api_client:
                        api_client.stop_daemon()
                        st.rerun()
        with d_btn_col2:
            st.caption(f"Daemon: **{'RUNNING' if d_running else 'STOPPED'}** (30s background scan interval)")

    with col_ctrl_right:
        st.markdown("#### **Risk & Strategy Parameters**")
        st.markdown(
            """
            <div style="background: rgba(0, 230, 118, 0.08); border: 1px solid rgba(0, 230, 118, 0.25); border-radius: 6px; padding: 6px 12px; margin-bottom: 12px; font-size: 11px; color: #00E676; font-family: 'JetBrains Mono', monospace;">
                🛡️ INSTITUTIONAL RISK PROFILE: 85 Confluence • 1.0% Risk Sizing • Max 2 Positions • Reversal Churn Blocked
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("auto_trader_config_form"):
            try:
                cfg_min_score = int(bot_cfg.get("min_confluence_score") or 85)
            except (ValueError, TypeError):
                cfg_min_score = 85
            new_score = st.slider(
                "Minimum Confluence Score Threshold",
                min_value=50,
                max_value=95,
                value=cfg_min_score,
                step=5,
            )
            new_ai_gate = st.checkbox(
                "Require Gemini AI Confirmation Gate",
                value=bool(bot_cfg.get("require_ai_approval", True)),
            )
            new_rev_exit = st.checkbox(
                "Auto-Exit Position on Strategy Reversal to SELL",
                value=bool(bot_cfg.get("auto_exit_on_reversal", False)),
            )
            new_enforce_hours = st.checkbox(
                "Enforce Strict Exchange Session Hours",
                value=bool(bot_cfg.get("enforce_market_hours", False)),
            )
            try:
                cfg_max_pos = int(bot_cfg.get("max_open_positions") or 2)
            except (ValueError, TypeError):
                cfg_max_pos = 2
            new_max_pos = st.number_input(
                "Maximum Concurrent Open Positions",
                min_value=1,
                max_value=5,
                value=cfg_max_pos,
            )

            save_cfg = st.form_submit_button("💾 Save Auto-Trader Settings", use_container_width=True)
            if save_cfg and api_client:
                cfg_payload = {
                    "min_confluence_score": new_score,
                    "require_ai_approval": new_ai_gate,
                    "auto_exit_on_reversal": new_rev_exit,
                    "enforce_market_hours": new_enforce_hours,
                    "max_open_positions": new_max_pos,
                }
                api_client.update_auto_trader_config(cfg_payload)
                st.success("Auto-Trader configuration saved successfully!")
                st.rerun()

    st.divider()

    # =========================================================================
    # 3. Interactive Virtual GTT Bracket Orders Table
    # =========================================================================
    st.markdown("#### **🏛️ Active Virtual Exchange GTT Bracket Orders**")
    st.caption("Exchange-side simulated Stop-Loss and Take-Profit bracket orders protecting open positions with zero execution lag.")
    gtt_orders = api_client.get_gtt_orders() if api_client else []
    if not isinstance(gtt_orders, list):
        gtt_orders = []

    if not gtt_orders:
        st.markdown(
            """
            <div style="background:#0E131F; border:1px solid #1E2638; border-radius:8px; padding:16px 20px; text-align:center; box-shadow:0 4px 16px rgba(0,0,0,0.25); margin-bottom:14px;">
                <div style="font-size:20px; margin-bottom:6px;">🛡️</div>
                <div style="font-size:13px; font-weight:600; color:#F8FAFC;">No Active GTT Bracket Orders</div>
                <div style="font-size:11.5px; color:#8F9CAE; margin-top:4px;">
                    When the Auto-Trader opens a position, simulated exchange-side Stop-Loss and Take-Profit GTT brackets are automatically registered here.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.dataframe(
            gtt_orders,
            use_container_width=True,
            column_config={
                "order_id": "GTT ID",
                "symbol": "Symbol",
                "order_type": "Order Type",
                "trigger_price": st.column_config.NumberColumn(f"Trigger Price ({curr_sym})", format=f"{curr_sym}%.2f"),
                "limit_price": st.column_config.NumberColumn(f"Limit Price ({curr_sym})", format=f"{curr_sym}%.2f"),
                "quantity": "Quantity",
                "status": "Status",
                "created_at": "Registered At",
            },
        )

    st.divider()

    # =========================================================================
    # 4. Live Decision Audit Feed (Dual-View: Rationale Cards vs Structured Table)
    # =========================================================================
    st.markdown("#### **Real-Time AI Decision Feed & Audit Trail**")
    decisions = bot_status.get("recent_decisions", [])
    if not isinstance(decisions, list):
        decisions = []

    if not decisions:
        st.info("No decisions logged yet. Click 'Run AI Auto-Trade Cycle Now' above to begin autonomous scanning.")
    else:
        feed_view = st.radio(
            "Decision Audit View Mode",
            ["Interactive Rationale Cards Feed", "Structured Table View"],
            horizontal=True,
            index=0,
            key="autotrader_feed_view_mode",
        )

        if feed_view == "Structured Table View":
            st.dataframe(
                decisions,
                use_container_width=True,
                column_config={
                    "timestamp": "Timestamp",
                    "symbol": "Symbol",
                    "market": "Market",
                    "action": "Action",
                    "score": st.column_config.NumberColumn("Score", format="%d/100"),
                    "executed": "Executed",
                    "order_id": "Order ID",
                    "pnl": st.column_config.NumberColumn(f"P&L ({active_currency})", format=f"{curr_sym}%.2f"),
                    "reason": "AI / Strategy Rationale",
                },
            )
        else:
            # Interactive Rationale Cards Feed
            for d in decisions[:25]:
                d_action = str(d.get("action", "HOLD")).upper()
                d_symbol = d.get("symbol", "—")
                d_market = d.get("market", active_market)
                d_score = d.get("score")
                d_executed = d.get("executed", False)
                d_order_id = d.get("order_id")
                d_pnl = d.get("pnl")
                d_reason = d.get("reason", "No rationale recorded.")
                d_time = str(d.get("timestamp", "—")).split(".")[0].replace("T", " ")

                # Action styling
                if d_action == "BUY":
                    a_color = "#00E676"
                    a_bg = "rgba(0, 230, 118, 0.12)"
                    a_border = "rgba(0, 230, 118, 0.28)"
                    a_label = "🟢 BUY"
                elif "TP" in d_action or "TAKE_PROFIT" in d_action:
                    a_color = "#00F2FE"
                    a_bg = "rgba(0, 242, 254, 0.12)"
                    a_border = "rgba(0, 242, 254, 0.28)"
                    a_label = "🎯 TAKE PROFIT"
                elif "SL" in d_action or "STOP_LOSS" in d_action:
                    a_color = "#FF3366"
                    a_bg = "rgba(255, 51, 102, 0.12)"
                    a_border = "rgba(255, 51, 102, 0.28)"
                    a_label = "🛑 STOP LOSS"
                elif "REVERSAL" in d_action:
                    a_color = "#FF9900"
                    a_bg = "rgba(255, 153, 0, 0.12)"
                    a_border = "rgba(255, 153, 0, 0.28)"
                    a_label = "⚠️ STRATEGY REVERSAL"
                elif d_action == "SKIP":
                    a_color = "#8F9CAE"
                    a_bg = "rgba(143, 156, 174, 0.12)"
                    a_border = "rgba(143, 156, 174, 0.28)"
                    a_label = "⏭️ SKIP"
                else:
                    a_color = "#64748B"
                    a_bg = "rgba(100, 116, 139, 0.12)"
                    a_border = "rgba(100, 116, 139, 0.28)"
                    a_label = "⏸️ HOLD"

                # Executed badge
                if d_executed:
                    exec_badge = f'<span style="background:rgba(0,230,118,0.15); color:#00E676; border:1px solid rgba(0,230,118,0.3); padding:2px 8px; border-radius:4px; font-size:10.5px; font-family:\'JetBrains Mono\', monospace; font-weight:600;">✅ EXECUTED {f"(#{d_order_id})" if d_order_id else ""}</span>'
                else:
                    exec_badge = '<span style="background:rgba(100,116,139,0.15); color:#8F9CAE; border:1px solid rgba(100,116,139,0.3); padding:2px 8px; border-radius:4px; font-size:10.5px; font-family:\'JetBrains Mono\', monospace;">ℹ️ EVALUATED ONLY</span>'

                score_badge = (
                    f'<span style="background:rgba(0,242,254,0.12); color:#00F2FE; border:1px solid rgba(0,242,254,0.25); padding:2px 8px; border-radius:4px; font-size:10.5px; font-family:\'JetBrains Mono\', monospace;">SCORE: {d_score}/100</span>'
                    if d_score is not None
                    else ""
                )

                pnl_badge = ""
                if d_pnl is not None:
                    try:
                        pnl_val = float(d_pnl)
                        if not math.isnan(pnl_val):
                            pnl_color = "#00E676" if pnl_val >= 0 else "#FF3366"
                            pnl_badge = f'<span style="color:{pnl_color}; font-family:\'JetBrains Mono\', monospace; font-size:11px; font-weight:600; margin-left:8px;">P&L: {curr_sym}{pnl_val:+,.2f}</span>'
                    except (ValueError, TypeError):
                        pass

                st.markdown(
                    f"""
                    <div style="background:#0E131F; border:1px solid #1E2638; border-left:3px solid {a_color}; border-radius:6px; padding:12px 16px; margin-bottom:8px; box-shadow:0 2px 8px rgba(0,0,0,0.2);">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span style="background:{a_bg}; color:{a_color}; border:1px solid {a_border}; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700; font-family:'JetBrains Mono', monospace;">
                                    {a_label}
                                </span>
                                <span style="font-family:'JetBrains Mono', monospace; font-size:13px; font-weight:700; color:#F8FAFC;">
                                    {d_symbol}
                                </span>
                                <span style="font-size:11px; color:#8F9CAE;">({d_market})</span>
                                {score_badge}
                                {pnl_badge}
                            </div>
                            <div style="display:flex; align-items:center; gap:10px;">
                                {exec_badge}
                                <span style="font-size:11px; color:#6B7280; font-family:'JetBrains Mono', monospace;">{d_time}</span>
                            </div>
                        </div>
                        <div style="font-size:12px; color:#94A3B8; line-height:1.4; margin-top:4px;">
                            {d_reason}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()

    # =========================================================================
    # 5. 24/7 Autonomous Background Daemon & Safety Controls
    # =========================================================================
    st.markdown("#### **🛡️ 24/7 Background Trading Daemon & Real-World Safety**")
    d_col1, d_col2 = st.columns([1, 1])

    with d_col1:
        st.markdown("##### **24/7 Server Daemon Status**")
        d_interval = daemon_data.get("interval_seconds", 30)
        d_cycles = daemon_data.get("cycles_completed", 0)
        d_last = daemon_data.get("last_cycle_at") or "Never"

        m_badge = "🟢 Session OPEN" if m_open else f"🔴 Session CLOSED ({m_reason})"
        d_badge = "🟢 ACTIVE (Running 24/7)" if d_running else "⏸️ STOPPED"

        st.caption(f"Status: **{d_badge}** • {active_market} Market: **{m_badge}**")
        st.caption(f"Polling Interval: **{d_interval}s** • Completed Cycles: **{d_cycles}** • Last Run: **{d_last.split('.')[0] if '.' in d_last else d_last}**")

        c_d1, c_d2 = st.columns(2)
        with c_d1:
            if not d_running:
                if st.button("🚀 Start 24/7 Background Daemon", type="primary", use_container_width=True, key="btn_start_daemon_tab"):
                    if api_client:
                        api_client.start_daemon(interval_seconds=30)
                        st.rerun()
            else:
                if st.button("⏹️ Stop Background Daemon", type="secondary", use_container_width=True, key="btn_stop_daemon_tab"):
                    if api_client:
                        api_client.stop_daemon()
                        st.rerun()
        with c_d2:
            st.caption("When active, trades execute autonomously on the server even if your browser is closed.")

    with d_col2:
        st.markdown("##### **📱 Free Real-Time Telegram Push Alerts**")
        with st.expander("Configure Telegram Trade Alerts"):
            st.caption("Get instant notifications for orders, take-profits, and stop-loss triggers on your phone.")
            tg_token = st.text_input("Telegram Bot Token (from @BotFather)", type="password", key="tg_bot_token_input")
            tg_chat = st.text_input("Telegram Chat ID", key="tg_chat_id_input")
            if st.button("🔔 Send Test Notification", use_container_width=True, key="btn_test_tg_notification"):
                if api_client:
                    test_res = api_client.test_telegram_notification(bot_token=tg_token or None, chat_id=tg_chat or None)
                    if test_res and test_res.get("success"):
                        st.success(test_res.get("message", "Test alert delivered!"))
                    else:
                        msg = test_res.get("message", "Failed to send alert. Check token/chat ID.") if test_res else "Failed."
                        st.error(msg)
