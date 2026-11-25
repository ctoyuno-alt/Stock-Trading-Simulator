"""
Gauges and Visual Risk Indicators for Quantum Trader Dashboard.

Provides:
1. Radial Confluence Score Gauge (0-100 score, SVG/HTML & Plotly visualizer).
2. Risk/Reward Ratio visualizer bar and validation preview.
3. Classification helpers (score to tier, degrees mapping).
4. Deterministic 4-factor confluence calculation helper.
"""

import math
from typing import Any, Dict, Optional

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


def get_confluence_tier(score: float) -> Dict[str, Any]:
    """
    Validates score-to-tier color mapping across all ranges.
    Matches test_confluence_tier_classification.
    """
    try:
        score_val = float(score if score is not None else 0.0)
        if math.isnan(score_val):
            score_val = 0.0
    except (ValueError, TypeError):
        score_val = 0.0

    clamped = max(0.0, min(100.0, score_val))
    if clamped >= 85.0:
        return {
            "tier": "Institutional Strong Buy",
            "color": "#00F2FE",
            "status": "CYAN",
            "bg": "rgba(0, 242, 254, 0.12)",
            "border": "rgba(0, 242, 254, 0.28)",
        }
    elif clamped >= 70.0:
        return {
            "tier": "Qualified Buy Signal",
            "color": "#00E676",
            "status": "GREEN",
            "bg": "rgba(0, 230, 118, 0.12)",
            "border": "rgba(0, 230, 118, 0.28)",
        }
    elif clamped >= 50.0:
        return {
            "tier": "Neutral / Developing",
            "color": "#FF9900",
            "status": "AMBER",
            "bg": "rgba(255, 153, 0, 0.12)",
            "border": "rgba(255, 153, 0, 0.28)",
        }
    else:
        return {
            "tier": "Unfavorable / Bearish",
            "color": "#FF3366",
            "status": "CRIMSON",
            "bg": "rgba(255, 51, 102, 0.12)",
            "border": "rgba(255, 51, 102, 0.28)",
        }


def score_to_gauge_degrees(score: float) -> float:
    """
    Converts confluence score [0, 100] to 180-degree semi-circle gauge rotation.
    Matches test_gauge_radial_degree_mapping.
    """
    try:
        score_val = float(score if score is not None else 0.0)
        if math.isnan(score_val):
            score_val = 0.0
    except (ValueError, TypeError):
        score_val = 0.0

    clamped = max(0.0, min(100.0, score_val))
    return round((clamped / 100.0) * 180.0, 1)


def calculate_rr_preview(entry: float, stop_loss: float, take_profit: float) -> Dict[str, Any]:
    """
    Calculates Risk:Reward ratio and validation status for UI preview.
    Matches test_dashboard_calculations.TestRiskRewardRatioCalculations.
    """
    try:
        e = float(entry)
        sl = float(stop_loss)
        tp = float(take_profit)
    except (ValueError, TypeError):
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Invalid numerical parameters."}

    if math.isnan(e) or math.isnan(sl) or math.isnan(tp) or math.isinf(e) or math.isinf(sl) or math.isinf(tp):
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Parameters cannot be NaN or infinite."}
    if e <= 0:
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Entry price must be positive."}
    if sl >= e:
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Stop-loss must be strictly below entry price."}
    if tp <= e:
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Take-profit must be strictly above entry price."}

    risk_per_sh = e - sl
    reward_per_sh = tp - e
    rr_ratio = reward_per_sh / risk_per_sh if risk_per_sh > 0 else 0.0
    sl_pct = (risk_per_sh / e) * 100.0
    tp_pct = (reward_per_sh / e) * 100.0

    if rr_ratio >= 2.0:
        tier = "OPTIMAL"
        status_color = "#00E676"
    elif rr_ratio >= 1.5:
        tier = "SUBOPTIMAL"
        status_color = "#FF9900"
    else:
        tier = "REJECTED"
        status_color = "#FF3366"

    return {
        "is_valid": True,
        "rr_ratio": round(rr_ratio, 2),
        "risk_per_share": round(risk_per_sh, 2),
        "reward_per_share": round(reward_per_sh, 2),
        "stop_loss_pct": round(sl_pct, 2),
        "take_profit_pct": round(tp_pct, 2),
        "tier": tier,
        "status_color": status_color,
    }


