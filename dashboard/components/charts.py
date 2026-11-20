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
            increasing_line_color="#00E676",
            increasing_fillcolor="#00E676",
            decreasing_line_color="#FF3B30",
            decreasing_fillcolor="#FF3B30",
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
                go.Scatter(x=timestamps, y=ema_20, mode="lines", name="EMA 20", line=dict(color="#00F2FE", width=1.5)),
                row=1,
                col=1,
            )
        if ema_50:
            fig.add_trace(
                go.Scatter(x=timestamps, y=ema_50, mode="lines", name="EMA 50", line=dict(color="#FF9100", width=1.5)),
                row=1,
                col=1,
            )
        if vwap:
            fig.add_trace(
                go.Scatter(x=timestamps, y=vwap, mode="lines", name="VWAP", line=dict(color="#A855F7", width=1.5, dash="dot")),
                row=1,
                col=1,
            )

    # 2. Volume Bar Chart
    vol_colors = ["#00E676" if closes[i] >= opens[i] else "#FF3B30" for i in range(len(closes))]
    fig.add_trace(
        go.Bar(x=timestamps, y=volumes, name="Volume", marker_color=vol_colors, opacity=0.7),
        row=2,
        col=1,
    )

    # 3. MACD Subplot
    if indicators_dict and indicators_dict.get("macd_line"):
        m_line = indicators_dict.get("macd_line")
        s_line = indicators_dict.get("macd_signal")
        hist = indicators_dict.get("macd_hist")

        fig.add_trace(
            go.Scatter(x=timestamps, y=m_line, mode="lines", name="MACD", line=dict(color="#00F2FE", width=1.5)),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=timestamps, y=s_line, mode="lines", name="Signal", line=dict(color="#FF9100", width=1.5)),
            row=3,
            col=1,
        )
        if hist:
            hist_colors = ["#00E676" if (h or 0) >= 0 else "#FF3B30" for h in hist]
            fig.add_trace(
                go.Bar(x=timestamps, y=hist, name="Hist", marker_color=hist_colors, opacity=0.75),
                row=3,
                col=1,
            )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono, Inter, -apple-system, sans-serif", color="#8F9CAE", size=11),
        xaxis_rangeslider_visible=False,
        height=700,
        margin=dict(l=30, r=30, t=40, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color="#8F9CAE"),
            bgcolor="rgba(14, 19, 31, 0.6)",
        ),
        hovermode="x unified",
    )
    fig.update_xaxes(
        gridcolor="rgba(255, 255, 255, 0.05)",
        zerolinecolor="rgba(255, 255, 255, 0.05)",
        tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#8F9CAE"),
    )
    fig.update_yaxes(
        gridcolor="rgba(255, 255, 255, 0.05)",
        zerolinecolor="rgba(255, 255, 255, 0.05)",
        tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#8F9CAE"),
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
            line=dict(color="#A855F7", width=2),
        )
    )

    # Horizontal guide bands
    fig.add_hline(y=70, line_dash="dash", line_color="#FF3B30", annotation_text="Overbought (70)", annotation_font_color="#FF3B30")
    fig.add_hline(y=30, line_dash="dash", line_color="#00E676", annotation_text="Oversold (30)", annotation_font_color="#00E676")
    fig.add_hline(y=50, line_dash="dot", line_color="rgba(255, 255, 255, 0.2)")

    fig.update_layout(
        title="Relative Strength Index (RSI 14)",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono, Inter, -apple-system, sans-serif", color="#8F9CAE", size=11),
        height=250,
        yaxis=dict(
            range=[0, 100],
            gridcolor="rgba(255, 255, 255, 0.05)",
            tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#8F9CAE"),
        ),
        xaxis=dict(
            gridcolor="rgba(255, 255, 255, 0.05)",
            tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#8F9CAE"),
        ),
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
            name="Virtual Equity",
            line=dict(color="#00E676", width=2.5),
            marker=dict(size=6, color="#00E676", symbol="circle"),
            fill="tozeroy",
            fillcolor="rgba(0, 230, 118, 0.08)",
        )
    )

    # Initial Capital Benchmark Line
    fig.add_hline(
        y=initial_capital,
        line_dash="dot",
        line_color="#FFB300",
        annotation_text=f"Initial Capital ({initial_capital:,.2f})",
        annotation_font_color="#FFB300",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title="Portfolio Equity Curve",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono, Inter, -apple-system, sans-serif", color="#8F9CAE", size=11),
        height=350,
        margin=dict(l=30, r=30, t=40, b=30),
        hovermode="x unified",
    )
    fig.update_xaxes(
        gridcolor="rgba(255, 255, 255, 0.05)",
        zerolinecolor="rgba(255, 255, 255, 0.05)",
        tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#8F9CAE"),
    )
    fig.update_yaxes(
        gridcolor="rgba(255, 255, 255, 0.05)",
        zerolinecolor="rgba(255, 255, 255, 0.05)",
        tickfont=dict(family="JetBrains Mono, monospace", size=10, color="#8F9CAE"),
    )

    return fig
