"""
Tab 4: Positions & Virtual Execution Portal for Quantum Trader.
Manages active open paper positions, position closing, and 1% risk-budgeted
virtual order execution with automated or manual sizing and real-time R:R preview.
"""

from decimal import Decimal
from typing import Any, Dict

try:
    import streamlit as st
except ImportError:
    st = None

from trading.risk import calculate_position_size, calculate_rr_preview
from trading.charges import calculate_trade_friction, calculate_us_trade_friction
from dashboard.styles import pnl_pill, badge


def render_tab(
    api_client: Any,
    state: Dict[str, Any],
    market: str,
    symbol: str,
    timeframe: str,
) -> None:
    """
    Renders Tab 4: Positions & Virtual Execution.
    """
    active_market = market or state.get("active_market", "NSE")
    active_currency = state.get("active_currency", "INR")
    curr_sym = state.get("curr_sym", "₹")
    is_us_market = state.get("is_us_market", False)
    portfolio = state.get("portfolio", {})
    if not isinstance(portfolio, dict):
        portfolio = {}

    default_cap = float(state.get("default_cap", 100000.0) or 100000.0)
    equity_val = float(portfolio.get("equity_inr", state.get("equity_val", default_cap)) or default_cap)
    cash_val = float(portfolio.get("cash_balance_inr", equity_val) or equity_val)
    universe_symbols = state.get("universe_symbols", [symbol])

    st.markdown(f"### **Virtual Portfolio Exposure & Position Management ({active_currency})**")

    # Open Positions List for Active Currency
    open_positions = api_client.get_positions(status_filter="OPEN", currency=active_currency)
    if not isinstance(open_positions, list):
        open_positions = []

    if not open_positions:
        st.info(
            f"No active virtual {active_currency} swing positions currently open. "
            "Use the order execution portal below to enter trades."
        )
    else:
        pos_hdr_c1, pos_hdr_c2 = st.columns([4, 1])
        pos_hdr_c1.markdown(f"#### **Active Open Positions ({len(open_positions)} / 5 Max)**")
        with pos_hdr_c2:
            if st.button("🔄 Refresh Quotes", use_container_width=True, key="btn_refresh_positions_quotes"):
                st.rerun()

        for pos in open_positions:
            p_col1, p_col2, p_col3, p_col4, p_col5, p_col6 = st.columns([2, 2, 2, 2, 2, 2])
            pnl = float(pos.get("unrealized_pnl_inr", 0.0) or 0.0)
            entry_p = float(pos.get("entry_price", 1.0) or 1.0)
            curr_p = float(pos.get("current_price", 1.0) or 1.0)
            ret_pct = ((curr_p - entry_p) / entry_p) * 100.0 if entry_p else 0.0

            p_col1.markdown(f"**{pos.get('symbol')}** ({pos.get('quantity')} shs • {pos.get('exchange', 'NSE')})")
            p_col2.metric("Entry", f"{curr_sym}{entry_p:,.2f}")
            p_col3.metric("Current", f"{curr_sym}{curr_p:,.2f}")
            p_col4.metric("Unrealized P&L", f"{curr_sym}{pnl:+,.2f}", delta=f"{ret_pct:+.2f}%")
            sl_val = pos.get("stop_loss_price") or 0.0
            tp_val = pos.get("take_profit_price") or 0.0
            p_col5.markdown(
                f"**SL:** {curr_sym}{float(sl_val):,.2f}<br>**TP:** {curr_sym}{float(tp_val):,.2f}",
                unsafe_allow_html=True,
            )

            pos_id = pos.get("id")
            if p_col6.button("Close Position", key=f"close_{pos_id}", type="primary"):
                close_res = api_client.close_position(pos_id, exit_price=pos.get("current_price"))
                if close_res and close_res.get("error"):
                    st.error(f"Closure failed: {close_res.get('message')}")
                else:
                    st.success(f"Position {pos.get('symbol')} closed successfully!")
                    st.rerun()

    st.divider()

    # 1% Risk Position Sizing & Virtual Order Placement
    st.markdown(f"#### **Virtual Order Placement & 1% Risk Calculator ({active_currency})**")
    st.caption("Positions are sized strictly so maximum loss at stop-loss does not exceed 1% of total virtual equity.")

    # Safely resolve latest_close from state or fallback
    latest_snap = state.get("latest_snapshot")
    if not latest_snap:
        try:
            ind = api_client.get_indicators(symbol, timeframe)
            if ind and not ind.get("error"):
                latest_snap = ind.get("latest_snapshot", {})
        except Exception:
            latest_snap = {}
    if not isinstance(latest_snap, dict):
        latest_snap = {}

    fallback_price = 200.0 if is_us_market else 2500.0
    latest_close = float(latest_snap.get("close_price") or fallback_price)
    tick_step = 0.01 if is_us_market else 0.05

    # REACTIVE CONTAINER (Not inside st.form, ensuring immediate updates on parameter changes)
    with st.container():
        f_col1, f_col2, f_col3 = st.columns(3)
        order_sym = f_col1.selectbox(
            "Order Symbol",
            options=universe_symbols,
            index=universe_symbols.index(symbol) if symbol in universe_symbols else 0,
            key="pos_order_sym_sel",
        )
        order_price = f_col2.number_input(
            f"Entry Price ({active_currency})",
            value=latest_close,
            min_value=0.1,
            step=tick_step,
            key="pos_order_price_input",
        )
        default_sl = round(order_price * 0.98, 2)
        order_sl = f_col3.number_input(
            f"Protective Stop-Loss ({active_currency})",
            value=default_sl,
            min_value=0.05,
            step=tick_step,
            key="pos_order_sl_input",
        )

        f_col4, f_col5 = st.columns(2)
        default_tp = round(order_price + 2.0 * max(0.01, order_price - order_sl), 2)
        order_tp = f_col4.number_input(
            f"Take-Profit Target ({active_currency} - Min 2:1 R:R)",
            value=default_tp,
            min_value=order_price,
            step=tick_step,
            key="pos_order_tp_input",
        )
        manual_qty = f_col5.number_input(
            "Quantity (Leave 0 for automatic 1% Risk Sizing)",
            value=0,
            min_value=0,
            step=1,
            key="pos_order_qty_input",
        )

        bypass_session_label = (
            "Bypass market session hours (Simulate outside 09:30-16:00 ET)"
            if is_us_market
            else "Bypass market session hours (Simulate outside 09:15-15:30 IST)"
        )
        bypass_hours = st.checkbox(bypass_session_label, value=True, key="pos_bypass_hours_chk")

        # Dynamic 1% Risk Sizing & R:R Preview
        sizing_res = calculate_position_size(
            equity=Decimal(str(round(equity_val, 2))),
            available_cash=Decimal(str(round(cash_val, 2))),
            entry_price=Decimal(str(round(order_price, 2))),
            stop_loss_price=Decimal(str(round(order_sl, 2))),
            max_risk_pct=0.01,
            max_allocation_pct=0.20,
        )

        rr_res = calculate_rr_preview(
            entry=order_price,
            stop_loss=order_sl,
            take_profit=order_tp,
        )

        rec_qty = sizing_res.quantity
        effective_qty = manual_qty if manual_qty > 0 else rec_qty
        effective_cap = effective_qty * order_price
        risk_per_sh = max(0.0, order_price - order_sl)
        effective_risk = effective_qty * risk_per_sh
        risk_pct_equity = (effective_risk / equity_val * 100.0) if equity_val > 0 else 0.0

        # R:R Preview Badge
        if rr_res["is_valid"]:
            badge_html = f"""
            <div style="background-color: rgba(14, 19, 31, 0.85); border: 1px solid rgba(30, 38, 56, 0.9); border-radius: 8px; padding: 12px 16px; margin: 10px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #8F9CAE; font-weight: 600;">Risk : Reward Assessment</span>
                        <div style="font-size: 20px; font-weight: 700; color: #F8FAFC; margin-top: 2px;">
                            {rr_res['rr_ratio']:.2f} : 1
                            <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; background-color: {rr_res['status_color']}20; color: {rr_res['status_color']}; border: 1px solid {rr_res['status_color']}; margin-left: 8px;">
                                {rr_res['tier']}
                            </span>
                        </div>
                    </div>
                    <div style="text-align: right; font-size: 12px; color: #8F9CAE;">
                        <div>Risk/sh: <b style="color: #FF3366;">{curr_sym}{rr_res['risk_per_share']:.2f}</b> (-{rr_res['stop_loss_pct']:.2f}%)</div>
                        <div>Reward/sh: <b style="color: #00E676;">{curr_sym}{rr_res['reward_per_share']:.2f}</b> (+{rr_res['take_profit_pct']:.2f}%)</div>
                    </div>
                </div>
            </div>
            """
            st.markdown(badge_html, unsafe_allow_html=True)
        else:
            st.markdown(
                f"""
                <div style="background-color: rgba(255, 51, 102, 0.1); border: 1px solid #FF3366; border-radius: 6px; padding: 10px 14px; margin: 8px 0; color: #FF3366; font-size: 13px;">
                    ⚠️ <b>Invalid R:R Parameters:</b> {rr_res.get('reason')}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Sizing Metric Cards
        s_c1, s_c2, s_c3, s_c4 = st.columns(4)
        s_c1.metric(
            "Suggested Quantity",
            f"{rec_qty} shares",
            delta="1% Risk Bound" if rec_qty > 0 else "Blocked",
        )
        s_c2.metric(
            "Effective Order Size",
            f"{effective_qty} shares",
            delta="Manual Override" if manual_qty > 0 else "Auto Sized",
        )
        s_c3.metric(
            "Capital Required",
            f"{curr_sym}{effective_cap:,.2f}",
            delta=f"{(effective_cap / equity_val * 100):.1f}% equity" if equity_val > 0 else "0%",
        )
        s_c4.metric(
            "Max Risk at Stop",
            f"{curr_sym}{effective_risk:,.2f}",
            delta=f"{risk_pct_equity:.2f}% equity",
            delta_color="inverse" if risk_pct_equity > 1.05 else "normal",
        )

        if manual_qty > 0 and risk_pct_equity > 1.05:
            st.warning(
                f"⚠️ Warning: Manual quantity of {manual_qty} shares incurs {risk_pct_equity:.2f}% equity risk at stop-loss, "
                "exceeding the institutional 1.0% risk budget."
            )

        # Regulatory Taxes & Friction Breakdown
        if effective_qty > 0:
            try:
                if is_us_market:
                    fric = calculate_us_trade_friction(
                        symbol=order_sym,
                        side="BUY",
                        quantity=effective_qty,
                        price=Decimal(str(round(order_price, 2))),
                    )
                    tax_html = f"""
                    <div style="background-color: rgba(14, 19, 31, 0.6); border: 1px solid rgba(30, 38, 56, 0.7); border-radius: 6px; padding: 10px 14px; margin: 8px 0; font-size: 12px; color: #8F9CAE;">
                        <b style="color: #F8FAFC;">US Regulatory Estimates (Entry Buy):</b>
                        Brokerage: <b style="color: #00E676;">${float(fric.brokerage_inr):.2f}</b> • 
                        Slippage (5 bps): <b>${float(fric.slippage_impact_inr):.2f}</b> • 
                        Total Charges: <b style="color: #FF9900;">${float(fric.total_charges_inr):.2f}</b> • 
                        Net Cash Impact: <b style="color: #00F2FE;">${float(fric.net_cash_impact_inr):,.2f}</b><br>
                        <span style="font-size: 11px; color: #64748B;">*SEC Section 31 (0.0000278) &amp; FINRA TAF ($0.000166/sh) apply strictly on SELL exit orders.</span>
                    </div>
                    """
                else:
                    fric = calculate_trade_friction(
                        symbol=order_sym,
                        side="BUY",
                        quantity=effective_qty,
                        price=Decimal(str(round(order_price, 2))),
                    )
                    tax_html = f"""
                    <div style="background-color: rgba(14, 19, 31, 0.6); border: 1px solid rgba(30, 38, 56, 0.7); border-radius: 6px; padding: 10px 14px; margin: 8px 0; font-size: 12px; color: #8F9CAE;">
                        <b style="color: #F8FAFC;">Indian Statutory Friction Breakdown (NSE Buy):</b>
                        Brokerage: <b>₹{float(fric.brokerage_inr):.2f}</b> • 
                        STT (0.1%): <b>₹{float(fric.stt_tax_inr):.2f}</b> • 
                        Exchange + SEBI: <b>₹{float(fric.exchange_turnover_inr + fric.sebi_charges_inr):.2f}</b> • 
                        GST (18%): <b>₹{float(fric.gst_inr):.2f}</b> • 
                        Stamp Duty (0.015%): <b>₹{float(fric.stamp_duty_inr):.2f}</b> • 
                        Slippage (5 bps): <b>₹{float(fric.slippage_impact_inr):.2f}</b> • 
                        Total Charges: <b style="color: #FF9900;">₹{float(fric.total_charges_inr):.2f}</b> • 
                        Net Cash Impact: <b style="color: #00F2FE;">₹{float(fric.net_cash_impact_inr):,.2f}</b>
                    </div>
                    """
                st.markdown(tax_html, unsafe_allow_html=True)
            except ValueError:
                fee_desc = (
                    "US Regulatory Charges: Zero Brokerage ($0.00), SEC Section 31 Fee on sell (0.0000278), FINRA TAF ($0.000166/sh), 5 bps slippage."
                    if is_us_market
                    else "Indian Regulatory Charges: Flat ₹20 Brokerage, 0.1% STT on turnover, GST 18%, Stamp Duty 0.015%, 5 bps slippage."
                )
                st.caption(f"ℹ️ {fee_desc}")
        else:
            fee_desc = (
                "US Regulatory Charges: Zero Brokerage ($0.00), SEC Section 31 Fee on sell (0.0000278), FINRA TAF ($0.000166/sh), 5 bps slippage."
                if is_us_market
                else "Indian Regulatory Charges: Flat ₹20 Brokerage, 0.1% STT on turnover, GST 18%, Stamp Duty 0.015%, 5 bps slippage."
            )
            st.caption(f"ℹ️ {fee_desc}")

        submitted = st.button("🚀 Submit Virtual Paper Order", type="primary", use_container_width=True, key="btn_submit_order")
        if submitted:
            if not rr_res.get("is_valid", False):
                st.error(f"Cannot submit order: {rr_res.get('reason')}")
            else:
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

                if buy_res and buy_res.get("error"):
                    st.error(f"Order Placement Rejected: {buy_res.get('message')}")
                elif buy_res:
                    st.success(
                        f"Order FILLED! Bought {buy_res.get('quantity')} shares of {buy_res.get('symbol')} "
                        f"@ {curr_sym}{buy_res.get('executed_price')}. Order ID: {buy_res.get('order_id')}"
                    )
                    st.rerun()
