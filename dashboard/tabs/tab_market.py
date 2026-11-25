"""
Tab 1: Market & Technical Indicators for Quantum Trader.
Renders real-time quotes, technical KPI snapshots, and multi-engine charting
(TradingView Lightweight Canvas, Advanced Widget, and Plotly quantitative panels).
"""

from typing import Any, Dict, Optional

try:
    import streamlit as st
except ImportError:
    st = None

from dashboard.components.charts import (
    HAS_PLOTLY,
    create_candlestick_with_indicators,
    create_rsi_chart,
)
from dashboard.components.tradingview import render_tradingview_chart


def _cache_data(**kwargs):
    """Safely decorates with st.cache_data if available, fallback to identity."""
    if st is not None and hasattr(st, "cache_data"):
        return st.cache_data(**kwargs)
    return lambda f: f


@_cache_data(ttl=15, show_spinner=False)
def fetch_cached_candles(_api_client: Any, symbol: str, timeframe: str, period: str) -> Dict[str, Any]:
    """
    Fetches candlestick data with 15s TTL.
    Prefixed with _api_client to avoid unhashable parameter errors in Streamlit.
    """
    if not _api_client:
        return {"candles": [], "error": True, "message": "API client unavailable"}
    try:
        res = _api_client.get_candles(symbol, timeframe=timeframe, period=period)
        if res is None:
            return {"candles": [], "error": True, "message": "No candle data returned"}
        return res
    except Exception as exc:
        return {"candles": [], "error": True, "message": str(exc)}


