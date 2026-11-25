"""
TradingView Financial Charting Integration for Streamlit.

Provides two complementary charting engines:
1. TradingView Lightweight Charts (Official Open-Source Canvas Engine):
   - Works for 100% of symbols (Indian Equities: RELIANCE, TCS, INFY, etc. & US: AAPL, NVDA, etc.).
   - Zero exchange licensing restrictions; fed by our real-time/historical backend market data.
   - Candlesticks (Green/Red), Volume histogram, Cyan EMA 20 line, Orange EMA 50 line.
   - Interactive crosshair with live hover legend (OHLC, Change %, Volume, EMA values).
   - High-performance HTML5 canvas with zoom, pan, and responsive resize.

2. TradingView Advanced Widget (Official Free Embed Widget):
   - Embedded iframe with TradingView's full drawing tools, Fibonacci retracements, and pitchforks.
   - Fully enabled for US Mega-Caps (NASDAQ:AAPL, NASDAQ:NVDA, NYSE:JPM, etc.).
   - For Indian equities (NSE/BSE), TradingView restricts 3rd-party iframe embeds due to exchange policies;
     we provide an explanatory notice and a direct one-click link to open the chart live on TradingView.com.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

# Mapping from internal symbols to TradingView exchange-qualified identifiers
TRADINGVIEW_SYMBOL_MAP: Dict[str, str] = {
    # 🇮🇳 Indian Equities (NSE)
    "RELIANCE": "NSE:RELIANCE",
    "TCS": "NSE:TCS",
    "INFY": "NSE:INFY",
    "HDFCBANK": "NSE:HDFCBANK",
    "ICICIBANK": "NSE:ICICIBANK",
    "BHARTIARTL": "NSE:BHARTIARTL",
    "SBIN": "NSE:SBIN",
    "ITC": "NSE:ITC",
    "LT": "NSE:LT",
    "TATAMOTORS": "NSE:TATAMOTORS",
    # 🇺🇸 US Equities (NYSE / NASDAQ)
    "AAPL": "NASDAQ:AAPL",
    "MSFT": "NASDAQ:MSFT",
    "NVDA": "NASDAQ:NVDA",
    "AMZN": "NASDAQ:AMZN",
    "GOOGL": "NASDAQ:GOOGL",
    "META": "NASDAQ:META",
    "TSLA": "NASDAQ:TSLA",
    "BRK-B": "NYSE:BRK.B",
    "JPM": "NYSE:JPM",
    "V": "NYSE:V",
}

US_SYMBOLS = {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V"}

TIMEFRAME_TO_TV_INTERVAL: Dict[str, str] = {
    "1d": "D",
    "1h": "60",
    "15m": "15",
    "5m": "5",
}


def clean_symbol_name(symbol: str) -> str:
    """Normalizes symbol string."""
    clean = str(symbol or "INSTRUMENT").strip().upper()
    if not clean:
        clean = "INSTRUMENT"
    if clean.endswith(".NS"):
        clean = clean[:-3]
    return clean


def is_us_symbol(symbol: str) -> bool:
    """Checks whether symbol is a US exchange equity."""
    return clean_symbol_name(symbol) in US_SYMBOLS


def get_tradingview_symbol(symbol: str) -> str:
    """Resolves symbol to TradingView exchange-qualified identifier."""
    clean = clean_symbol_name(symbol)
    return TRADINGVIEW_SYMBOL_MAP.get(clean, f"NSE:{clean}")


def get_tradingview_url(symbol: str) -> str:
    """Returns direct web URL for live analysis on TradingView.com."""
    tv_symbol = get_tradingview_symbol(symbol)
    if is_us_symbol(symbol):
        return f"https://www.tradingview.com/chart/?symbol={tv_symbol.replace(':', '%3A')}"
    return f"https://in.tradingview.com/chart/?symbol={tv_symbol.replace(':', '%3A')}"


def _parse_timestamp_to_seconds(ts_str: str) -> int:
    """Converts ISO timestamp string to UNIX seconds integer for Lightweight Charts."""
    try:
        dt = datetime.fromisoformat(ts_str)
        return int(dt.timestamp())
    except Exception:
        try:
            dt = datetime.strptime(ts_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            return 0


def render_tradingview_lightweight_chart(
    symbol: str,
    candles_data: Dict[str, Any],
    indicators_data: Optional[Dict[str, Any]] = None,
    timeframe: str = "1d",
    height: int = 640,
) -> None:
    """
    Renders high-performance TradingView Lightweight Chart using official standalone library.
    Works for 100% of symbols (Indian & US equities) with zero exchange blocks.
    """
    clean_sym = clean_symbol_name(symbol)
    safe_timeframe = str(timeframe or "1d")
    market_label = "US (NASDAQ/NYSE)" if is_us_symbol(clean_sym) else "India (NSE)"
    candles = candles_data.get("candles", []) if candles_data else []

    if not candles:
        import streamlit as st
        st.warning(f"No price candle data available to render chart for {clean_sym}.")
        return

    # 1. Prepare Candlesticks and Volume Data (sorted, strictly ascending, unique timestamps)
    seen_times = set()
    candlestick_points: List[Dict[str, Any]] = []
    volume_points: List[Dict[str, Any]] = []

    for c in candles:
        t_sec = _parse_timestamp_to_seconds(c.get("timestamp", ""))
        if t_sec <= 0 or t_sec in seen_times:
            continue
        seen_times.add(t_sec)

        op = float(c.get("open", 0.0))
        hi = float(c.get("high", 0.0))
        lo = float(c.get("low", 0.0))
        cl = float(c.get("close", 0.0))
        vol = float(c.get("volume", 0.0))

        candlestick_points.append({"time": t_sec, "open": op, "high": hi, "low": lo, "close": cl})
        vol_col = "rgba(0, 230, 118, 0.45)" if cl >= op else "rgba(255, 51, 102, 0.45)"
        volume_points.append({"time": t_sec, "value": vol, "color": vol_col})

    # Sort ascending by time
    candlestick_points.sort(key=lambda x: x["time"])
    volume_points.sort(key=lambda x: x["time"])

    # 2. Prepare EMA 20 and EMA 50 Series
    ema20_points: List[Dict[str, Any]] = []
    ema50_points: List[Dict[str, Any]] = []

    if indicators_data:
        ts_list = indicators_data.get("timestamps", [])
        ema_fast_list = indicators_data.get("ema_fast", [])
        ema_slow_list = indicators_data.get("ema_slow", [])

        seen_e20 = set()
        seen_e50 = set()

        for idx, ts in enumerate(ts_list):
            t_sec = _parse_timestamp_to_seconds(ts)
            if t_sec <= 0:
                continue

            if idx < len(ema_fast_list) and ema_fast_list[idx] is not None:
                if t_sec not in seen_e20:
                    seen_e20.add(t_sec)
                    ema20_points.append({"time": t_sec, "value": round(float(ema_fast_list[idx]), 2)})

            if idx < len(ema_slow_list) and ema_slow_list[idx] is not None:
                if t_sec not in seen_e50:
                    seen_e50.add(t_sec)
                    ema50_points.append({"time": t_sec, "value": round(float(ema_slow_list[idx]), 2)})

        ema20_points.sort(key=lambda x: x["time"])
        ema50_points.sort(key=lambda x: x["time"])

    candles_json = json.dumps(candlestick_points)
    volume_json = json.dumps(volume_points)
    ema20_json = json.dumps(ema20_points)
    ema50_json = json.dumps(ema50_points)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{clean_sym} - TradingView Chart</title>
        <!-- TradingView Official Lightweight Charts Standalone CDN -->
        <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background-color: #0E131F;
                font-family: 'JetBrains Mono', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                color: #8F9CAE;
            }}
            #chart-wrapper {{
                width: 100%;
                height: 100%;
                position: relative;
                border: 1px solid #1E2638;
                border-radius: 8px;
                overflow: hidden;
            }}
            #chart-container {{
                width: 100%;
                height: 100%;
            }}
            #legend {{
                position: absolute;
                top: 8px;
                left: 10px;
                z-index: 50;
                font-size: 12px;
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 8px;
                background: rgba(14, 19, 31, 0.88);
                padding: 6px 12px;
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                backdrop-filter: blur(8px);
                pointer-events: none;
            }}
            .legend-title {{ font-weight: 700; color: #F8FAFC; font-size: 13px; letter-spacing: 0.04em; }}
            .legend-badge {{
                background-color: #172033;
                color: #8F9CAE;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.06);
                font-size: 11px;
                font-weight: 600;
            }}
            .val-up {{ color: #00E676 !important; font-weight: 600; }}
            .val-down {{ color: #FF3366 !important; font-weight: 600; }}
            .ema20-label {{ color: #00F2FE; font-weight: 600; }}
            .ema50-label {{ color: #FF9900; font-weight: 600; }}
            #watermark {{
                position: absolute;
                bottom: 35px;
                left: 15px;
                z-index: 10;
                font-size: 32px;
                font-weight: 800;
                color: rgba(255, 255, 255, 0.03);
                pointer-events: none;
                user-select: none;
            }}
        </style>
    </head>
    <body>
        <div id="chart-wrapper">
            <div id="legend">
                <span class="legend-title">{clean_sym}</span>
                <span class="legend-badge">{safe_timeframe.upper()}</span>
                <span class="legend-badge">{market_label}</span>
                <span id="leg-ohlc">Loading data...</span>
                <span class="ema20-label" id="leg-ema20"></span>
                <span class="ema50-label" id="leg-ema50"></span>
            </div>
            <div id="watermark">{clean_sym} · {safe_timeframe.upper()}</div>
            <div id="chart-container"></div>
        </div>

        <script>
        (function() {{
            const container = document.getElementById('chart-container');
            const legendOhlc = document.getElementById('leg-ohlc');
            const legendEma20 = document.getElementById('leg-ema20');
            const legendEma50 = document.getElementById('leg-ema50');

            const chart = LightweightCharts.createChart(container, {{
                width: container.clientWidth,
                height: container.clientHeight || {height},
                layout: {{
                    background: {{ type: 'solid', color: '#0E131F' }},
                    textColor: '#8F9CAE',
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                    horzLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                }},
                rightPriceScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.08)',
                    scaleMargins: {{
                        top: 0.1,
                        bottom: 0.22,
                    }},
                }},
                timeScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.08)',
                    timeVisible: true,
                    secondsVisible: false,
                }},
            }});

            // 1. Candlestick Series (Minimal Modern Palette)
            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#00E676',
                downColor: '#FF3366',
                borderVisible: false,
                wickUpColor: '#00E676',
                wickDownColor: '#FF3366',
            }});

            // 2. Volume Series (Histogram at bottom)
            const volumeSeries = chart.addHistogramSeries({{
                priceFormat: {{ type: 'volume' }},
                priceScaleId: '', // Overlay without separate right scale
                scaleMargins: {{
                    top: 0.82,
                    bottom: 0,
                }},
            }});

            // 3. EMA 20 Line Series (Cyan)
            const ema20Series = chart.addLineSeries({{
                color: '#00F2FE',
                lineWidth: 2,
                crosshairMarkerVisible: true,
                title: 'EMA 20',
            }});

            // 4. EMA 50 Line Series (Amber)
            const ema50Series = chart.addLineSeries({{
                color: '#FF9900',
                lineWidth: 2,
                crosshairMarkerVisible: true,
                title: 'EMA 50',
            }});

            const candlesData = {candles_json};
            const volumeData = {volume_json};
            const ema20Data = {ema20_json};
            const ema50Data = {ema50_json};

            if (candlesData && candlesData.length > 0) {{
                candleSeries.setData(candlesData);
            }}
            if (volumeData && volumeData.length > 0) {{
                volumeSeries.setData(volumeData);
            }}
            if (ema20Data && ema20Data.length > 0) {{
                ema20Series.setData(ema20Data);
            }}
            if (ema50Data && ema50Data.length > 0) {{
                ema50Series.setData(ema50Data);
            }}

            chart.timeScale().fitContent();

            // Responsive Auto-Resize
            const resizeObserver = new ResizeObserver(entries => {{
                if (entries.length === 0 || !entries[0].contentRect) return;
                const {{ width, height }} = entries[0].contentRect;
                chart.applyOptions({{ width, height: height || {height} }});
            }});
            resizeObserver.observe(container);

            // Dynamic Legend Update on Crosshair Move
            function updateLegend(param) {{
                if (!param || !param.time || !param.seriesData) {{
                    if (candlesData.length > 0) {{
                        const last = candlesData[candlesData.length - 1];
                        const chg = last.close - last.open;
                        const chgPct = (chg / last.open) * 100;
                        const cls = chg >= 0 ? 'val-up' : 'val-down';
                        legendOhlc.innerHTML = `O: <b>${{last.open.toFixed(2)}}</b> H: <b>${{last.high.toFixed(2)}}</b> L: <b>${{last.low.toFixed(2)}}</b> C: <b class="${{cls}}">${{last.close.toFixed(2)}} (${{chg >= 0 ? '+' : ''}}${{chgPct.toFixed(2)}}%)</b>`;
                    }}
                    if (ema20Data.length > 0) {{
                        legendEma20.innerText = `EMA 20: ${{ema20Data[ema20Data.length - 1].value.toFixed(2)}}`;
                    }}
                    if (ema50Data.length > 0) {{
                        legendEma50.innerText = `EMA 50: ${{ema50Data[ema50Data.length - 1].value.toFixed(2)}}`;
                    }}
                    return;
                }}

                const cData = param.seriesData.get(candleSeries);
                if (cData) {{
                    const chg = cData.close - cData.open;
                    const chgPct = (chg / cData.open) * 100;
                    const cls = chg >= 0 ? 'val-up' : 'val-down';
                    legendOhlc.innerHTML = `O: <b>${{cData.open.toFixed(2)}}</b> H: <b>${{cData.high.toFixed(2)}}</b> L: <b>${{cData.low.toFixed(2)}}</b> C: <b class="${{cls}}">${{cData.close.toFixed(2)}} (${{chg >= 0 ? '+' : ''}}${{chgPct.toFixed(2)}}%)</b>`;
                }}

                const e20 = param.seriesData.get(ema20Series);
                if (e20 && e20.value !== undefined) {{
                    legendEma20.innerText = `EMA 20: ${{e20.value.toFixed(2)}}`;
                }} else {{
                    legendEma20.innerText = '';
                }}

                const e50 = param.seriesData.get(ema50Series);
                if (e50 && e50.value !== undefined) {{
                    legendEma50.innerText = `EMA 50: ${{e50.value.toFixed(2)}}`;
                }} else {{
                    legendEma50.innerText = '';
                }}
            }}

            chart.subscribeCrosshairMove(updateLegend);
            updateLegend(null);
        }})();
        </script>
    </body>
    </html>
    """

    import streamlit.components.v1 as components
    components.html(html_code, height=height, scrolling=False)