def calculate_deterministic_confluence(
    close: float,
    ema_20: float,
    ema_50: float,
    rsi_14: float,
    macd_hist: float,
    prev_macd_hist: Optional[float],
    vwap: float,
) -> float:
    """
    Computes deterministic 4-factor technical confluence score (0.0 to 100.0).
    Matches TestDeterministicConfluenceScoring.
    """
    score = 0.0

    # 1. Trend Alignment (30%)
    if ema_20 > ema_50:
        if close >= ema_20:
            score += 30.0
        else:
            score += 15.0
    else:
        score += 0.0

    # 2. Momentum / RSI 14 (25%)
    if 48.0 <= rsi_14 <= 65.0:
        score += 25.0
    elif 40.0 <= rsi_14 < 48.0:
        score += 12.0
    elif rsi_14 > 70.0:
        score += 5.0
    elif rsi_14 < 35.0:
        score += 0.0
    else:
        score += 10.0

    # 3. MACD (25%)
    if macd_hist > 0:
        if prev_macd_hist is not None and macd_hist > prev_macd_hist:
            score += 25.0
        else:
            score += 15.0
    else:
        score += 0.0

    # 4. VWAP Fair Value (20%)
    if close >= vwap:
        score += 20.0
    else:
        score += 0.0

    return max(0.0, min(100.0, score))


def render_radial_gauge(
    score: float,
    title: str = "Confluence Score",
    subtitle: str = "",
    use_plotly: bool = False,
) -> None:
    """
    Renders high-performance radial semi-circle gauge.
    Uses ultra-fast inline SVG by default (<1ms render, zero layout shift).
    """
    if st is None:
        return

    try:
        score_val = float(score if score is not None else 0.0)
        if math.isnan(score_val):
            score_val = 0.0
    except (ValueError, TypeError):
        score_val = 0.0

    clamped_score = max(0.0, min(100.0, score_val))
    tier_info = get_confluence_tier(clamped_score)

    if use_plotly and HAS_PLOTLY:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=clamped_score,
                number={"suffix": "/100", "font": {"family": "JetBrains Mono", "size": 26, "color": "#F8FAFC"}},
                title={"text": title, "font": {"family": "Inter", "size": 14, "color": "#8F9CAE"}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#1E2638"},
                    "bar": {"color": tier_info["color"], "thickness": 0.28},
                    "bgcolor": "#0E131F",
                    "borderwidth": 1,
                    "bordercolor": "#1E2638",
                    "steps": [
                        {"range": [0, 50], "color": "rgba(255, 51, 102, 0.1)"},
                        {"range": [50, 70], "color": "rgba(255, 153, 0, 0.1)"},
                        {"range": [70, 85], "color": "rgba(0, 230, 118, 0.1)"},
                        {"range": [85, 100], "color": "rgba(0, 242, 254, 0.1)"},
                    ],
                },
            )
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=200,
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
        return

    # SVG Semi-circle Radial Gauge
    # Radius = 85, Arc length = pi * 85 = 267.04
    r = 85
    arc_length = math.pi * r
    stroke_offset = arc_length * (1.0 - clamped_score / 100.0)

    subtitle_html = f'<div style="font-size:11px; color:#8F9CAE; margin-top:2px;">{subtitle}</div>' if subtitle else ""

    svg_html = f"""
    <div style="background:#0E131F; border:1px solid #1E2638; border-radius:8px; padding:16px; text-align:center; box-shadow:0 4px 16px rgba(0,0,0,0.25); margin-bottom:14px;">
        <div style="font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; color:#8F9CAE;">{title}</div>
        {subtitle_html}
        <div style="margin: 10px auto 0 auto; width: 260px; height: 130px; position: relative;">
            <svg viewBox="0 0 260 135" width="260" height="135" style="overflow: visible;">
                <!-- Background track -->
                <path d="M 45 115 A 85 85 0 0 1 215 115"
                      fill="none" stroke="#1E2638" stroke-width="12" stroke-linecap="round"/>
                <!-- Colored progress arc -->
                <path d="M 45 115 A 85 85 0 0 1 215 115"
                      fill="none" stroke="{tier_info['color']}" stroke-width="12" stroke-linecap="round"
                      stroke-dasharray="{arc_length:.2f}" stroke-dashoffset="{stroke_offset:.2f}"
                      style="filter: drop-shadow(0 0 6px {tier_info['color']}66); transition: stroke-dashoffset 0.6s ease-in-out;"/>
                <!-- Score Text -->
                <text x="130" y="95" text-anchor="middle"
                      font-family="'JetBrains Mono', monospace" font-size="32" font-weight="700" fill="#F8FAFC">
                    {clamped_score:.1f}
                </text>
                <text x="130" y="112" text-anchor="middle"
                      font-family="'JetBrains Mono', monospace" font-size="11" font-weight="600" fill="#8F9CAE">
                    OUT OF 100
                </text>
            </svg>
        </div>
        <div style="margin-top: 6px;">
            <span class="status-pill" style="background:{tier_info['bg']}; color:{tier_info['color']}; border:1px solid {tier_info['border']}; padding:4px 12px; font-size:11.5px; border-radius:9999px; font-family:'JetBrains Mono', monospace;">
                {tier_info['tier']}
            </span>
        </div>
    </div>
    """
    st.markdown(svg_html, unsafe_allow_html=True)


