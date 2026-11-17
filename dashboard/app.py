"""
Gemini-Powered AI Paper Trading Simulator (NSE & US Markets) - Streamlit Dashboard.

Features:
1. Dual-Market Trading Support: Indian Equities (NSE/BSE in INR) & US Mega-Caps (NYSE/NASDAQ in USD).
2. Portfolio balance, purchasing power, and equity curve in native currency (₹ or $).
3. Active watchlists of 10 liquid NSE equities and 10 liquid US mega-caps.
4. Interactive Plotly charts (Candlestick, EMA 20/50, VWAP, Volume, RSI, MACD).
5. Grounded Gemini AI analysis, technical signal explanations, and non-hallucinatory confidence ratings.
6. Open virtual positions with real-time unrealized P&L and one-click manual closure.
7. Chronological trade order ledger with market-specific regulatory frictions (STT/GST vs SEC/FINRA).
8. Realized P&L, Unrealized P&L, Win Rate, Profit Factor, Max Drawdown, Sharpe Ratio.
9. 1% Equity Risk Position Sizing calculator and virtual execution portal.
10. Dual-Market session awareness (IST for NSE, ET for US).
"""

import sys
from pathlib import Path
from datetime import datetime
import streamlit as st

# Ensure application root (/app or workspace root) is in Python sys.path
_APP_ROOT = str(Path(__file__).resolve().parent.parent)
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from dashboard.api_client import api_client
from dashboard.components.charts import (
    create_candlestick_with_indicators,
    create_equity_curve_chart,
    create_rsi_chart,
)
from dashboard.components.tradingview import render_tradingview_chart