@_cache_data(ttl=15, show_spinner=False)
def fetch_cached_indicators(_api_client: Any, symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    Fetches technical indicators snapshot with 15s TTL.
    """
    if not _api_client:
        return {"error": True, "message": "API client unavailable", "latest_snapshot": {}}
    try:
        res = _api_client.get_indicators(symbol, timeframe=timeframe)
        if res is None:
            return {"error": True, "message": "No indicator data returned", "latest_snapshot": {}}
        return res
    except Exception as exc:
        return {"error": True, "message": str(exc), "latest_snapshot": {}}


# Lookback period map for timeframe
TIMEFRAME_LOOKBACK_MAP = {
    "5m": "5d",
    "15m": "5d",
    "1h": "1mo",
    "1d": "6mo",
}


def render_tab(
    api_client: Any,
    state: Dict[str, Any],
    market: str,
    symbol: str,
    timeframe: str,
) -> None:
    """
    Renders Tab 1: Market & Technical Indicators.
    Uniform interface contract adhering to dashboard/app.py.
    """
    active_market = market or state.get("active_market", "NSE")
    active_currency = state.get("active_currency", "INR")
    curr_sym = state.get("curr_sym", "₹")
    refresh_rate = state.get("refresh_rate", 10)
    auto_refresh = state.get("auto_refresh", False)
    safe_timeframe = str(timeframe or "1d")
    safe_symbol = str(symbol or ("AAPL" if active_market == "US" else "RELIANCE"))

    # 1. Header Toolbar
    m_top_col1, m_top_col2 = st.columns([4, 1])
    with m_top_col1:
        st.markdown(f"### **{safe_symbol} — Live Market & Technical Indicators**")
        st.caption(
            f"Data source: TradingView & Yahoo Finance • {active_market} Market ({active_currency}) • "
            f"Timeframe: {safe_timeframe} • Polling interval: {refresh_rate if auto_refresh else 'Manual'}s"
        )
    with m_top_col2:
        if st.button("🔄 Refresh Quote Now", use_container_width=True, key="btn_refresh_quote_tab_market"):
            # Instant cache busting
            try:
                fetch_cached_candles.clear()
                fetch_cached_indicators.clear()
            except Exception:
                pass
            st.rerun()

    # 2. Chart Engine Selector
    chart_engine = st.radio(
        "Chart Engine View",
        [
            "📈 TradingView Interactive Pro Chart (Live Canvas - All Stocks)",
            "🌐 TradingView Advanced Widget (US Stocks & Web View)",
            "📊 Quantitative Multi-Panel (Plotly Indicators)",
        ],
        horizontal=True,
        index=0,
        key="market_chart_engine_radio",
    )

    # 3. Cached Data Retrieval (Sub-100ms on reruns)
    default_period = TIMEFRAME_LOOKBACK_MAP.get(safe_timeframe, "6mo")
    candles_data = fetch_cached_candles(api_client, safe_symbol, safe_timeframe, default_period)
    indicators_data = fetch_cached_indicators(api_client, safe_symbol, safe_timeframe)

    # 4. Error Banners
    if isinstance(candles_data, dict) and candles_data.get("error"):
        st.warning(f"Note on historical candles: {candles_data.get('message')}")
    if isinstance(indicators_data, dict) and indicators_data.get("error"):
        st.warning(f"Note on technical indicators: {indicators_data.get('message')}")

    # 5. High-Density Bloomberg Metric Ribbon (Resilient, never collapses)
    latest_snap = (indicators_data.get("latest_snapshot") or {}) if isinstance(indicators_data, dict) else {}
    if not isinstance(latest_snap, dict):
        latest_snap = {}
    if latest_snap:
        state["latest_snapshot"] = latest_snap

    # Extract price & delta fallbacks if snapshot is empty but candles exist
    candles = (candles_data.get("candles") or []) if isinstance(candles_data, dict) else []
    if not isinstance(candles, list):
        candles = []
    close_price = latest_snap.get("close_price")
    if close_price is None and candles:
        try:
            close_price = float(candles[-1].get("close", 0.0))
        except (ValueError, TypeError, IndexError):
            close_price = None

    kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5, kpi_c6 = st.columns(6)

    # Metric 1: Close Price
    close_str = f"{curr_sym}{close_price:,.2f}" if close_price is not None else "—"
    kpi_c1.metric("Close", close_str)

    # Metric 2: EMA 20
    ema_20 = latest_snap.get("ema_fast_20")
    ema_20_str = f"{curr_sym}{ema_20:,.2f}" if ema_20 is not None else "—"
    kpi_c2.metric("EMA 20", ema_20_str)

    # Metric 3: EMA 50 & Spread
    ema_50 = latest_snap.get("ema_slow_50")
    ema_50_str = f"{curr_sym}{ema_50:,.2f}" if ema_50 is not None else "—"
    ema_spread = latest_snap.get("ema_spread_pct")
    ema_delta = f"{ema_spread:+.2f}%" if ema_spread is not None else None
    kpi_c3.metric("EMA 50", ema_50_str, delta=ema_delta)

    # Metric 4: RSI 14
    rsi_14 = latest_snap.get("rsi_14")
    rsi_str = f"{rsi_14:.1f}" if rsi_14 is not None else "—"
    rsi_regime = latest_snap.get("rsi_regime")
    kpi_c4.metric("RSI 14", rsi_str, delta=rsi_regime)

    # Metric 5: MACD Histogram
    macd_hist = latest_snap.get("macd_histogram")
    macd_str = f"{macd_hist:+.3f}" if macd_hist is not None else "—"
    macd_state = latest_snap.get("macd_state")
    kpi_c5.metric("MACD Hist", macd_str, delta=macd_state)

    # Metric 6: VWAP
    vwap = latest_snap.get("vwap")
    vwap_str = f"{curr_sym}{vwap:,.2f}" if vwap is not None else "—"
    p_vwap_pct = latest_snap.get("price_to_vwap_pct")
    vwap_delta = f"{p_vwap_pct:+.2f}%" if p_vwap_pct is not None else None
    kpi_c6.metric("VWAP", vwap_str, delta=vwap_delta)

    # 6. Chart Engine Rendering
    if "Canvas" in chart_engine or "All Stocks" in chart_engine:
        st.caption(
            f"⚡ Interactive TradingView Canvas Chart for {safe_symbol} ({safe_timeframe.upper()}) with volume histogram, "
            "EMA 20 (Cyan), EMA 50 (Amber) and live crosshair legend."
        )
        if candles:
            render_tradingview_chart(
                safe_symbol,
                timeframe=safe_timeframe,
                height=640,
                candles_data=candles_data,
                indicators_data=indicators_data,
                use_embed_widget=False,
            )
        else:
            st.info(f"Historical candles are currently loading or unavailable for {safe_symbol}. Try clicking 'Refresh Quote Now'.")

    elif "Advanced Widget" in chart_engine:
        st.caption("⚡ TradingView Advanced Widget with drawing tools, Fibonacci retracements & institutional dark theme.")
        render_tradingview_chart(
            safe_symbol,
            timeframe=safe_timeframe,
            height=680,
            use_embed_widget=True,
        )

    else:
        # Quantitative Multi-Panel (Plotly Indicators)
        if not HAS_PLOTLY:
            st.warning("Plotly is not installed in the environment. Switch to TradingView Canvas view above.")
        elif not candles:
            st.info(f"No candlestick data available to construct Plotly multi-panel chart for {safe_symbol}.")
        else:
            fig = create_candlestick_with_indicators(candles_data, indicators_data, symbol=safe_symbol)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            # RSI Subplot
            if indicators_data and indicators_data.get("rsi"):
                rsi_fig = create_rsi_chart(indicators_data.get("timestamps", []), indicators_data.get("rsi", []))
                if rsi_fig:
                    st.plotly_chart(rsi_fig, use_container_width=True)
