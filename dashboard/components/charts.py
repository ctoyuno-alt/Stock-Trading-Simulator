"""
Plotly Financial Visualizations for AI Paper Trading Dashboard.

Builds:
- Multi-panel Candlestick Chart (Candles, EMA 20/50, VWAP, Volume, MACD).
- RSI 14 Oscillator Chart with 70/30 boundary corridors.
- Portfolio Equity Curve and Drawdown Chart.
"""

from typing import Any, Dict, List, Optional

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def create_candlestick_with_indicators(
    candles_dict: Dict[str, Any],
    indicators_dict: Optional[Dict[str, Any]] = None,
    symbol: str = "INSTRUMENT",
) -> Any:
    """
    Creates an interactive 3-panel financial chart:
    - Panel 1: Candlesticks + EMA 20 + EMA 50 + VWAP
    - Panel 2: Volume Bars
    - Panel 3: MACD Line, Signal Line, and Histogram
    """
    if not HAS_PLOTLY:
        return None

    raw_candles = candles_dict.get("candles", [])
    if not raw_candles:
        return None

    timestamps = [c["timestamp"] for c in raw_candles]
    opens = [c["open"] for c in raw_candles]
    highs = [c["high"] for c in raw_candles]
    lows = [c["low"] for c in raw_candles]
    closes = [c["close"] for c in raw_candles]
    volumes = [c["volume"] for c in raw_candles]

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(f"{symbol} Price Action & Moving Averages", "Volume", "MACD (12, 26, 9)"),
        row_heights=[0.60, 0.20, 0.20],
    )

    # 1. Candlestick
    fig.add_trace(
        go.Candlestick(
            x=timestamps,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name="OHLC",
            increasing_line_color="#00C087",
            decreasing_line_color="#FF4B4B",
        ),
        row=1,
        col=1,
    )

    # Overlays from indicators if available
    if indicators_dict:
        ema_20 = indicators_dict.get("ema_fast")
        ema_50 = indicators_dict.get("ema_slow")
        vwap = indicators_dict.get("vwap")

        if ema_20:
            fig.add_trace(
                go.Scatter(x=timestamps, y=ema_20, mode="lines", name="EMA 20", line=dict(color="#FFB300", width=1.5)),
                row=1,
                col=1,
            )
        if ema_50:
            fig.add_trace(
                go.Scatter(x=timestamps, y=ema_50, mode="lines", name="EMA 50", line=dict(color="#29B6F6", width=1.5)),
                row=1,
                col=1,
            )
        if vwap:
            fig.add_trace(
                go.Scatter(x=timestamps, y=vwap, mode="lines", name="VWAP", line=dict(color="#AB47BC", width=1.5, dash="dot")),
                row=1,
                col=1,
            )

    # 2. Volume Bar Chart
    vol_colors = ["#00C087" if closes[i] >= opens[i] else "#FF4B4B" for i in range(len(closes))]
    fig.add_trace(
        go.Bar(x=timestamps, y=volumes, name="Volume", marker_color=vol_colors, opacity=0.8),
        row=2,
        col=1,
    )

    # 3. MACD Subplot
    if indicators_dict and indicators_dict.get("macd_line"):
        m_line = indicators_dict.get("macd_line")
        s_line = indicators_dict.get("macd_signal")
        hist = indicators_dict.get("macd_hist")

        fig.add_trace(
            go.Scatter(x=timestamps, y=m_line, mode="lines", name="MACD", line=dict(color="#29B6F6", width=1.5)),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=timestamps, y=s_line, mode="lines", name="Signal", line=dict(color="#FFB300", width=1.5)),
            row=3,
            col=1,
        )
        if hist:
            hist_colors = ["#00C087" if (h or 0) >= 0 else "#FF4B4B" for h in hist]
            fig.add_trace(
                go.Bar(x=timestamps, y=hist, name="Hist", marker_color=hist_colors, opacity=0.7),
                row=3,
                col=1,
            )

    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=700,
        margin=dict(l=30, r=30, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )

    return fig


def create_rsi_chart(timestamps: List[str], rsi_values: List[Optional[float]]) -> Any:
    """Plots RSI 14 with 70/30 overbought/oversold reference bands."""
    if not HAS_PLOTLY or not timestamps:
        return None

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=rsi_values,
            mode="lines",
            name="RSI 14",
            line=dict(color="#9C27B0", width=2),
        )
    )

    # Horizontal guide bands
    fig.add_hline(y=70, line_dash="dash", line_color="#FF4B4B", annotation_text="Overbought (70)")
    fig.add_hline(y=30, line_dash="dash", line_color="#00C087", annotation_text="Oversold (30)")
    fig.add_hline(y=50, line_dash="dot", line_color="#757575")

    fig.update_layout(
        title="Relative Strength Index (RSI 14)",
        template="plotly_dark",
        height=250,
        yaxis=dict(range=[0, 100]),
        margin=dict(l=30, r=30, t=40, b=30),
        hovermode="x unified",
    )

    return fig


def create_equity_curve_chart(
    timestamps: List[str],
    equity_values: List[float],
    initial_capital: float = 100000.0,
) -> Any:
    """Plots virtual portfolio equity curve against initial starting capital benchmark."""
    if not HAS_PLOTLY or not equity_values:
        return None

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=equity_values,
            mode="lines+markers",
            name="Virtual Equity (INR)",
            line=dict(color="#00C087", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(0, 192, 135, 0.1)",
        )
    )

    # Initial Capital Benchmark Line
    fig.add_hline(
        y=initial_capital,
        line_dash="dash",
        line_color="#FFB300",
        annotation_text=f"Initial Capital (₹{initial_capital:,.2f})",
    )

    fig.update_layout(
        title="Portfolio Equity Curve (INR)",
        template="plotly_dark",
        height=350,
        margin=dict(l=30, r=30, t=40, b=30),
        hovermode="x unified",
    )

    return fig