def render_risk_reward_gauge(
    entry: float,
    target: float,
    stop_loss: float,
    curr_sym: str = "₹",
    currency: Optional[str] = None,
) -> None:
    """
    Renders institutional Risk:Reward visualizer bar and parameter limits.
    """
    if st is None:
        return

    if currency is not None:
        curr_sym = currency

    preview = calculate_rr_preview(entry, stop_loss, target)
    if not preview["is_valid"]:
        st.markdown(
            f"""
            <div style="background:#0E131F; border:1px solid rgba(255, 51, 102, 0.3); border-radius:8px; padding:12px 16px; margin-bottom:14px;">
                <span class="status-pill pill-bearish" style="background:rgba(255,51,102,0.12); color:#FF3366; border:1px solid rgba(255,51,102,0.25); padding:2px 8px; border-radius:4px; font-size:11px; font-family:'JetBrains Mono', monospace;">INVALID R:R CONFIGURATION</span>
                <span style="font-size:12px; color:#8F9CAE; margin-left:8px;">{preview.get('reason')}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    rr_ratio = preview["rr_ratio"]
    tier = preview["tier"]
    status_color = preview["status_color"]
    risk_sh = preview["risk_per_share"]
    reward_sh = preview["reward_per_share"]
    sl_pct = preview["stop_loss_pct"]
    tp_pct = preview["take_profit_pct"]

    # Proportional width: Risk / (Risk + Reward)
    total_spread = risk_sh + reward_sh
    risk_pct_width = (risk_sh / total_spread) * 100.0 if total_spread > 0 else 33.3
    reward_pct_width = 100.0 - risk_pct_width

    html = f"""
    <div style="background:#0E131F; border:1px solid #1E2638; border-radius:8px; padding:14px 16px; box-shadow:0 4px 16px rgba(0,0,0,0.25); margin-bottom:14px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <div style="font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; color:#8F9CAE;">
                Risk / Reward Ratio
            </div>
            <span class="status-pill" style="background:{status_color}22; color:{status_color}; border:1px solid {status_color}55; padding:2px 10px; border-radius:9999px; font-size:11.5px; font-family:'JetBrains Mono', monospace; font-weight:600;">
                {rr_ratio:.2f}:1 • {tier}
            </span>
        </div>

        <!-- Proportional R:R Bar -->
        <div style="height:10px; width:100%; border-radius:5px; background:#1E2638; overflow:hidden; display:flex;">
            <div style="width:{risk_pct_width:.1f}%; background:#FF3366; transition:width 0.4s ease;" title="Risk: -{curr_sym}{risk_sh:,.2f} (-{sl_pct:.2f}%)"></div>
            <div style="width:3px; background:#F8FAFC;"></div>
            <div style="width:{reward_pct_width:.1f}%; background:#00E676; transition:width 0.4s ease;" title="Reward: +{curr_sym}{reward_sh:,.2f} (+{tp_pct:.2f}%)"></div>
        </div>

        <!-- Key Levels Grid -->
        <div style="display:flex; justify-content:space-between; margin-top:10px; font-family:'JetBrains Mono', monospace; font-size:11.5px;">
            <div>
                <span style="color:#FF3366;">Stop Loss</span>: {curr_sym}{stop_loss:,.2f}
                <div style="font-size:10px; color:#8F9CAE;">-{sl_pct:.2f}% (-{curr_sym}{risk_sh:,.2f}/sh)</div>
            </div>
            <div style="text-align:center;">
                <span style="color:#F8FAFC;">Entry</span>: {curr_sym}{entry:,.2f}
                <div style="font-size:10px; color:#8F9CAE;">Execution Basis</div>
            </div>
            <div style="text-align:right;">
                <span style="color:#00E676;">Take Profit</span>: {curr_sym}{target:,.2f}
                <div style="font-size:10px; color:#8F9CAE;">+{tp_pct:.2f}% (+{curr_sym}{reward_sh:,.2f}/sh)</div>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
