"""
Gemini-Powered AI Paper Trading Simulator (NSE/BSE) - Streamlit Dashboard.

Features:
1. Portfolio balance, purchasing power, and equity curve.
2. Active watchlist of 10 liquid NSE equities with delay notices.
3. Interactive Plotly charts (Candlestick, EMA 20/50, VWAP, Volume, RSI, MACD).
4. Gemini AI analysis, technical signal explanations, and non-hallucinatory confidence ratings.
5. Open virtual positions with real-time unrealized P&L and one-click manual closure.
6. Chronological trade order ledger with itemized Indian taxes (STT, Brokerage, GST).
7. Realized P&L, Unrealized P&L, Win Rate, Profit Factor, Max Drawdown, Sharpe Ratio.
8. 1% Equity Risk Position Sizing calculator and virtual execution portal.
9. System health, database latency, and NSE holiday calendar.
"""

from datetime import datetime
import streamlit as st

from dashboard.api_client import api_client
from dashboard.components.charts import (
    create_candlestick_with_indicators,
    create_equity_curve_chart,
    create_rsi_chart,
)

# Page configuration
st.set_page_config(
    page_title="AI Paper Trading Simulator (NSE/BSE)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Institutional CSS Styling
st.markdown("""
<style>
    .main-header { font-size: 26px; font-weight: 700; color: #FAFAFA; margin-bottom: 0px; }
    .sub-caption { font-size: 13px; color: #9E9E9E; margin-bottom: 15px; }
    .badge-open { background-color: #1B5E20; color: #A5D6A7; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .badge-closed { background-color: #B71C1C; color: #FFCDD2; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .badge-paper { background-color: #0D47A1; color: #90CAF9; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .metric-card { background-color: #1E1E1E; border-radius: 8px; padding: 12px; border: 1px solid #333333; }
</style>
""", unsafe_allow_html=True)


# --- Fetch Global System & Portfolio State ---
system_status = api_client.get_system_status()
health_ready = api_client.get_health_ready()
portfolio = api_client.get_portfolio()
universe = api_client.get_universe()

is_market_open = system_status.get("market_open", False)
ist_time = system_status.get("ist_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"))
kill_switch_active = system_status.get("safety_guardrails", {}).get("kill_switch_active", False)

universe_symbols = [inst["symbol"] for inst in universe] or [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "LT", "TATAMOTORS"
]


# --- Sidebar Controls & Metrics ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bullish.png", width=64)
    st.markdown("### **NSE/BSE Paper Simulator**")
    st.caption("AI-Assisted Quantitative Research Platform")

    # Session Status Badge
    if is_market_open:
        st.markdown(f'<span class="badge-open">● NSE MARKET OPEN</span> <span class="badge-paper">VIRTUAL</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="badge-closed">● NSE MARKET CLOSED</span> <span class="badge-paper">VIRTUAL</span>', unsafe_allow_html=True)
    st.caption(f"IST: {ist_time}")

    st.divider()

    # Instrument & Timeframe Selectors
    selected_symbol = st.selectbox("Select Instrument (Universe)", options=universe_symbols, index=0)
    timeframe = st.selectbox("Timeframe", options=["1d", "1h", "15m"], index=0)

    st.divider()

    # Portfolio Quick Snapshot
    st.markdown("#### **Portfolio Snapshot**")
    equity_val = portfolio.get("equity_inr", 100000.0)
    cash_val = portfolio.get("cash_balance_inr", 100000.0)
    open_count = portfolio.get("open_positions_count", 0)
    total_pnl = portfolio.get("total_pnl_inr", 0.0)

    col_s1, col_s2 = st.columns(2)
    col_s1.metric("Equity", f"₹{equity_val:,.2f}")
    col_s2.metric("Cash", f"₹{cash_val:,.2f}")
    st.metric("Total P&L", f"₹{total_pnl:+,.2f}", delta=f"{portfolio.get('return_on_initial_capital_pct', 0.0):+.2f}%")
    st.caption(f"Active Positions: {open_count} / 5 max")

    st.divider()

    # Emergency Kill Switch
    st.markdown("#### **Safety Controls**")
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


