"""
Institutional Design System & CSS Styling for Quantum Trader.
Bloomberg Terminal / TradingView / Linear Dark Aesthetic.
"""

from typing import Optional

try:
    import streamlit as st
except ImportError:
    st = None

_original_st = st

# --- Design Tokens ---
COLOR_OBSIDIAN = "#080B11"        # Base canvas
COLOR_SLATE_SURFACE = "#0E131F"   # Card, sidebar, panel surface
COLOR_ELEVATED = "#131A2B"        # Hover / elevated surface
COLOR_BORDER = "#1E2638"          # Structural borders
COLOR_BORDER_LIGHT = "rgba(255, 255, 255, 0.08)"
COLOR_AMBER = "#FF9900"           # Bloomberg Terminal accent
COLOR_AMBER_GLOW = "rgba(255, 153, 0, 0.2)"
COLOR_GREEN = "#00E676"           # Bullish / Positive delta
COLOR_GREEN_BG = "rgba(0, 230, 118, 0.12)"
COLOR_GREEN_BORDER = "rgba(0, 230, 118, 0.25)"
COLOR_RED = "#FF3366"             # Bearish / Negative delta
COLOR_RED_BG = "rgba(255, 51, 102, 0.12)"
COLOR_RED_BORDER = "rgba(255, 51, 102, 0.25)"
COLOR_CYAN = "#00F2FE"            # Technical overlay / EMA
COLOR_PURPLE = "#A855F7"          # VWAP / AI Confluence
COLOR_TEXT_WHITE = "#F8FAFC"      # Headings, primary values
COLOR_TEXT_LIGHT = "#E2E8F0"      # Readable body text
COLOR_TEXT_DIM = "#8F9CAE"        # Labels, subtitles
COLOR_TEXT_MUTED = "#6B7280"      # Muted captions