def render_tradingview_embed_widget(
    symbol: str,
    timeframe: str = "1d",
    height: int = 680,
    theme: str = "dark",
) -> None:
    """
    Renders the official TradingView Advanced Real-Time Chart widget iframe.
    Fully enabled for US mega-caps (AAPL, NVDA, TSLA, etc.).
    For Indian stocks, TradingView restricts embedding on 3rd party domains.
    """
    clean_sym = clean_symbol_name(symbol)
    tv_symbol = get_tradingview_symbol(symbol)
    safe_timeframe = str(timeframe or "1d")
    tv_interval = TIMEFRAME_TO_TV_INTERVAL.get(safe_timeframe.lower(), "D")
    external_url = get_tradingview_url(symbol)

    if not is_us_symbol(clean_sym):
        import streamlit as st
        st.warning(
            f"ℹ️ **TradingView Exchange Policy Notice for {clean_sym}:** "
            "The National Stock Exchange of India (NSE) restricts embedding live and historical data inside 3rd-party iframe widgets. "
            "That is why the embedded widget shows *'This symbol is only available on TradingView'*. "
            "Please use the **'📈 TradingView Interactive Pro Chart (Live)'** view above to inspect real-time interactive charts directly here, "
            f"or click below to open {clean_sym} live on TradingView.com:"
        )
        st.link_button(f"🔗 Open {clean_sym} Live on TradingView.com (New Tab)", external_url, type="primary")
        return

    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                height: 100%;
                width: 100%;
                background-color: #080B11;
                overflow: hidden;
            }}
            .tradingview-widget-container {{
                height: 100% !important;
                width: 100% !important;
            }}
            #tv_chart_container {{
                height: 100% !important;
                width: 100% !important;
            }}
        </style>
    </head>
    <body>
        <div class="tradingview-widget-container">
            <div id="tv_chart_container"></div>
            <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
            <script type="text/javascript">
                new TradingView.widget({{
                    "autosize": true,
                    "symbol": "{tv_symbol}",
                    "interval": "{tv_interval}",
                    "timezone": "exchange",
                    "theme": "{theme}",
                    "style": "1",
                    "locale": "en",
                    "toolbar_bg": "#1E1E1E",
                    "enable_publishing": false,
                    "allow_symbol_change": true,
                    "container_id": "tv_chart_container",
                    "hide_side_toolbar": false,
                    "withdateranges": true,
                    "details": true,
                    "hotlist": false,
                    "calendar": true,
                    "studies": [
                        "STD;EMA",
                        "STD;MACD",
                        "STD;RSI"
                    ]
                }});
            </script>
        </div>
    </body>
    </html>
    """

    import streamlit.components.v1 as components
    components.html(html_code, height=height, scrolling=False)


def render_tradingview_chart(
    symbol: str,
    timeframe: str = "1d",
    height: int = 680,
    theme: str = "dark",
    candles_data: Optional[Dict[str, Any]] = None,
    indicators_data: Optional[Dict[str, Any]] = None,
    use_embed_widget: bool = False,
) -> None:
    """
    Unified entry point for TradingView charts in Streamlit.
    - If use_embed_widget=True: Uses the iframe Advanced Chart widget (for US stocks / drawing tools).
    - By default: Uses the high-performance TradingView Lightweight Charts canvas engine (supporting all symbols).
    """
    safe_timeframe = str(timeframe or "1d")
    if use_embed_widget:
        render_tradingview_embed_widget(symbol, timeframe=safe_timeframe, height=height, theme=theme)
    elif candles_data and candles_data.get("candles"):
        render_tradingview_lightweight_chart(
            symbol=symbol,
            candles_data=candles_data,
            indicators_data=indicators_data,
            timeframe=safe_timeframe,
            height=height,
        )
    else:
        # Fallback to embed widget
        render_tradingview_embed_widget(symbol, timeframe=safe_timeframe, height=height, theme=theme)
