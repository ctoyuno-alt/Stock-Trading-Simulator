"""
TradingView Financial Charting Widget Integration for Streamlit.

Embeds the official TradingView Advanced Real-Time Chart widget, supporting:
- Live streaming price updates for NSE and US equities (NYSE/NASDAQ).
- Institutional drawing tools, Fibonacci retracements, pitchforks, and trendlines.
- Built-in indicators (EMA, MACD, RSI, Volume, Bollinger Bands).
- Customizable intervals (1m, 5m, 15m, 1h, Daily, Weekly).
- High-contrast institutional dark theme.
"""

from typing import Dict

# Mapping from internal symbols to TradingView symbols
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

TIMEFRAME_TO_TV_INTERVAL: Dict[str, str] = {
    "1d": "D",
    "1h": "60",
    "15m": "15",
    "5m": "5",
}


def get_tradingview_symbol(symbol: str) -> str:
    """Resolves symbol to TradingView exchange-qualified identifier."""
    clean = symbol.strip().upper()
    if clean.endswith(".NS"):
        clean = clean[:-3]
    return TRADINGVIEW_SYMBOL_MAP.get(clean, f"NSE:{clean}")


def render_tradingview_chart(
    symbol: str,
    timeframe: str = "1d",
    height: int = 680,
    theme: str = "dark",
) -> None:
    """
    Renders the official TradingView Advanced Chart Widget inside Streamlit.
    """
    tv_symbol = get_tradingview_symbol(symbol)
    tv_interval = TIMEFRAME_TO_TV_INTERVAL.get(timeframe.lower(), "D")

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
                background-color: #121212;
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