INSTITUTIONAL_CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
    /* Global Reset & Base Fonts */
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        background-color: {COLOR_OBSIDIAN} !important;
        color: {COLOR_TEXT_LIGHT};
    }}

    /* App Layout Container Clean-up */
    .block-container {{
        padding-top: 0.8rem !important;
        padding-bottom: 2rem !important;
        max-width: 98% !important;
    }}
    header[data-testid="stHeader"] {{
        background-color: transparent !important;
    }}
    #MainMenu, footer {{
        visibility: hidden !important;
    }}

    /* Top App Bar Header */
    .top-app-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: {COLOR_SLATE_SURFACE};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 10px 18px;
        margin-bottom: 14px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }}
    .brand-title {{
        font-size: 17px;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: {COLOR_TEXT_WHITE};
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .brand-sub {{
        font-size: 11.5px;
        color: {COLOR_TEXT_DIM};
        margin-top: 2px;
    }}
    .status-capsules {{
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }}

    /* Status Pills & Badges */
    .status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        font-family: 'JetBrains Mono', monospace;
    }}
    .pill-open, .pill-bullish {{
        background: {COLOR_GREEN_BG};
        color: {COLOR_GREEN};
        border: 1px solid {COLOR_GREEN_BORDER};
    }}
    .pill-closed, .pill-bearish {{
        background: {COLOR_RED_BG};
        color: {COLOR_RED};
        border: 1px solid {COLOR_RED_BORDER};
    }}
    .pill-amber {{
        background: rgba(255, 153, 0, 0.12);
        color: {COLOR_AMBER};
        border: 1px solid rgba(255, 153, 0, 0.28);
    }}
    .pill-cyan {{
        background: rgba(0, 242, 254, 0.12);
        color: {COLOR_CYAN};
        border: 1px solid rgba(0, 242, 254, 0.25);
    }}
    .pill-daemon {{
        background: rgba(99, 102, 241, 0.12);
        color: #818CF8;
        border: 1px solid rgba(99, 102, 241, 0.25);
    }}
    .pill-paper {{
        background: rgba(0, 242, 254, 0.12);
        color: {COLOR_CYAN};
        border: 1px solid rgba(0, 242, 254, 0.25);
    }}

    /* Metric Cards Override */
    div[data-testid="stMetric"] {{
        background: {COLOR_SLATE_SURFACE} !important;
        border: 1px solid {COLOR_BORDER} !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
        transition: transform 0.15s ease, border-color 0.15s ease !important;
    }}
    div[data-testid="stMetric"]:hover {{
        border-color: {COLOR_AMBER} !important;
        box-shadow: 0 0 12px {COLOR_AMBER_GLOW} !important;
        transform: translateY(-1px);
    }}
    div[data-testid="stMetricLabel"] p {{
        font-size: 11px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        color: {COLOR_TEXT_DIM} !important;
        font-weight: 600 !important;
        margin-bottom: 2px !important;
    }}
    div[data-testid="stMetricValue"] {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 20px !important;
        font-weight: 700 !important;
        color: {COLOR_TEXT_WHITE} !important;
        letter-spacing: -0.02em !important;
    }}
    div[data-testid="stMetricDelta"] {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11.5px !important;
        font-weight: 600 !important;
    }}

    /* Tab Navigation (Bloomberg Segmented Tab Style) */
    div[data-baseweb="tab-list"] {{
        gap: 6px !important;
        background-color: transparent !important;
        border-bottom: 1px solid {COLOR_BORDER} !important;
        padding-bottom: 8px !important;
        margin-bottom: 14px !important;
    }}
    button[data-baseweb="tab"] {{
        background: {COLOR_SLATE_SURFACE} !important;
        border: 1px solid {COLOR_BORDER} !important;
        border-radius: 6px !important;
        padding: 6px 13px !important;
        color: {COLOR_TEXT_DIM} !important;
        font-weight: 500 !important;
        font-size: 12.5px !important;
        letter-spacing: 0.02em !important;
        transition: all 0.2s ease !important;
    }}
    button[data-baseweb="tab"]:hover {{
        background: {COLOR_ELEVATED} !important;
        color: {COLOR_TEXT_WHITE} !important;
        border-color: rgba(255, 255, 255, 0.18) !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        background: {COLOR_ELEVATED} !important;
        border: 1px solid {COLOR_AMBER} !important;
        color: {COLOR_AMBER} !important;
        box-shadow: 0 0 10px {COLOR_AMBER_GLOW} !important;
        font-weight: 600 !important;
    }}
    div[data-baseweb="tab-highlight"] {{
        display: none !important;
    }}

    /* Buttons */
    div.stButton > button {{
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        letter-spacing: 0.02em !important;
        padding: 7px 15px !important;
        transition: all 0.2s ease !important;
    }}
    div.stButton > button[kind="primary"] {{
        background: {COLOR_AMBER} !important;
        border: none !important;
        color: #000000 !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 10px {COLOR_AMBER_GLOW} !important;
    }}
    div.stButton > button[kind="primary"]:hover {{
        background: #FFB300 !important;
        box-shadow: 0 4px 16px rgba(255, 153, 0, 0.45) !important;
        transform: translateY(-1px);
    }}
    div.stButton > button[kind="secondary"] {{
        background: {COLOR_SLATE_SURFACE} !important;
        border: 1px solid {COLOR_BORDER} !important;
        color: {COLOR_TEXT_LIGHT} !important;
    }}
    div.stButton > button[kind="secondary"]:hover {{
        background: {COLOR_ELEVATED} !important;
        border-color: rgba(255, 255, 255, 0.2) !important;
    }}

    /* Sidebar Clean Elevation */
    section[data-testid="stSidebar"] {{
        background-color: #0A0D15 !important;
        border-right: 1px solid {COLOR_BORDER} !important;
    }}
    .sidebar-brand {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
    }}
    .sidebar-brand-title {{
        font-size: 16px;
        font-weight: 700;
        letter-spacing: 0.03em;
        color: {COLOR_TEXT_WHITE};
    }}

    /* Dataframes & Tables */
    div[data-testid="stDataFrame"] {{
        border: 1px solid {COLOR_BORDER} !important;
        border-radius: 6px !important;
        overflow: hidden !important;
    }}

    /* Inputs, Selectboxes, Sliders */
    div[data-baseweb="select"] > div {{
        background-color: {COLOR_SLATE_SURFACE} !important;
        border: 1px solid {COLOR_BORDER} !important;
        border-radius: 6px !important;
        color: {COLOR_TEXT_WHITE} !important;
    }}
    div[data-baseweb="input"] > div {{
        background-color: {COLOR_SLATE_SURFACE} !important;
        border: 1px solid {COLOR_BORDER} !important;
        border-radius: 6px !important;
        color: {COLOR_TEXT_WHITE} !important;
    }}

    /* Custom Dividers */
    hr {{
        border-color: {COLOR_BORDER} !important;
        margin: 16px 0 !important;
    }}
