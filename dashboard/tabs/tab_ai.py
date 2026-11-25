"""
Tab 2: AI & Deterministic Strategy Signals for Quantum Trader.
Renders deterministic rule-based quantitative signals, radial confluence gauge,
and Google Gemini LLM grounded multi-factor market interpretation.
"""

import math
from typing import Any, Dict, Optional

try:
    import streamlit as st
except ImportError:
    st = None

from dashboard.components.gauges import (
    get_confluence_tier,
    render_radial_gauge,
    render_risk_reward_gauge,
)


def render_tab(
    api_client: Any,
    state: Dict[str, Any],
    market: str,
    symbol: str,
    timeframe: str,
) -> None:
    """
    Renders Tab 2: AI Confluence Analysis.
    Uniform interface contract adhering to dashboard/app.py.
    """
    active_market = market or state.get("active_market", "NSE")
    active_currency = state.get("active_currency", "INR")
    curr_sym = state.get("curr_sym", "₹")
    safe_symbol = str(symbol or ("AAPL" if active_market == "US" else "RELIANCE"))
    safe_timeframe = str(timeframe or "1d")

    st.markdown(f"### **Strategy Signals & Gemini AI Confluence Analysis: {safe_symbol}**")
    st.caption(
        f"Multi-factor institutional quantitative strategy synthesis • Market: {active_market} ({active_currency}) • Timeframe: {safe_timeframe}"
    )

    col_ai_left, col_ai_right = st.columns([1, 1])

    # =========================================================================
    # LEFT COLUMN: Deterministic Strategy Engine (Python)
    # =========================================================================
    with col_ai_left:
        st.markdown("#### **Deterministic Strategy Engine (Python)**")
        with st.spinner("Evaluating multi-factor swing trading rules..."):
            signal_data = api_client.get_signal(safe_symbol, timeframe=safe_timeframe) if api_client else {}

        if isinstance(signal_data, dict) and signal_data.get("error"):
            st.warning(f"Could not load strategy signal: {signal_data.get('message')}")
        elif not signal_data:
            st.info(f"No strategy signal currently available for {safe_symbol}.")
        else:
            action = signal_data.get("action", "HOLD")
            strength = signal_data.get("strength", "MODERATE")
            technical_score = float(signal_data.get("technical_score") or 0.0)
            primary_trigger = signal_data.get("primary_trigger", "Multi-Factor Technical Evaluation")

            action_color = "#00E676" if action == "BUY" else ("#FF3366" if action == "SELL" else "#94A3B8")
            action_bg = "rgba(0, 230, 118, 0.12)" if action == "BUY" else ("rgba(255, 51, 102, 0.12)" if action == "SELL" else "rgba(148, 163, 184, 0.12)")
            action_border = "rgba(0, 230, 118, 0.28)" if action == "BUY" else ("rgba(255, 51, 102, 0.28)" if action == "SELL" else "rgba(148, 163, 184, 0.28)")

            # Strategy Signal Banner
            st.markdown(
                f"""
                <div style="background-color: #0E131F; padding: 14px 18px; border-radius: 8px;
                            border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid {action_color};
                            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25); margin-bottom: 14px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-family:'JetBrains Mono', monospace; font-size:16px; font-weight:700; color:{action_color};">
                            {action} ({strength})
                        </span>
                        <span class="status-pill" style="background:{action_bg}; color:{action_color}; border:1px solid {action_border}; padding:2px 8px; font-size:11px; border-radius:4px; font-family:'JetBrains Mono', monospace;">
                            RULE EVALUATED
                        </span>
                    </div>
                    <div style="font-size: 12.5px; color: #8F9CAE; margin-top: 6px;">
                        {primary_trigger}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 1. Radial Confluence Score Gauge
            render_radial_gauge(
                score=technical_score,
                title="Technical Confluence Score",
                subtitle=f"{safe_symbol} • {safe_timeframe.upper()} Factor Weighting",
            )

            # 2. Risk / Reward Visualizer
            entry_price = float(signal_data.get("entry_price") or 0.0)
            stop_loss = float(signal_data.get("suggested_stop_loss") or 0.0)
            take_profit = float(signal_data.get("suggested_take_profit") or 0.0)

            if entry_price > 0 and stop_loss > 0 and take_profit > 0 and stop_loss < entry_price < take_profit:
                render_risk_reward_gauge(
                    entry=entry_price,
                    target=take_profit,
                    stop_loss=stop_loss,
                    curr_sym=curr_sym,
                )
            else:
                # Fallback metrics if values don't satisfy bracket hierarchy
                st.markdown("##### **Quantitative Target & Risk Limits:**")
                t_col1, t_col2, t_col3 = st.columns(3)
                t_col1.metric("Entry Benchmark", f"{curr_sym}{entry_price:,.2f}" if entry_price > 0 else "—")
                t_col2.metric(
                    "Stop Loss",
                    f"{curr_sym}{stop_loss:,.2f}" if stop_loss > 0 else "—",
                    delta=f"-{signal_data.get('stop_loss_pct', 0):.2f}%" if signal_data.get("stop_loss_pct") else None,
                )
                t_col3.metric(
                    "Take Profit",
                    f"{curr_sym}{take_profit:,.2f}" if take_profit > 0 else "—",
                    delta=f"+{signal_data.get('target_profit_pct', 0):.2f}%" if signal_data.get("target_profit_pct") else None,
                )

            # 3. 4-Factor Deterministic Breakdown
            latest_snap = state.get("latest_snapshot", {})
            if latest_snap:
                st.markdown("##### **4-Factor Technical Indicator Matrix:**")
                f_c1, f_c2 = st.columns(2)
                with f_c1:
                    ema_20 = latest_snap.get("ema_fast_20")
                    ema_50 = latest_snap.get("ema_slow_50")
                    trend_status = "BULLISH" if (ema_20 and ema_50 and ema_20 > ema_50) else "BEARISH / NEUTRAL"
                    trend_color = "#00E676" if trend_status == "BULLISH" else "#FF3366"
                    st.markdown(
                        f"""
                        <div style="background:#0E131F; border:1px solid #1E2638; border-radius:6px; padding:10px; margin-bottom:8px;">
                            <div style="font-size:10px; font-weight:600; text-transform:uppercase; color:#8F9CAE;">1. Trend Alignment (30%)</div>
                            <div style="font-family:'JetBrains Mono', monospace; font-size:12px; font-weight:700; color:{trend_color}; margin-top:2px;">
                                {trend_status}
                            </div>
                            <div style="font-size:10.5px; color:#6B7280;">EMA 20 vs EMA 50</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    macd_hist = latest_snap.get("macd_histogram")
                    macd_status = "POSITIVE" if (macd_hist and macd_hist > 0) else "NEGATIVE / FLAT"
                    macd_color = "#00E676" if macd_status == "POSITIVE" else "#FF3366"
                    macd_val_str = f"{macd_hist:+.3f}" if macd_hist is not None else "—"
                    st.markdown(
                        f"""
                        <div style="background:#0E131F; border:1px solid #1E2638; border-radius:6px; padding:10px;">
                            <div style="font-size:10px; font-weight:600; text-transform:uppercase; color:#8F9CAE;">3. MACD Trajectory (25%)</div>
                            <div style="font-family:'JetBrains Mono', monospace; font-size:12px; font-weight:700; color:{macd_color}; margin-top:2px;">
                                {macd_status} ({macd_val_str})
                            </div>
                            <div style="font-size:10.5px; color:#6B7280;">Signal Crossover Dynamics</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with f_c2:
                    rsi_14 = latest_snap.get("rsi_14")
                    rsi_regime = latest_snap.get("rsi_regime") or "Neutral"
                    rsi_color = "#00E676" if (rsi_14 and 48 <= rsi_14 <= 65) else "#FF9900"
                    rsi_val_str = f"{rsi_14:.1f}" if rsi_14 is not None else "—"
                    st.markdown(
                        f"""
                        <div style="background:#0E131F; border:1px solid #1E2638; border-radius:6px; padding:10px; margin-bottom:8px;">
                            <div style="font-size:10px; font-weight:600; text-transform:uppercase; color:#8F9CAE;">2. Momentum Corridor (25%)</div>
                            <div style="font-family:'JetBrains Mono', monospace; font-size:12px; font-weight:700; color:{rsi_color}; margin-top:2px;">
                                RSI: {rsi_val_str} ({rsi_regime})
                            </div>
                            <div style="font-size:10.5px; color:#6B7280;">48-65 Optimal Corridor</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    vwap = latest_snap.get("vwap")
                    close_p = latest_snap.get("close_price")
                    vwap_status = "ABOVE VWAP" if (close_p and vwap and close_p >= vwap) else "BELOW VWAP"
                    vwap_color = "#00E676" if vwap_status == "ABOVE VWAP" else "#FF3366"
                    st.markdown(
                        f"""
                        <div style="background:#0E131F; border:1px solid #1E2638; border-radius:6px; padding:10px;">
                            <div style="font-size:10px; font-weight:600; text-transform:uppercase; color:#8F9CAE;">4. VWAP Institutional Value (20%)</div>
                            <div style="font-family:'JetBrains Mono', monospace; font-size:12px; font-weight:700; color:{vwap_color}; margin-top:2px;">
                                {vwap_status}
                            </div>
                            <div style="font-size:10.5px; color:#6B7280;">Fair Value Benchmark</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            # Confirming & Conflicting Factors
            confirming = signal_data.get("confirming_factors", [])
            if confirming:
                st.markdown("##### **Confirming Factors:**")
                for c in confirming:
                    st.markdown(f"- ✅ <span style='color:#00E676;'>{c}</span>", unsafe_allow_html=True)

            conflicting = signal_data.get("conflicting_factors", [])
            if conflicting:
                st.markdown("##### **Conflicting Factors / Warning Signs:**")
                for cf in conflicting:
                    st.markdown(f"- ⚠️ <span style='color:#FF3366;'>{cf}</span>", unsafe_allow_html=True)

    # =========================================================================
    # RIGHT COLUMN: Google Gemini AI Quantitative Interpretation
    # =========================================================================
    with col_ai_right:
        st.markdown("#### **Google Gemini AI Quantitative Interpretation**")

        # DEFECT GUARDRAIL: Only execute when explicitly requested by user button click or session flag
        cache_key = f"ai_analysis_{safe_symbol}_{safe_timeframe}"
        trigger_requested = False
        if st.button("⚡ Generate AI Market Interpretation", type="secondary", use_container_width=True, key="btn_trigger_ai"):
            trigger_requested = True
            if hasattr(st, "session_state") and isinstance(st.session_state, dict):
                st.session_state["trigger_ai"] = True

        session_dict = st.session_state if hasattr(st, "session_state") and isinstance(st.session_state, dict) else {}
        should_run_ai = (session_dict.get("trigger_ai") is True) or trigger_requested

        if should_run_ai and api_client:
            with st.spinner("Synthesizing grounded technical interpretation via Gemini..."):
                ai_resp = api_client.get_ai_analysis(safe_symbol, timeframe=safe_timeframe)
            if hasattr(st, "session_state") and isinstance(st.session_state, dict):
                st.session_state[cache_key] = ai_resp
                st.session_state["trigger_ai"] = False
        else:
            ai_resp = session_dict.get(cache_key)

        # AI Response Display
        if ai_resp is None:
            # Standby Card
            st.markdown(
                """
                <div style="background:#0E131F; border:1px solid #1E2638; border-radius:8px; padding:24px 20px; text-align:center; box-shadow:0 4px 16px rgba(0,0,0,0.25); margin-top:12px;">
                    <div style="font-size:28px; margin-bottom:10px;">🤖</div>
                    <div style="font-size:14px; font-weight:600; color:#F8FAFC; margin-bottom:6px;">Gemini AI Interpretation Standby</div>
                    <div style="font-size:12px; color:#8F9CAE; max-width:420px; margin:0 auto 16px auto; line-height:1.5;">
                        Click <strong>"Generate AI Market Interpretation"</strong> above to synthesize grounded, multi-factor technical analysis powered by Google Gemini.
                    </div>
                    <div style="font-size:11px; color:#6B7280; font-family:'JetBrains Mono', monospace;">
                        Parameters: Grounded Technical Snapshots • Zero Hallucination Guardrails
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif isinstance(ai_resp, dict) and ai_resp.get("error"):
            st.warning(f"AI service response: {ai_resp.get('message')}")
        elif isinstance(ai_resp, dict):
            ai_data = (ai_resp.get("ai_analysis") or {}) if isinstance(ai_resp, dict) else {}
            if not isinstance(ai_data, dict):
                ai_data = {}
            stance = ai_data.get("recommended_action_opinion", "FAVORS_PATIENCE")
            try:
                conf_val = float(ai_data.get("ai_confidence_score") or 0.0)
                if math.isnan(conf_val):
                    conf_val = 0.0
            except (ValueError, TypeError):
                conf_val = 0.0
            confidence = conf_val
            confidence_rationale = ai_data.get("ai_confidence_rationale", "")

            # Stance badge styling
            if "ACCUMULATION" in stance or stance == "BUY":
                stance_color = "#00E676"
                stance_bg = "rgba(0, 230, 118, 0.12)"
                stance_border = "rgba(0, 230, 118, 0.28)"
            elif "PROFIT_TAKING" in stance or stance == "SELL":
                stance_color = "#FF3366"
                stance_bg = "rgba(255, 51, 102, 0.12)"
                stance_border = "rgba(255, 51, 102, 0.28)"
            else:
                stance_color = "#FF9900"
                stance_bg = "rgba(255, 153, 0, 0.12)"
                stance_border = "rgba(255, 153, 0, 0.28)"

            # Stance and Confidence Card
            st.markdown(
                f"""
                <div style="background-color: #0E131F; padding: 14px 18px; border-radius: 8px;
                            border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid {stance_color};
                            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25); margin-bottom: 14px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-family:'JetBrains Mono', monospace; font-size:15px; font-weight:700; color:{stance_color};">
                            AI Stance: {stance}
                        </span>
                        <span class="status-pill" style="background:{stance_bg}; color:{stance_color}; border:1px solid {stance_border}; padding:2px 8px; font-size:11px; border-radius:4px; font-family:'JetBrains Mono', monospace;">
                            CONFIDENCE: {confidence:.1f}/100
                        </span>
                    </div>
                    <div style="font-size: 12px; color: #8F9CAE; margin-top: 6px;">
                        <strong>Rationale:</strong> {confidence_rationale}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 4 Accordions for Grounded Interpretation
            with st.expander("📈 Trend & Moving Averages Interpretation", expanded=True):
                st.write(ai_data.get("trend_analysis", "N/A"))

            with st.expander("⚡ Momentum & RSI 14 Analysis", expanded=True):
                st.write(ai_data.get("momentum_analysis", "N/A"))

            with st.expander("🌊 MACD & Institutional VWAP Assessment", expanded=False):
                st.write(f"**MACD:** {ai_data.get('macd_interpretation', 'N/A')}")
                st.write(f"**VWAP:** {ai_data.get('vwap_relationship', 'N/A')}")

            with st.expander("⚠️ Key Identified Market Risks", expanded=False):
                risks = ai_data.get("key_risks", [])
                if isinstance(risks, list) and risks:
                    for rk in risks:
                        st.markdown(f"- {rk}")
                else:
                    st.write("No elevated market risks flagged.")

            # Mandatory Ethical Notice / Disclaimer
            disclaimer = (
                ai_data.get("disclaimer")
                or "Algorithmic and AI signals are synthesized for paper trading simulation and educational purposes only. Past performance does not guarantee future results."
            )
            st.warning(f"**ETHICAL NOTICE:** {disclaimer}")