# --- Main Dashboard Header ---
st.markdown(
    '<div class="main-header">📈 Gemini-Powered AI Paper Trading Simulator</div>'
    '<div class="sub-caption">Indian Stock Market (NSE/BSE) Quantitative Research • Strictly Virtual Funds • Broker Independent</div>',
    unsafe_allow_html=True,
)


# --- Dashboard Tabs ---
tab_market, tab_ai, tab_positions, tab_ledger, tab_health = st.tabs([
    "📊 Market & Technicals",
    "🤖 AI & Strategy Signals",
    "💼 Positions & Execution",
    "📜 Trade Ledger & Performance",
    "🛡️ System Health & Freshness",
])


# ==============================================================================
# TAB 1: Market & Technical Indicators
# ==============================================================================
with tab_market:
    st.markdown(f"### **{selected_symbol} - Technical Analysis & Indicators**")
    st.caption("Data source: Yahoo Finance (15-min delayed quotes for prototyping). Strictly for paper research.")

    # Fetch Candles & Indicators for selected instrument
    with st.spinner(f"Loading market data and quantitative indicators for {selected_symbol}..."):
        candles_data = api_client.get_candles(selected_symbol, timeframe=timeframe)
        indicators_data = api_client.get_indicators(selected_symbol, timeframe=timeframe)

    if candles_data.get("error"):
        st.error(f"Failed to fetch market data: {candles_data.get('message')}")
    else:
        # Latest Snapshot KPIs
        latest_snap = indicators_data.get("latest_snapshot", {})
        if latest_snap:
            kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5, kpi_c6 = st.columns(6)
            kpi_c1.metric("Close", f"₹{latest_snap.get('close_price', 0):,.2f}")
            kpi_c2.metric("EMA 20", f"₹{latest_snap.get('ema_fast_20') or 0:,.2f}")
            kpi_c3.metric("EMA 50", f"₹{latest_snap.get('ema_slow_50') or 0:,.2f}", delta=f"{latest_snap.get('ema_spread_pct') or 0:+.2f}%")
            kpi_c4.metric("RSI 14", f"{latest_snap.get('rsi_14') or 0:.1f}", delta=latest_snap.get("rsi_regime"))
            kpi_c5.metric("MACD Hist", f"{latest_snap.get('macd_histogram') or 0:+.3f}", delta=latest_snap.get("macd_state"))
            kpi_c6.metric("VWAP", f"₹{latest_snap.get('vwap') or 0:,.2f}", delta=f"{latest_snap.get('price_to_vwap_pct') or 0:+.2f}%")

        # Interactive Plotly Candlestick Chart
        fig = create_candlestick_with_indicators(candles_data, indicators_data, symbol=selected_symbol)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        # RSI Subplot Chart
        if indicators_data.get("rsi"):
            rsi_fig = create_rsi_chart(indicators_data.get("timestamps", []), indicators_data.get("rsi", []))
            if rsi_fig:
                st.plotly_chart(rsi_fig, use_container_width=True)