# Page configuration
st.set_page_config(
    page_title="AI Paper Trading Simulator (NSE & US)",
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
    .badge-buy { background-color: #1B5E20; color: #A5D6A7; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .badge-sell-sl { background-color: #B71C1C; color: #FFCDD2; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .badge-sell-tp { background-color: #004D40; color: #80CBC4; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .badge-sell-rev { background-color: #E65100; color: #FFE0B2; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    .metric-card { background-color: #1E1E1E; border-radius: 8px; padding: 12px; border: 1px solid #333333; }
</style>
""", unsafe_allow_html=True)


# --- Fetch Global System Status ---
system_status = api_client.get_system_status()
health_ready = api_client.get_health_ready()
kill_switch_active = system_status.get("safety_guardrails", {}).get("kill_switch_active", False)


# --- Sidebar Controls & Metrics ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bullish.png", width=64)
    st.markdown("### **AI Paper Trading Station**")
    st.caption("Institutional Quantitative Research • Multi-Market")

    # 1. Market Selection Toggle
    market_choice = st.radio(
        "Active Market / Exchange",
        ["🇮🇳 India (NSE) - INR (₹)", "🇺🇸 US (NYSE/NASDAQ) - USD ($)"],
        index=0,
    )
    is_us_market = "US" in market_choice
    active_market = "US" if is_us_market else "IN"
    active_currency = "USD" if is_us_market else "INR"
    curr_sym = "$" if is_us_market else "₹"

    # Session Status Badge
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

    if is_open:
        st.markdown(f'<span class="badge-open">● {badge_text}</span> <span class="badge-paper">VIRTUAL</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="badge-closed">● {badge_text}</span> <span class="badge-paper">VIRTUAL</span>', unsafe_allow_html=True)
    st.caption(clock_label)

    st.divider()

    # Fetch Universe and Portfolio for the active market
    universe = api_client.get_universe(market=active_market)
    universe_symbols = [inst["symbol"] for inst in universe] or (
        ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V"]
        if is_us_market
        else ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "SBIN", "ITC", "LT", "TATAMOTORS"]
    )

    portfolio = api_client.get_portfolio(currency=active_currency)

    # Instrument & Timeframe Selectors
    selected_symbol = st.selectbox("Select Instrument (Universe)", options=universe_symbols, index=0)
    timeframe = st.selectbox("Timeframe", options=["1d", "1h", "15m"], index=0)

    # Live Monitoring & Auto-Refresh Controls
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
        auto_trade_on_refresh = st.checkbox("🤖 Auto-Trade Cycle on Refresh", value=False)
        st.caption(f"⚡ Live polling active ({refresh_rate}s interval)")

    st.divider()

    # Portfolio Quick Snapshot
    st.markdown(f"#### **Portfolio Snapshot ({active_currency})**")
    default_cap = 25000.0 if is_us_market else 100000.0
    equity_val = portfolio.get("equity_inr", default_cap)
    cash_val = portfolio.get("cash_balance_inr", default_cap)
    open_count = portfolio.get("open_positions_count", 0)
    total_pnl = portfolio.get("total_pnl_inr", 0.0)

    col_s1, col_s2 = st.columns(2)
    col_s1.metric("Equity", f"{curr_sym}{equity_val:,.2f}")
    col_s2.metric("Cash", f"{curr_sym}{cash_val:,.2f}")
    st.metric("Total P&L", f"{curr_sym}{total_pnl:+,.2f}", delta=f"{portfolio.get('return_on_initial_capital_pct', 0.0):+.2f}%")
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
market_header_text = "US Equities (NYSE/NASDAQ)" if is_us_market else "Indian Equities (NSE/BSE)"
st.markdown(
    f'<div class="main-header">📈 Gemini-Powered AI Paper Trading Simulator — {market_header_text}</div>'
    f'<div class="sub-caption">Institutional Quantitative Research • Strictly Virtual Funds ({active_currency}) • Broker Independent</div>',
    unsafe_allow_html=True,
)


# --- Dashboard Tabs ---
tab_market, tab_ai, tab_autotrader, tab_positions, tab_ledger, tab_backtest, tab_health = st.tabs([
    "📊 Market & Technicals",
    "🧠 AI Confluence Analysis",
    "🤖 Autonomous AI Auto-Trader",
    "💼 Positions & Execution",
    "📜 Trade Ledger & Performance",
    "🧪 Historical Backtest",
    "🛡️ System Health & Freshness",
])


# ==============================================================================
# TAB 1: Market & Technical Indicators
# ==============================================================================
with tab_market:
    m_top_col1, m_top_col2 = st.columns([4, 1])
    with m_top_col1:
        st.markdown(f"### **{selected_symbol} — Live Market & Technical Indicators**")
        st.caption(f"Data source: TradingView & Yahoo Finance • {active_market} Market ({active_currency}) • Timeframe: {timeframe} • Polling interval: {refresh_rate if auto_refresh else 'Manual'}s")
    with m_top_col2:
        if st.button("🔄 Refresh Quote Now", use_container_width=True):
            st.rerun()

    chart_engine = st.radio(
        "Chart Engine View",
        [
            "📈 TradingView Interactive Pro Chart (Live Canvas - All Stocks)",
            "🌐 TradingView Advanced Widget (US Stocks & Web View)",
            "📊 Quantitative Multi-Panel (Plotly Indicators)",
        ],
        horizontal=True,
        index=0,
    )

    # Smart lookback period based on selected timeframe
    default_period = "5d" if timeframe == "15m" else ("1mo" if timeframe == "1h" else "6mo")

    with st.spinner(f"Loading market data and quantitative indicators for {selected_symbol}..."):
        candles_data = api_client.get_candles(selected_symbol, timeframe=timeframe, period=default_period)
        indicators_data = api_client.get_indicators(selected_symbol, timeframe=timeframe)

    if candles_data.get("error"):
        st.warning(f"Note on historical candles: {candles_data.get('message')}")

    # Latest Snapshot KPIs
    latest_snap = indicators_data.get("latest_snapshot", {})
    if latest_snap:
        kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5, kpi_c6 = st.columns(6)
        kpi_c1.metric("Close", f"{curr_sym}{latest_snap.get('close_price', 0):,.2f}")
        kpi_c2.metric("EMA 20", f"{curr_sym}{latest_snap.get('ema_fast_20') or 0:,.2f}")
        kpi_c3.metric("EMA 50", f"{curr_sym}{latest_snap.get('ema_slow_50') or 0:,.2f}", delta=f"{latest_snap.get('ema_spread_pct') or 0:+.2f}%")
        kpi_c4.metric("RSI 14", f"{latest_snap.get('rsi_14') or 0:.1f}", delta=latest_snap.get("rsi_regime"))
        kpi_c5.metric("MACD Hist", f"{latest_snap.get('macd_histogram') or 0:+.3f}", delta=latest_snap.get("macd_state"))
        kpi_c6.metric("VWAP", f"{curr_sym}{latest_snap.get('vwap') or 0:,.2f}", delta=f"{latest_snap.get('price_to_vwap_pct') or 0:+.2f}%")

    if "Canvas" in chart_engine or "All Stocks" in chart_engine:
        st.caption(f"⚡ Interactive TradingView Canvas Chart for {selected_symbol} ({timeframe.upper()}) with volume histogram, EMA 20 (Cyan), EMA 50 (Orange) and live crosshair legend.")
        render_tradingview_chart(
            selected_symbol,
            timeframe=timeframe,
            height=640,
            candles_data=candles_data,
            indicators_data=indicators_data,
            use_embed_widget=False,
        )
    elif "Advanced Widget" in chart_engine:
        st.caption("⚡ TradingView Advanced Widget with drawing tools, Fibonacci retracements & institutional dark theme.")
        render_tradingview_chart(
            selected_symbol,
            timeframe=timeframe,
            height=680,
            use_embed_widget=True,
        )
    else:
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
            t_col1.metric("Entry Benchmark", f"{curr_sym}{signal_data.get('entry_price', 0):,.2f}")
            t_col2.metric("Stop Loss", f"{curr_sym}{signal_data.get('suggested_stop_loss', 0):,.2f}", delta=f"-{signal_data.get('stop_loss_pct', 0):.2f}%")
            t_col3.metric("Take Profit", f"{curr_sym}{signal_data.get('suggested_take_profit', 0):,.2f}", delta=f"+{signal_data.get('target_profit_pct', 0):.2f}%")

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
# TAB 3: Autonomous AI Auto-Trader
# ==============================================================================
with tab_autotrader:
    st.markdown(f"### **🤖 Autonomous AI Auto-Trading Engine ({active_market} Market — {active_currency})**")
    st.caption("Fully automated, hands-free order execution and position management powered by quantitative strategy confluence and Google Gemini AI.")

    # Fetch Auto-Trader Status from Backend
    bot_status = api_client.get_auto_trader_status()
    bot_cfg = bot_status.get("config", {})
    last_cycle = bot_status.get("last_cycle_at") or "Never"
    is_bot_enabled = bot_cfg.get("enabled", False)

    # Top KPI Banner
    stat_c1, stat_c2, stat_c3, stat_c4 = st.columns(4)
    stat_c1.metric("Bot Status", "🟢 ACTIVE" if is_bot_enabled else "⏸️ STANDBY")
    stat_c2.metric("Min Confluence", f"{bot_cfg.get('min_confluence_score', 70)}/100")
    stat_c3.metric("AI Gate", "🔒 REQUIRED" if bot_cfg.get("require_ai_approval", True) else "🔓 BYPASSED")
    stat_c4.metric("Last Evaluation", last_cycle.split(".")[0] if "." in last_cycle else last_cycle)

    st.divider()

    # Bot Master Switch & Settings
    col_ctrl_left, col_ctrl_right = st.columns([1, 1])

    with col_ctrl_left:
        st.markdown("#### **Execution Controls & Master Switch**")
        new_enabled = st.toggle("Enable Autonomous Auto-Trading", value=is_bot_enabled, key="bot_master_toggle")
        if new_enabled != is_bot_enabled:
            api_client.update_auto_trader_config({"enabled": new_enabled})
            st.rerun()

        if is_bot_enabled:
            st.success("🤖 AI Auto-Trader is **ACTIVE**. Orders will trigger automatically when high-confluence signals are detected.")
        else:
            st.info("⏸️ AI Auto-Trader is on **STANDBY**. You can run a single cycle manually using the button below.")

        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("⚡ Run AI Auto-Trade Cycle Now", type="primary", use_container_width=True):
                with st.spinner(f"Scanning {active_market} universe, verifying AI gates, and managing positions..."):
                    tick_res = api_client.run_auto_trader_tick(market=active_market, timeframe=timeframe)
                if tick_res.get("error"):
                    st.error(f"Auto-Trader cycle failed: {tick_res.get('message')}")
                else:
                    cycle = tick_res.get("cycle_result", {})
                    n_exec = cycle.get("orders_executed_count", 0)
                    n_closed = cycle.get("positions_closed_count", 0)
                    st.success(f"Cycle completed! Executed: {n_exec} orders | Closed: {n_closed} positions.")
                    st.rerun()
        with col_act2:
            if st.button("🗑️ Clear Decision Log", use_container_width=True):
                api_client.clear_auto_trader_history()
                st.rerun()

    with col_ctrl_right:
        st.markdown("#### **Risk & Strategy Parameters**")
        with st.form("auto_trader_config_form"):
            new_score = st.slider("Minimum Confluence Score Threshold", min_value=50, max_value=95, value=bot_cfg.get("min_confluence_score", 70), step=5)
            new_ai_gate = st.checkbox("Require Gemini AI Confirmation Gate", value=bot_cfg.get("require_ai_approval", True))
            new_rev_exit = st.checkbox("Auto-Exit Position on Strategy Reversal to SELL", value=bot_cfg.get("auto_exit_on_reversal", True))
            new_enforce_hours = st.checkbox("Enforce Strict Exchange Session Hours", value=bot_cfg.get("enforce_market_hours", False))
            new_max_pos = st.number_input("Maximum Concurrent Open Positions", min_value=1, max_value=10, value=bot_cfg.get("max_open_positions", 5))

            save_cfg = st.form_submit_button("💾 Save Auto-Trader Settings", use_container_width=True)
            if save_cfg:
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

    # Live Activity & Decision Audit Feed
    st.markdown("#### **Real-Time AI Decision Feed & Audit Trail**")
    decisions = bot_status.get("recent_decisions", [])
    if not decisions:
        st.info("No decisions logged yet. Click 'Run AI Auto-Trade Cycle Now' above to begin autonomous scanning.")
    else:
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


# ==============================================================================
# TAB 4: Positions & Execution Portal
# ==============================================================================
with tab_positions:
    st.markdown(f"### **Virtual Portfolio Exposure & Position Management ({active_currency})**")

    # Open Positions List for Active Currency
    open_positions = api_client.get_positions(status_filter="OPEN", currency=active_currency)

    if not open_positions:
        st.info(f"No active virtual {active_currency} swing positions currently open. Use the order execution portal below to enter trades.")
    else:
        st.markdown(f"#### **Active Open Positions ({len(open_positions)} / 5 Max)**")
        for pos in open_positions:
            p_col1, p_col2, p_col3, p_col4, p_col5, p_col6 = st.columns([2, 2, 2, 2, 2, 2])
            pnl = pos.get("unrealized_pnl_inr", 0.0)

            p_col1.markdown(f"**{pos['symbol']}** ({pos['quantity']} shs • {pos.get('exchange', 'NSE')})")
            p_col2.metric("Entry", f"{curr_sym}{pos['entry_price']:,.2f}")
            p_col3.metric("Current", f"{curr_sym}{pos['current_price']:,.2f}")
            p_col4.metric("Unrealized P&L", f"{curr_sym}{pnl:+,.2f}")
            p_col5.markdown(f"**SL:** {curr_sym}{pos['stop_loss_price']:,.2f}<br>**TP:** {curr_sym}{pos.get('take_profit_price') or 0:,.2f}", unsafe_allow_html=True)

            if p_col6.button("Close Position", key=f"close_{pos['id']}", type="primary"):
                close_res = api_client.close_position(pos["id"], exit_price=pos["current_price"])
                if close_res.get("error"):
                    st.error(f"Closure failed: {close_res.get('message')}")
                else:
                    st.success(f"Position {pos['symbol']} closed successfully!")
                    st.rerun()

    st.divider()

    # 1% Risk Position Sizing & Virtual Order Placement
    st.markdown(f"#### **Virtual Order Placement & 1% Risk Calculator ({active_currency})**")
    st.caption("Positions are sized strictly so maximum loss at stop-loss does not exceed 1% of total virtual equity.")

    latest_close = float(latest_snap.get("close_price") or (200.0 if is_us_market else 2500.0))
    tick_step = 0.01 if is_us_market else 0.05

    with st.form("virtual_buy_form"):
        f_col1, f_col2, f_col3 = st.columns(3)
        order_sym = f_col1.selectbox("Order Symbol", options=universe_symbols, index=universe_symbols.index(selected_symbol) if selected_symbol in universe_symbols else 0)
        order_price = f_col2.number_input(f"Entry Price ({active_currency})", value=latest_close, min_value=0.1, step=tick_step)
        default_sl = round(order_price * 0.98, 2)
        order_sl = f_col3.number_input(f"Protective Stop-Loss ({active_currency})", value=default_sl, min_value=0.05, step=tick_step)

        f_col4, f_col5 = st.columns(2)
        default_tp = round(order_price + 2.0 * (order_price - order_sl), 2)
        order_tp = f_col4.number_input(f"Take-Profit Target ({active_currency} - Min 2:1 R:R)", value=default_tp, min_value=order_price, step=tick_step)
        manual_qty = f_col5.number_input("Quantity (Leave 0 for automatic 1% Risk Sizing)", value=0, min_value=0, step=1)

        bypass_session_label = (
            "Bypass market session hours (Simulate outside 09:30-16:00 ET)"
            if is_us_market
            else "Bypass market session hours (Simulate outside 09:15-15:30 IST)"
        )
        bypass_hours = st.checkbox(bypass_session_label, value=True)

        # Preview Size Calculation
        risk_per_sh = max(0.01, order_price - order_sl)
        budget_1pct = equity_val * 0.01
        est_qty = int(budget_1pct // risk_per_sh) if manual_qty == 0 else manual_qty
        est_cap = est_qty * order_price
        st.caption(f"Estimated Position Size: **{est_qty} shares** • Capital Required: **{curr_sym}{est_cap:,.2f}** • Max Risk at Stop: **{curr_sym}{est_qty * risk_per_sh:,.2f}** ({est_qty * risk_per_sh / equity_val * 100:.2f}% equity)")

        fee_desc = (
            "US Regulatory Charges: Zero Brokerage ($0.00), SEC Section 31 Fee on sell (0.0000278), FINRA TAF ($0.000166/sh), 5 bps slippage."
            if is_us_market
            else "Indian Regulatory Charges: Flat ₹20 Brokerage, 0.1% STT on turnover, GST 18%, Stamp Duty 0.015%, 5 bps slippage."
        )
        st.caption(f"ℹ️ {fee_desc}")

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
                    reason=f"Dashboard Virtual Entry ({active_market})",
                )

            if buy_res.get("error"):
                st.error(f"Order Placement Rejected: {buy_res.get('message')}")
            else:
                st.success(f"Order FILLED! Bought {buy_res.get('quantity')} shares of {buy_res.get('symbol')} @ {curr_sym}{buy_res.get('executed_price')}. Order ID: {buy_res.get('order_id')}")
                st.rerun()


# ==============================================================================
# TAB 4: Trade Ledger & Performance Analytics
# ==============================================================================
with tab_ledger:
    st.markdown(f"### **Trade Ledger & Performance Analytics ({active_currency})**")

    metrics_data = api_client.get_metrics(currency=active_currency)
    orders_data = api_client.get_orders(limit=50, currency=active_currency)

    # KPI Summary Cards
    m_c1, m_c2, m_c3, m_c4, m_c5, m_c6 = st.columns(6)
    m_c1.metric("Win Rate", f"{metrics_data.get('win_rate_pct', 0.0):.1f}%", f"{metrics_data.get('winning_trades', 0)}W / {metrics_data.get('losing_trades', 0)}L")
    m_c2.metric("Profit Factor", f"{metrics_data.get('profit_factor', 0.0):.2f}")
    m_c3.metric("Net Realized P&L", f"{curr_sym}{metrics_data.get('total_net_realized_pnl_inr', 0.0):+,.2f}")
    m_c4.metric("Charges Paid", f"{curr_sym}{metrics_data.get('total_charges_paid_inr', 0.0):,.2f}")
    m_c5.metric("Max Drawdown", f"{metrics_data.get('max_drawdown_pct', 0.0):.2f}%", f"-{curr_sym}{metrics_data.get('max_drawdown_inr', 0.0):,.2f}")
    m_c6.metric("Sharpe Ratio", f"{metrics_data.get('sharpe_ratio') or 'N/A'}")

    st.divider()

    # Portfolio Equity Curve Plotly Chart
    if orders_data:
        eq_curve = [float(portfolio.get("initial_capital_inr", default_cap)), float(equity_val)]
        eq_fig = create_equity_curve_chart(["Start", "Current"], eq_curve, initial_capital=float(portfolio.get("initial_capital_inr", default_cap)))
        if eq_fig:
            st.plotly_chart(eq_fig, use_container_width=True)

    # Order History Table
    st.markdown(f"#### **Executed Virtual Orders Audit Trail ({active_currency})**")
    if not orders_data:
        st.info(f"No {active_currency} orders executed yet in this session.")
    else:
        st.dataframe(
            orders_data,
            use_container_width=True,
            column_config={
                "client_order_id": "Order ID",
                "symbol": "Symbol",
                "side": "Side",
                "quantity": "Qty",
                "executed_price": st.column_config.NumberColumn(f"Fill Price ({active_currency})", format=f"{curr_sym}%.2f"),
                "turnover_inr": st.column_config.NumberColumn(f"Turnover ({active_currency})", format=f"{curr_sym}%.2f"),
                "total_charges_inr": st.column_config.NumberColumn(f"Charges ({active_currency})", format=f"{curr_sym}%.2f"),
                "net_cash_impact_inr": st.column_config.NumberColumn(f"Net Cash ({active_currency})", format=f"{curr_sym}%.2f"),
                "executed_at": "Execution Time",
                "reason": "Reason",
            },
        )


# ==============================================================================
# TAB 5: Historical Backtesting Engine
# ==============================================================================
with tab_backtest:
    st.markdown(f"### **Walk-Forward Historical Strategy Backtesting ({active_currency})**")
    backtest_caption = (
        "Walk-forward simulation with zero look-ahead bias, accounting for US zero-commission trading, SEC/FINRA exit charges, and 5 bps adverse slippage."
        if is_us_market
        else "Walk-forward simulation with zero look-ahead bias, accounting for Indian delivery frictions (STT, Brokerage, GST, Stamp Duty) and 5 bps adverse slippage."
    )
    st.caption(backtest_caption)

    with st.form("backtest_form"):
        bt_c1, bt_c2, bt_c3, bt_c4 = st.columns(4)
        bt_symbol = bt_c1.selectbox("Backtest Instrument", options=universe_symbols, index=universe_symbols.index(selected_symbol) if selected_symbol in universe_symbols else 0)
        bt_period = bt_c2.selectbox("Lookback Window", options=["6mo", "1y", "2y"], index=1)
        bt_capital = bt_c3.number_input(f"Starting Capital ({active_currency})", value=default_cap, step=5000.0 if is_us_market else 10000.0)
        bt_risk = bt_c4.number_input("Risk Per Trade (Fraction)", value=0.01, min_value=0.005, max_value=0.05, step=0.005, format="%.3f")

        bt_submit = st.form_submit_button("▶️ Run Quantitative Backtest", use_container_width=True)

    if bt_submit or st.session_state.get(f"bt_done_{selected_symbol}"):
        with st.spinner(f"Executing bar-by-bar simulation for {bt_symbol} ({bt_period})..."):
            bt_res = api_client.run_backtest(
                symbol=bt_symbol,
                timeframe="1d",
                period=bt_period,
                initial_capital_inr=bt_capital,
                max_risk_per_trade=bt_risk,
                slippage_bps=5.0,
            )

        if bt_res.get("error"):
            st.error(f"Backtest execution failed: {bt_res.get('message')}")
        else:
            st.session_state[f"bt_done_{selected_symbol}"] = True
            metrics = bt_res.get("metrics", {})
            st.markdown(f"#### **Backtest Results: {bt_res.get('symbol')} ({bt_res.get('total_bars')} bars, {bt_res.get('strategy_name')})**")

            res_c1, res_c2, res_c3, res_c4, res_c5, res_c6 = st.columns(6)
            res_c1.metric("Total Return", f"{bt_res.get('total_return_pct'):+.2f}%", f"{curr_sym}{bt_res.get('total_net_profit_inr'):+,.2f}")
            res_c2.metric("Win Rate", f"{metrics.get('win_rate_pct', 0.0):.1f}%", f"{metrics.get('winning_trades', 0)}W / {metrics.get('losing_trades', 0)}L")
            res_c3.metric("Profit Factor", f"{metrics.get('profit_factor', 0.0):.2f}")
            res_c4.metric("Friction Paid", f"{curr_sym}{metrics.get('total_charges_paid_inr', 0.0):,.2f}")
            res_c5.metric("Max Drawdown", f"{metrics.get('max_drawdown_pct', 0.0):.2f}%", f"-{curr_sym}{metrics.get('max_drawdown_inr', 0.0):,.2f}")
            res_c6.metric("Sharpe Ratio", f"{metrics.get('sharpe_ratio') or 'N/A'}")

            # Plot Equity Curve from backtest
            eq_curve_raw = bt_res.get("equity_curve", [])
            if eq_curve_raw:
                eq_ts = [pt["timestamp"] for pt in eq_curve_raw]
                eq_vals = [pt["equity"] for pt in eq_curve_raw]
                bt_fig = create_equity_curve_chart(eq_ts, eq_vals, initial_capital=bt_capital)
                if bt_fig:
                    st.plotly_chart(bt_fig, use_container_width=True)

            # Trades Table
            trades_list = bt_res.get("trades", [])
            st.markdown(f"##### **Closed Trades Log ({len(trades_list)} Total Trades)**")
            if not trades_list:
                st.info("No trades triggered under strict strategy confluence rules during this window.")
            else:
                st.dataframe(
                    trades_list,
                    use_container_width=True,
                    column_config={
                        "trade_id": "#",
                        "symbol": "Symbol",
                        "side": "Side",
                        "quantity": "Qty",
                        "entry_price": st.column_config.NumberColumn(f"Entry ({active_currency})", format=f"{curr_sym}%.2f"),
                        "exit_price": st.column_config.NumberColumn(f"Exit ({active_currency})", format=f"{curr_sym}%.2f"),
                        "exit_reason": "Exit Reason",
                        "net_pnl_inr": st.column_config.NumberColumn(f"Net P&L ({active_currency})", format=f"{curr_sym}%.2f"),
                        "total_charges_inr": st.column_config.NumberColumn(f"Charges ({active_currency})", format=f"{curr_sym}%.2f"),
                        "return_pct": st.column_config.NumberColumn("Return %", format="%.2f%%"),
                        "holding_period_bars": "Holding Bars",
                        "entry_time": "Entry Date",
                        "exit_time": "Exit Date",
                    },
                )


# ==============================================================================
# TAB 6: System Health & Freshness
# ==============================================================================
with tab_health:
    st.markdown("### **System Infrastructure, Multi-Market Calendars & Compliance**")

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
        st.markdown("#### **Multi-Market Trading Sessions & Calendar Rules**")
        st.write("- **🇮🇳 India (NSE):** 09:15 to 15:30 IST • Tick: ₹0.05 • STT + GST + Stamp Duty")
        st.write("- **🇺🇸 United States (NYSE/NASDAQ):** 09:30 to 16:00 ET • Tick: $0.01 • Zero Brokerage + SEC/FINRA")
        st.write("- **Market Data Provider:** Yahoo Finance (Delayed quotes for research)")
        st.write(f"- **Active Virtual Currency:** `{active_currency}` ({curr_sym})")

    st.divider()

    st.markdown(f"#### **Active Universe Coverage ({active_market} Market - Top 10 Equities)**")
    st.dataframe(
        universe,
        use_container_width=True,
        column_config={
            "symbol": "Symbol",
            "company_name": "Company Name",
            "sector": "Sector",
            "exchange": "Exchange",
            "tick_size": st.column_config.NumberColumn(f"Tick Size ({active_currency})", format=f"{curr_sym}%.2f"),
            "lot_size": "Lot Size",
            "currency": "Currency",
            "market": "Market",
        },
    )


# --- Background Live Polling & Autonomous Trading Loop ---
if auto_refresh:
    import time
    if auto_trade_on_refresh and not kill_switch_active:
        api_client.run_auto_trader_tick(market=active_market, timeframe=timeframe)
    time.sleep(refresh_rate)
    st.rerun()