</style>
"""


def inject_custom_css() -> None:
    """Injects institutional styling into Streamlit app."""
    import sys
    if st is not _original_st and st is not None:
        target_st = st
    else:
        target_st = sys.modules.get("streamlit") or st

    if target_st is not None and hasattr(target_st, "markdown"):
        target_st.markdown(INSTITUTIONAL_CSS, unsafe_allow_html=True)


def metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_positive: Optional[bool] = None,
    subtext: Optional[str] = None,
) -> str:
    """Generates HTML string for institutional metric card."""
    delta_html = ""
    if delta:
        delta_color = COLOR_GREEN if delta_positive is not False else COLOR_RED
        delta_arrow = "▲" if delta_positive is not False else "▼"
        delta_html = f'<div style="font-family:\'JetBrains Mono\', monospace; font-size:11px; font-weight:600; color:{delta_color}; margin-top:2px;">{delta_arrow} {delta}</div>'

    subtext_html = ""
    if subtext:
        subtext_html = f'<div style="font-size:10.5px; color:{COLOR_TEXT_MUTED}; margin-top:3px;">{subtext}</div>'

    return f"""
    <div style="background:{COLOR_SLATE_SURFACE}; border:1px solid {COLOR_BORDER}; border-radius:8px; padding:10px 14px; box-shadow:0 4px 16px rgba(0,0,0,0.25);">
        <div style="font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; color:{COLOR_TEXT_DIM};">{label}</div>
        <div style="font-family:\'JetBrains Mono\', monospace; font-size:20px; font-weight:700; color:{COLOR_TEXT_WHITE}; letter-spacing:-0.02em; margin-top:2px;">{value}</div>
        {delta_html}
        {subtext_html}
    </div>
    """


def badge(text: str, variant: str = "paper") -> str:
    """Generates HTML string for a styled pill badge."""
    cls_map = {
        "open": "pill-open",
        "closed": "pill-closed",
        "bullish": "pill-bullish",
        "bearish": "pill-bearish",
        "amber": "pill-amber",
        "cyan": "pill-cyan",
        "daemon": "pill-daemon",
        "paper": "pill-paper",
    }
    variant_str = str(variant or "paper").lower()
    css_class = cls_map.get(variant_str, "pill-paper")
    return f'<span class="status-pill {css_class}">{text}</span>'


badge_pill = badge


def pnl_pill(amount: float, pct: Optional[float] = None, currency: str = "₹") -> str:
    """Generates formatted HTML pill badge for profit/loss display."""
    try:
        amt = float(amount or 0.0) if amount is not None else 0.0
    except (ValueError, TypeError):
        amt = 0.0
    is_pos = amt >= 0
    css_class = "pill-bullish" if is_pos else "pill-bearish"
    sign = "+" if is_pos else ""
    pct_text = f" ({sign}{pct:.2f}%)" if pct is not None else ""
    return f'<span class="status-pill {css_class}">{sign}{currency}{amt:,.2f}{pct_text}</span>'


badge_pnl = pnl_pill


def order_badge(side: str) -> str:
    """Generates BUY/SELL order pill tag."""
    side_str = str(side or "HOLD").upper()
    is_buy = side_str == "BUY"
    css_class = "pill-bullish" if is_buy else "pill-bearish"
    return f'<span class="status-pill {css_class}">{side_str}</span>'
