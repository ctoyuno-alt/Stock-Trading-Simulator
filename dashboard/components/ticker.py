"""
Live Scrolling Ticker Marquee for Quantum Trader.
Institutional Bloomberg-style streaming quotes tape with pure CSS animation.
"""

import textwrap
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except ImportError:
    st = None

def _cache_data(**kwargs):
    if st is not None and hasattr(st, "cache_data"):
        return st.cache_data(**kwargs)
    return lambda f: f

# Sensible market snapshot fallbacks (used when offline or for index symbols)
DEFAULT_SNAPSHOTS: List[Dict[str, Any]] = [
    {"symbol": "NIFTY 50", "price": 24180.80, "delta_pct": 0.42, "currency": "₹", "is_index": True},
    {"symbol": "SENSEX", "price": 79402.29, "delta_pct": 0.38, "currency": "₹", "is_index": True},
    {"symbol": "RELIANCE", "price": 1285.50, "delta_pct": 1.15, "currency": "₹", "is_index": False},
    {"symbol": "TCS", "price": 4120.00, "delta_pct": -0.45, "currency": "₹", "is_index": False},
    {"symbol": "HDFCBANK", "price": 1745.20, "delta_pct": 0.82, "currency": "₹", "is_index": False},
    {"symbol": "AAPL", "price": 228.50, "delta_pct": 0.65, "currency": "$", "is_index": False},
    {"symbol": "NVDA", "price": 142.80, "delta_pct": 2.34, "currency": "$", "is_index": False},
    {"symbol": "MSFT", "price": 425.20, "delta_pct": -0.22, "currency": "$", "is_index": False},
    {"symbol": "TSLA", "price": 345.60, "delta_pct": 3.85, "currency": "$", "is_index": False},
]


@_cache_data(ttl=60, show_spinner=False)
def fetch_ticker_quotes(_api_client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Fetches latest quotes for marquee. Returns updated quotes with fallback to DEFAULT_SNAPSHOTS.
    Cached for 60 seconds to avoid impacting Streamlit responsiveness.
    """
    quotes = [dict(s) for s in DEFAULT_SNAPSHOTS]
    if not _api_client:
        return quotes

    for item in quotes:
        if item.get("is_index"):
            continue  # Indices rely on baseline snapshot (not in backend equity universe)

        sym = item["symbol"]
        try:
            res = _api_client.get_candles(sym, timeframe="1d", period="5d")
            if res and not res.get("error") and res.get("candles"):
                candles = res["candles"]
                if len(candles) >= 1:
                    last_close = float(candles[-1]["close"])
                    prev_close = float(candles[-2]["close"]) if len(candles) >= 2 else float(candles[-1]["open"])
                    delta = last_close - prev_close
                    pct = (delta / prev_close) * 100 if prev_close > 0 else 0.0
                    item["price"] = last_close
                    item["delta_pct"] = pct
        except Exception:
            pass  # Retain sensible snapshot on transient error

    return quotes


def render_ticker_tape(api_client: Optional[Any] = None, market: Optional[str] = None) -> None:
    """
    Renders high-performance institutional scrolling marquee at top of the app.
    Pure CSS keyframe animation ensures smooth 60fps infinite loop without UI blocking.
    """
    quotes = fetch_ticker_quotes(api_client)

    # Build ticker item HTML inline to prevent Markdown 4-space code block interpretation
    items_html = "".join([
        (
            f'<div class="ticker-item">'
            f'<span class="ticker-sym">{q["symbol"]}</span>'
            f'<span class="ticker-price">{q["currency"]}{q["price"]:,.2f}</span>'
            f'<span class="ticker-delta" style="color: {"#00E676" if q["delta_pct"] >= 0 else "#FF3366"};">'
            f'{"▲" if q["delta_pct"] >= 0 else "▼"} {"+" if q["delta_pct"] >= 0 else ""}{q["delta_pct"]:.2f}%</span>'
            f'</div>'
        )
        for q in quotes
    ])

    # Double items to create seamless infinite CSS loop
    marquee_content = items_html + items_html

    ticker_html = textwrap.dedent(f"""
<style>
.ticker-wrap {{
    width: 100%;
    overflow: hidden;
    background: #0A0E17;
    border: 1px solid #1E2638;
    border-radius: 6px;
    padding: 6px 0;
    margin-bottom: 12px;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.4);
    white-space: nowrap;
    user-select: none;
}}
.ticker-track {{
    display: inline-flex;
    white-space: nowrap;
    will-change: transform;
    animation: ticker-scroll 38s linear infinite;
}}
.ticker-wrap:hover .ticker-track {{
    animation-play-state: paused;
}}
.ticker-item {{
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 0 16px;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
}}
.ticker-sym {{
    font-weight: 700;
    color: #E2E8F0;
    letter-spacing: 0.03em;
}}
.ticker-price {{
    color: #F8FAFC;
    font-weight: 500;
}}
.ticker-delta {{
    font-weight: 600;
    font-size: 11px;
}}
@keyframes ticker-scroll {{
    0% {{
        transform: translateX(0);
    }}
    100% {{
        transform: translateX(-50%);
    }}
}}
</style>
<div class="ticker-wrap" title="Hover to pause tape">
<div class="ticker-track">{marquee_content}</div>
</div>
""").strip()
    st.markdown(ticker_html, unsafe_allow_html=True)



render_ticker_marquee = render_ticker_tape