# ==============================================================================
# TAB 2: AI & Deterministic Strategy Signals
# ==============================================================================
with tab_ai:
    st.markdown(f"### **Strategy Signals & Gemini AI Confluence Analysis: {selected_symbol}**")

    col_ai_left, col_ai_right = st.columns([1, 1])

    # Left: Deterministic Python Strategy Signal
    with col_ai_left:
        st.markdown("#### **Deterministic Strategy Engine (Python)**")
        with st.spinner("Evaluating multi-factor swing trading rules..."):
            signal_data = api_client.get_signal(selected_symbol, timeframe=timeframe)

        if signal_data.get("error"):
            st.warning(f"Could not load strategy signal: {signal_data.get('message')}")
        else:
            action = signal_data.get("action", "HOLD")
            action_color = "#00C087" if action == "BUY" else ("#FF4B4B" if action == "SELL" else "#BDBDBD")

            st.markdown(
                f'<div style="background-color: #212121; padding: 16px; border-radius: 8px; border-left: 6px solid {action_color};">'
                f'<h3 style="margin:0; color: {action_color};">Action: {action} ({signal_data.get("strength")})</h3>'
                f'<p style="margin: 5px 0 0 0; color: #EEEEEE;"><strong>Technical Confluence Score:</strong> {signal_data.get("technical_score")}/100</p>'
                f'<p style="margin: 5px 0 0 0; font-size: 13px; color: #BDBDBD;">{signal_data.get("primary_trigger")}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown("##### **Quantitative Target & Risk Limits:**")
            t_col1, t_col2, t_col3 = st.columns(3)
            t_col1.metric("Entry Benchmark", f"₹{signal_data.get('entry_price', 0):,.2f}")
            t_col2.metric("Stop Loss", f"₹{signal_data.get('suggested_stop_loss', 0):,.2f}", delta=f"-{signal_data.get('stop_loss_pct', 0):.2f}%")
            t_col3.metric("Take Profit", f"₹{signal_data.get('suggested_take_profit', 0):,.2f}", delta=f"+{signal_data.get('target_profit_pct', 0):.2f}%")

            st.markdown("##### **Confirming Factors:**")
            for c in signal_data.get("confirming_factors", []):
                st.markdown(f"- ✅ <span style='color:#A5D6A7;'>{c}</span>", unsafe_allow_html=True)

            if signal_data.get("conflicting_factors"):
                st.markdown("##### **Conflicting Factors / Warning Signs:**")
                for cf in signal_data.get("conflicting_factors", []):
                    st.markdown(f"- ⚠️ <span style='color:#EF9A9A;'>{cf}</span>", unsafe_allow_html=True)

    # Right: Google Gemini AI Analysis
    with col_ai_right:
        st.markdown("#### **Google Gemini AI Quantitative Interpretation**")
        if st.button("Generate AI Market Interpretation", type="secondary", use_container_width=True):
            st.session_state["trigger_ai"] = True

        if st.session_state.get("trigger_ai") or True:
            with st.spinner("Synthesizing grounded technical interpretation via Gemini..."):
                ai_resp = api_client.get_ai_analysis(selected_symbol, timeframe=timeframe)

            if ai_resp.get("error"):
                st.warning(f"AI service response: {ai_resp.get('message')}")
            else:
                ai_data = ai_resp.get("ai_analysis", {})
                st.info(f"**AI Stance:** {ai_data.get('recommended_action_opinion', 'FAVORS_PATIENCE')} (Confidence Rating: {ai_data.get('ai_confidence_score', 0):.1f}/100)")
                st.caption(f"**Confidence Rationale:** {ai_data.get('ai_confidence_rationale', '')}")

                with st.expander("📈 Trend & Moving Averages Interpretation", expanded=True):
                    st.write(ai_data.get("trend_analysis", "N/A"))

                with st.expander("⚡ Momentum & RSI 14 Analysis", expanded=True):
                    st.write(ai_data.get("momentum_analysis", "N/A"))

                with st.expander("🌊 MACD & Institutional VWAP Assessment", expanded=False):
                    st.write(f"**MACD:** {ai_data.get('macd_interpretation', 'N/A')}")
                    st.write(f"**VWAP:** {ai_data.get('vwap_relationship', 'N/A')}")

                with st.expander("⚠️ Key Identified Market Risks", expanded=False):
                    for rk in ai_data.get("key_risks", []):
                        st.markdown(f"- {rk}")

                st.warning(f"**ETHICAL NOTICE:** {ai_data.get('disclaimer', '')}")


# ==============================================================================
# TAB 3: Positions & Execution Portal
# ==============================================================================
with tab_positions:
    st.markdown("### **Virtual Portfolio Exposure & Position Management**")

    # Open Positions List
    open_positions = api_client.get_positions(status_filter="OPEN")

    if not open_positions:
        st.info("No active virtual swing positions currently open. Use the order execution portal below to enter trades.")
    else:
        st.markdown(f"#### **Active Open Positions ({len(open_positions)} / 5 Max)**")
        for pos in open_positions:
            p_col1, p_col2, p_col3, p_col4, p_col5, p_col6 = st.columns([2, 2, 2, 2, 2, 2])
            pnl = pos.get("unrealized_pnl_inr", 0.0)
            pnl_color = "green" if pnl >= 0 else "red"

            p_col1.markdown(f"**{pos['symbol']}** ({pos['quantity']} shs)")
            p_col2.metric("Entry", f"₹{pos['entry_price']:,.2f}")
            p_col3.metric("Current", f"₹{pos['current_price']:,.2f}")
            p_col4.metric("Unrealized P&L", f"₹{pnl:+,.2f}")
            p_col5.markdown(f"**SL:** ₹{pos['stop_loss_price']:,.2f}<br>**TP:** ₹{pos.get('take_profit_price') or 0:,.2f}", unsafe_allow_html=True)

            if p_col6.button("Close Position", key=f"close_{pos['id']}", type="primary"):
                close_res = api_client.close_position(pos["id"], exit_price=pos["current_price"])
                if close_res.get("error"):
                    st.error(f"Closure failed: {close_res.get('message')}")
                else:
                    st.success(f"Position {pos['symbol']} closed successfully!")
                    st.rerun()

    st.divider()

    # 1% Risk Position Sizing & Virtual Order Placement
    st.markdown("#### **Virtual Order Placement & 1% Equity Risk Calculator**")
    st.caption("Positions are sized strictly so maximum loss at stop-loss does not exceed 1% of total virtual equity.")

    with st.form("virtual_buy_form"):
        f_col1, f_col2, f_col3 = st.columns(3)
        order_sym = f_col1.selectbox("Order Symbol", options=universe_symbols, index=universe_symbols.index(selected_symbol) if selected_symbol in universe_symbols else 0)
        order_price = f_col2.number_input("Entry Price (INR)", value=float(latest_snap.get("close_price") or 2500.0), min_value=1.0, step=0.05)
        # Default stop-loss 2% below
        default_sl = round(order_price * 0.98, 2)
        order_sl = f_col3.number_input("Protective Stop-Loss (INR)", value=default_sl, min_value=0.5, step=0.05)

        f_col4, f_col5 = st.columns(2)
        default_tp = round(order_price + 2.0 * (order_price - order_sl), 2)
        order_tp = f_col4.number_input("Take-Profit Target (INR - Min 2:1 R:R)", value=default_tp, min_value=order_price, step=0.05)
        manual_qty = f_col5.number_input("Quantity (Leave 0 for automatic 1% Risk Sizing)", value=0, min_value=0, step=1)

        bypass_hours = st.checkbox("Bypass market session hours (Simulate outside 09:15-15:30 IST)", value=True)

        # Preview Size Calculation
        risk_per_sh = max(0.01, order_price - order_sl)
        budget_1pct = equity_val * 0.01
        est_qty = int(budget_1pct // risk_per_sh) if manual_qty == 0 else manual_qty
        est_cap = est_qty * order_price
        st.caption(f"Estimated Position Size: **{est_qty} shares** • Capital Required: **₹{est_cap:,.2f}** • Maximum Risk at Stop: **₹{est_qty * risk_per_sh:,.2f}** ({est_qty * risk_per_sh / equity_val * 100:.2f}% equity)")

        submitted = st.form_submit_button("🚀 Submit Virtual Paper Order", use_container_width=True)
        if submitted:
            with st.spinner("Validating risk constraints and routing virtual paper order..."):
                buy_res = api_client.place_buy_order(
                    symbol=order_sym,
                    price=order_price,
                    stop_loss_price=order_sl,
                    take_profit_price=order_tp,
                    quantity=None if manual_qty == 0 else manual_qty,
                    enforce_market_hours=not bypass_hours,
                    reason="Dashboard Virtual Entry",
                )

            if buy_res.get("error"):
                st.error(f"Order Placement Rejected: {buy_res.get('message')}")
            else:
                st.success(f"Order FILLED! Bought {buy_res.get('quantity')} shares of {buy_res.get('symbol')} @ ₹{buy_res.get('executed_price')}. Order ID: {buy_res.get('order_id')}")
                st.rerun()


# ==============================================================================
# TAB 4: Trade Ledger & Performance Analytics
# ==============================================================================
with tab_ledger:
    st.markdown("### **Trade Ledger & Performance Analytics**")

    metrics_data = api_client.get_metrics()
    orders_data = api_client.get_orders(limit=50)

    # KPI Summary Cards
    m_c1, m_c2, m_c3, m_c4, m_c5, m_c6 = st.columns(6)
    m_c1.metric("Win Rate", f"{metrics_data.get('win_rate_pct', 0.0):.1f}%", f"{metrics_data.get('winning_trades', 0)}W / {metrics_data.get('losing_trades', 0)}L")
    m_c2.metric("Profit Factor", f"{metrics_data.get('profit_factor', 0.0):.2f}")
    m_c3.metric("Net Realized P&L", f"₹{metrics_data.get('total_net_realized_pnl_inr', 0.0):+,.2f}")
    m_c4.metric("Charges Paid", f"₹{metrics_data.get('total_charges_paid_inr', 0.0):,.2f}")
    m_c5.metric("Max Drawdown", f"{metrics_data.get('max_drawdown_pct', 0.0):.2f}%", f"-₹{metrics_data.get('max_drawdown_inr', 0.0):,.2f}")
    m_c6.metric("Sharpe Ratio", f"{metrics_data.get('sharpe_ratio') or 'N/A'}")

    st.divider()

    # Portfolio Equity Curve Plotly Chart
    if orders_data:
        eq_curve = [float(portfolio.get("initial_capital_inr", 100000.0)), float(equity_val)]
        timestamps_eq = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        eq_fig = create_equity_curve_chart(["Start", "Current"], eq_curve, initial_capital=float(portfolio.get("initial_capital_inr", 100000.0)))
        if eq_fig:
            st.plotly_chart(eq_fig, use_container_width=True)

    # Order History Table
    st.markdown("#### **Executed Virtual Orders Audit Trail**")
    if not orders_data:
        st.info("No orders executed yet in this session.")
    else:
        st.dataframe(
            orders_data,
            use_container_width=True,
            column_config={
                "client_order_id": "Order ID",
                "symbol": "Symbol",
                "side": "Side",
                "quantity": "Qty",
                "executed_price": st.column_config.NumberColumn("Fill Price (INR)", format="₹%.2f"),
                "turnover_inr": st.column_config.NumberColumn("Turnover (INR)", format="₹%.2f"),
                "total_charges_inr": st.column_config.NumberColumn("Charges (INR)", format="₹%.2f"),
                "net_cash_impact_inr": st.column_config.NumberColumn("Net Cash (INR)", format="₹%.2f"),
                "executed_at": "Execution Time",
                "reason": "Reason",
            },
        )


# ==============================================================================
# TAB 5: System Health & Freshness
# ==============================================================================
with tab_health:
    st.markdown("### **System Infrastructure, Market Calendar & Compliance**")

    h_col1, h_col2 = st.columns(2)

    with h_col1:
        st.markdown("#### **Backend Service & Database Probes**")
        db_health = health_ready.get("database", {})
        st.write(f"- **FastAPI Backend Liveness:** {'🟢 ONLINE' if not health_ready.get('error') else '🔴 OFFLINE'}")
        st.write(f"- **PostgreSQL Readiness:** {'🟢 CONNECTED' if db_health.get('connected') else '🔴 DISCONNECTED'}")
        st.write(f"- **Database Query Roundtrip Latency:** `{db_health.get('latency_ms', 0)} ms`")
        st.write(f"- **Real Order Execution Safeguard:** `LOCKED (Paper Trading Mode)`")
        st.write(f"- **Emergency Kill Switch:** `{'ACTIVE (HALTED)' if kill_switch_active else 'STANDBY (NORMAL)'}`")

    with h_col2:
        st.markdown("#### **NSE Exchange Rules & Calendar**")
        st.write("- **Primary Exchange:** National Stock Exchange of India (NSE)")
        st.write("- **Regular Trading Session:** 09:15 to 15:30 IST (Monday - Friday)")
        st.write("- **Standard Equity Tick Size:** ₹0.05")
        st.write("- **Standard Cash Lot Size:** 1 share")
        st.write("- **Market Data Provider:** Yahoo Finance (Delayed 15-minutes, historical prototyping only)")

    st.divider()

    st.markdown("#### **Active Universe Coverage (Top 10 NSE Equities)**")
    st.dataframe(
        universe,
        use_container_width=True,
        column_config={
            "symbol": "Symbol",
            "company_name": "Company Name",
            "sector": "Sector",
            "exchange": "Exchange",
            "tick_size": st.column_config.NumberColumn("Tick Size", format="₹%.2f"),
            "lot_size": "Lot Size",
            "currency": "Currency",
        },
    )
