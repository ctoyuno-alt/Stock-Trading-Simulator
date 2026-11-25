"""
Tier 1 & Tier 2 Component Visualization Test Suite for Quantum Trader Dashboard.

Validates:
1. Design System (dashboard/styles.py): CSS tokens, typography, metric cards, badges, P&L pills, and injection.
2. Ticker Tape (dashboard/components/ticker.py): Quotes fetching, delta formatting, missing candles fallback, and CSS animation.
3. Charting Engine (dashboard/components/charts.py): Candlestick with EMA/VWAP/MACD, RSI 14 oscillator, equity curves, and Plotly missing fallback.
4. TradingView Component (dashboard/components/tradingview.py): Symbol normalization, Indian/US exchange mapping, Lightweight Charts HTML5 canvas JSON serialization, and iframe widgets.
5. Radial Confluence & Gauge Visualization: Color tier classification, score bounds, and display helpers.
"""

from datetime import datetime, timezone
import json
import math
import sys
from typing import Any, Dict, List
import unittest
from unittest.mock import MagicMock, Mock, patch

# Ensure Streamlit modules are mocked in headless environment before importing dashboard modules
if "streamlit" not in sys.modules:
    mock_st_root = MagicMock()
    mock_st_root.cache_data = lambda *a, **k: (lambda f: f)
    sys.modules["streamlit"] = mock_st_root
if "streamlit.components.v1" not in sys.modules:
    mock_comp_root = MagicMock()
    sys.modules["streamlit.components.v1"] = mock_comp_root
    sys.modules["streamlit"].components.v1 = mock_comp_root

import dashboard.styles as styles
from dashboard.components import ticker
from dashboard.components import charts
from dashboard.components import tradingview
from dashboard.components.gauges import get_confluence_tier, score_to_gauge_degrees


class TestDesignSystemStyles(unittest.TestCase):
    """Tests Bloomberg/TradingView/Linear design system tokens and HTML generators."""

    def test_css_tokens_defined(self):
        """Validates standard institutional color tokens."""
        self.assertEqual(styles.COLOR_OBSIDIAN, "#080B11")
        self.assertEqual(styles.COLOR_SLATE_SURFACE, "#0E131F")
        self.assertEqual(styles.COLOR_AMBER, "#FF9900")
        self.assertEqual(styles.COLOR_GREEN, "#00E676")
        self.assertEqual(styles.COLOR_RED, "#FF3366")
        self.assertEqual(styles.COLOR_CYAN, "#00F2FE")
        self.assertEqual(styles.COLOR_PURPLE, "#A855F7")
        self.assertEqual(styles.COLOR_TEXT_WHITE, "#F8FAFC")
        self.assertEqual(styles.COLOR_TEXT_DIM, "#8F9CAE")

    def test_font_family_declarations(self):
        """Verifies Inter and JetBrains Mono Google font declarations in INSTITUTIONAL_CSS."""
        css = styles.INSTITUTIONAL_CSS
        self.assertIn("family=Inter", css)
        self.assertIn("family=JetBrains+Mono", css)
        self.assertIn("font-family: 'Inter'", css)
        self.assertIn("font-family: 'JetBrains Mono'", css)

    def test_css_structural_rules(self):
        """Verifies high-contrast terminal layout styling rules."""
        css = styles.INSTITUTIONAL_CSS
        self.assertIn(".block-container", css)
        self.assertIn(".top-app-bar", css)
        self.assertIn(".status-pill", css)
        self.assertIn('div[data-testid="stMetric"]', css)
        self.assertIn('button[data-baseweb="tab"]', css)

    def test_inject_custom_css(self):
        """inject_custom_css passes INSTITUTIONAL_CSS to st.markdown with unsafe_allow_html."""
        mock_st = MagicMock()
        with patch.object(styles, "st", mock_st):
            styles.inject_custom_css()
            mock_st.markdown.assert_called_once_with(styles.INSTITUTIONAL_CSS, unsafe_allow_html=True)

    def test_metric_card_positive_delta(self):
        """metric_card produces valid HTML with upward green arrow for positive delta."""
        html = styles.metric_card("Portfolio Value", "₹1,25,000.00", delta="+2.5%", delta_positive=True, subtext="Live MTM")
        self.assertIn("Portfolio Value", html)
        self.assertIn("₹1,25,000.00", html)
        self.assertIn("▲ +2.5%", html)
        self.assertIn(styles.COLOR_GREEN, html)
        self.assertIn("Live MTM", html)

    def test_metric_card_negative_delta(self):
        """metric_card produces valid HTML with downward red arrow for negative delta."""
        html = styles.metric_card("Drawdown", "₹-5,200.00", delta="-4.1%", delta_positive=False)
        self.assertIn("Drawdown", html)
        self.assertIn("▼ -4.1%", html)
        self.assertIn(styles.COLOR_RED, html)

    def test_metric_card_no_delta(self):
        """metric_card renders cleanly without delta arrow when delta is None."""
        html = styles.metric_card("Sharpe Ratio", "1.85")
        self.assertIn("Sharpe Ratio", html)
        self.assertIn("1.85", html)
        self.assertNotIn("▲", html)
        self.assertNotIn("▼", html)

    def test_metric_card_empty_and_extreme_values(self):
        """metric_card handles empty strings and extreme monetary values without errors."""
        html_empty = styles.metric_card("", "")
        self.assertIsInstance(html_empty, str)

        extreme_val = "₹999,999,999,999.99"
        html_extreme = styles.metric_card("National Debt", extreme_val)
        self.assertIn(extreme_val, html_extreme)

    def test_badge_variants(self):
        """badge generates appropriate CSS classes for all variants."""
        self.assertIn("pill-open", styles.badge("Open", "open"))
        self.assertIn("pill-closed", styles.badge("Closed", "closed"))
        self.assertIn("pill-bullish", styles.badge("Bullish", "bullish"))
        self.assertIn("pill-bearish", styles.badge("Bearish", "bearish"))
        self.assertIn("pill-amber", styles.badge("Warning", "amber"))
        self.assertIn("pill-cyan", styles.badge("Info", "cyan"))
        self.assertIn("pill-daemon", styles.badge("Daemon", "daemon"))
        self.assertIn("pill-paper", styles.badge("Default", "unknown_variant"))

    def test_pnl_pill_positive(self):
        """pnl_pill formats positive amount with + sign, bullish class, and percent."""
        html = styles.pnl_pill(amount=1500.50, pct=1.50, currency="₹")
        self.assertIn("pill-bullish", html)
        self.assertIn("+₹1,500.50", html)
        self.assertIn("(+1.50%)", html)

    def test_pnl_pill_negative(self):
        """pnl_pill formats negative amount with bearish class."""
        html = styles.pnl_pill(amount=-750.25, pct=-0.75, currency="₹")
        self.assertIn("pill-bearish", html)
        self.assertIn("₹-750.25", html)
        self.assertIn("(-0.75%)", html)

    def test_pnl_pill_zero_and_custom_currency(self):
        """pnl_pill handles zero amount with + sign and custom USD currency."""
        html_zero = styles.pnl_pill(amount=0.0, pct=0.0, currency="₹")
        self.assertIn("pill-bullish", html_zero)
        self.assertIn("+₹0.00", html_zero)

        html_usd = styles.pnl_pill(amount=250.0, currency="$")
        self.assertIn("+", html_usd)
        self.assertIn("$250.00", html_usd)

    def test_order_badge(self):
        """order_badge generates pill-bullish for BUY and pill-bearish for SELL."""
        buy_html = styles.order_badge("BUY")
        self.assertIn("pill-bullish", buy_html)
        self.assertIn("BUY", buy_html)

        sell_html = styles.order_badge("sell")
        self.assertIn("pill-bearish", sell_html)
        self.assertIn("SELL", sell_html)

    def test_styles_helpers_adversarial_none_inputs(self):
        """Verifies badge, pnl_pill, and order_badge handle None, non-string, and empty inputs defensively."""
        # badge with variant=None, empty, or unexpected
        self.assertIn("pill-paper", styles.badge("TEXT", variant=None))
        self.assertIn("pill-paper", styles.badge("TEXT", variant=""))
        self.assertIn("pill-paper", styles.badge("TEXT", variant=123))

        # pnl_pill with amount=None, invalid types, or zero
        pnl_none = styles.pnl_pill(amount=None)
        self.assertIn("pill-bullish", pnl_none)
        self.assertIn("+₹0.00", pnl_none)

        pnl_str = styles.pnl_pill(amount="invalid")
        self.assertIn("+₹0.00", pnl_str)

        # order_badge with side=None, lowercase, or unknown
        ob_none = styles.order_badge(None)
        self.assertIn("pill-bearish", ob_none)
        self.assertIn("HOLD", ob_none)

        ob_hold = styles.order_badge("HOLD")
        self.assertIn("pill-bearish", ob_hold)
        self.assertIn("HOLD", ob_hold)


class TestTickerMarqueeComponent(unittest.TestCase):
    """Tests the scrolling live ticker marquee component."""

    def test_default_snapshots_structure(self):
        """DEFAULT_SNAPSHOTS contains required symbol, price, delta_pct, and currency fields."""
        self.assertGreater(len(ticker.DEFAULT_SNAPSHOTS), 5)
        for s in ticker.DEFAULT_SNAPSHOTS:
            self.assertIn("symbol", s)
            self.assertIn("price", s)
            self.assertIn("delta_pct", s)
            self.assertIn("currency", s)
            self.assertIn("is_index", s)

    def test_fetch_ticker_quotes_offline_fallback(self):
        """fetch_ticker_quotes returns snapshot copies when api_client is None."""
        quotes = ticker.fetch_ticker_quotes(_api_client=None)
        self.assertEqual(len(quotes), len(ticker.DEFAULT_SNAPSHOTS))
        self.assertEqual(quotes[0]["symbol"], ticker.DEFAULT_SNAPSHOTS[0]["symbol"])

    def test_fetch_ticker_quotes_with_api_data(self):
        """fetch_ticker_quotes updates prices and delta percentage from candles."""
        mock_api = MagicMock()
        mock_api.get_candles.return_value = {
            "candles": [
                {"timestamp": "2026-11-22T00:00:00Z", "close": 2400.0, "open": 2390.0},
                {"timestamp": "2026-11-23T00:00:00Z", "close": 2520.0, "open": 2410.0},
            ]
        }

        quotes = ticker.fetch_ticker_quotes(_api_client=mock_api)
        rel = next(q for q in quotes if q["symbol"] == "RELIANCE")
        self.assertEqual(rel["price"], 2520.0)
        # Delta = (2520 - 2400) / 2400 * 100 = 5.0%
        self.assertAlmostEqual(rel["delta_pct"], 5.0, places=2)

    def test_fetch_ticker_quotes_negative_delta(self):
        """fetch_ticker_quotes calculates negative delta when price declines."""
        mock_api = MagicMock()
        mock_api.get_candles.return_value = {
            "candles": [
                {"timestamp": "2026-11-22T00:00:00Z", "close": 2500.0, "open": 2500.0},
                {"timestamp": "2026-11-23T00:00:00Z", "close": 2450.0, "open": 2500.0},
            ]
        }

        quotes = ticker.fetch_ticker_quotes(_api_client=mock_api)
        rel = next(q for q in quotes if q["symbol"] == "RELIANCE")
        self.assertEqual(rel["price"], 2450.0)
        # Delta = (2450 - 2500) / 2500 * 100 = -2.0%
        self.assertAlmostEqual(rel["delta_pct"], -2.0, places=2)

    def test_fetch_ticker_quotes_handles_api_error(self):
        """fetch_ticker_quotes preserves sensible snapshot when API returns error dict."""
        mock_api = MagicMock()
        mock_api.get_candles.return_value = {"error": True, "message": "Failed"}

        quotes = ticker.fetch_ticker_quotes(_api_client=mock_api)
        rel = next(q for q in quotes if q["symbol"] == "RELIANCE")
        default_rel = next(s for s in ticker.DEFAULT_SNAPSHOTS if s["symbol"] == "RELIANCE")
        self.assertEqual(rel["price"], default_rel["price"])

    def test_fetch_ticker_quotes_skips_indices(self):
        """fetch_ticker_quotes does not query candle endpoints for indices (NIFTY 50, SENSEX)."""
        mock_api = MagicMock()
        ticker.fetch_ticker_quotes(_api_client=mock_api)
        called_symbols = [c[0][0] for c in mock_api.get_candles.call_args_list]
        self.assertNotIn("NIFTY 50", called_symbols)
        self.assertNotIn("SENSEX", called_symbols)

    def test_render_ticker_tape_markup(self):
        """render_ticker_tape renders ticker-wrap, ticker-track, and CSS keyframe animation."""
        mock_st = MagicMock()
        with patch.object(ticker, "st", mock_st):
            ticker.render_ticker_tape()
            self.assertTrue(mock_st.markdown.called)
            html = mock_st.markdown.call_args[0][0]
            self.assertIn("ticker-wrap", html)
            self.assertIn("ticker-track", html)
            self.assertIn("ticker-scroll", html)
            self.assertIn("RELIANCE", html)
            self.assertIn("AAPL", html)

    def test_render_ticker_marquee_alias(self):
        """render_ticker_marquee is an alias of render_ticker_tape."""
        self.assertIs(ticker.render_ticker_marquee, ticker.render_ticker_tape)


class TestChartingComponents(unittest.TestCase):
    """Tests Plotly charting functions and graceful fallback when Plotly is absent."""

    def test_candlestick_builder_returns_none_when_plotly_missing(self):
        """create_candlestick_with_indicators returns None when HAS_PLOTLY is False."""
        with patch.object(charts, "HAS_PLOTLY", False):
            result = charts.create_candlestick_with_indicators({"candles": [{"timestamp": "2026-11-23", "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}]})
            self.assertIsNone(result)

    def test_candlestick_builder_empty_candles(self):
        """create_candlestick_with_indicators returns None when candles list is empty."""
        result = charts.create_candlestick_with_indicators({"candles": []})
        self.assertIsNone(result)

    def test_rsi_builder_returns_none_when_plotly_missing(self):
        """create_rsi_chart returns None when HAS_PLOTLY is False or timestamps empty."""
        with patch.object(charts, "HAS_PLOTLY", False):
            result = charts.create_rsi_chart(["2026-11-23"], [55.0])
            self.assertIsNone(result)

        result_empty = charts.create_rsi_chart([], [])
        self.assertIsNone(result_empty)

    def test_equity_curve_builder_returns_none_when_plotly_missing(self):
        """create_equity_curve_chart returns None when HAS_PLOTLY is False or empty."""
        with patch.object(charts, "HAS_PLOTLY", False):
            result = charts.create_equity_curve_chart(["2026-11-23"], [100000.0])
            self.assertIsNone(result)

        result_empty = charts.create_equity_curve_chart([], [])
        self.assertIsNone(result_empty)

    def test_candlestick_builder_with_mocked_plotly(self):
        """create_candlestick_with_indicators constructs subplots and adds traces."""
        mock_fig = MagicMock()
        mock_make_subplots = MagicMock(return_value=mock_fig)
        mock_go = MagicMock()

        candles_data = {
            "candles": [
                {"timestamp": "2026-11-23T10:00:00Z", "open": 2500, "high": 2520, "low": 2490, "close": 2510, "volume": 1000},
                {"timestamp": "2026-11-23T11:00:00Z", "open": 2510, "high": 2530, "low": 2505, "close": 2525, "volume": 1500},
            ]
        }
        indicators_data = {
            "ema_fast": [2505, 2515],
            "ema_slow": [2500, 2505],
            "vwap": [2508, 2518],
            "macd_line": [1.0, 1.5],
            "macd_signal": [0.8, 1.0],
            "macd_hist": [0.2, 0.5],
        }

        with patch.object(charts, "HAS_PLOTLY", True), \
             patch.object(charts, "make_subplots", mock_make_subplots, create=True), \
             patch.object(charts, "go", mock_go, create=True):
            fig = charts.create_candlestick_with_indicators(candles_data, indicators_data, symbol="RELIANCE")
            self.assertEqual(fig, mock_fig)
            self.assertTrue(mock_fig.add_trace.called)
            self.assertGreaterEqual(mock_fig.add_trace.call_count, 5)
            self.assertTrue(mock_fig.update_layout.called)

    def test_rsi_builder_with_mocked_plotly(self):
        """create_rsi_chart adds RSI trace and 70/30 guide lines."""
        mock_fig = MagicMock()
        mock_go = MagicMock()
        mock_go.Figure.return_value = mock_fig

        with patch.object(charts, "HAS_PLOTLY", True), \
             patch.object(charts, "go", mock_go, create=True):
            fig = charts.create_rsi_chart(["2026-11-23"], [62.5])
            self.assertEqual(fig, mock_fig)
            self.assertTrue(mock_fig.add_trace.called)
            self.assertGreaterEqual(mock_fig.add_hline.call_count, 3)

    def test_equity_curve_builder_with_mocked_plotly(self):
        """create_equity_curve_chart adds equity curve trace and initial capital benchmark line."""
        mock_fig = MagicMock()
        mock_go = MagicMock()
        mock_go.Figure.return_value = mock_fig

        with patch.object(charts, "HAS_PLOTLY", True), \
             patch.object(charts, "go", mock_go, create=True):
            fig = charts.create_equity_curve_chart(
                ["2026-11-20", "2026-11-23"], [100000.0, 104500.0], initial_capital=100000.0
            )
            self.assertEqual(fig, mock_fig)
            self.assertTrue(mock_fig.add_trace.called)
            mock_fig.add_hline.assert_called_once()
            self.assertEqual(mock_fig.add_hline.call_args[1]["y"], 100000.0)


class TestTradingViewComponent(unittest.TestCase):
    """Tests symbol normalization, TradingView Lightweight canvas generator, and widgets."""

    def test_clean_symbol_name(self):
        """clean_symbol_name removes .NS suffix, strips spaces, and uppercases."""
        self.assertEqual(tradingview.clean_symbol_name("reliance.ns"), "RELIANCE")
        self.assertEqual(tradingview.clean_symbol_name("  aapl  "), "AAPL")
        self.assertEqual(tradingview.clean_symbol_name("tcs"), "TCS")

    def test_is_us_symbol(self):
        """is_us_symbol correctly classifies US vs Indian equities."""
        self.assertTrue(tradingview.is_us_symbol("AAPL"))
        self.assertTrue(tradingview.is_us_symbol("NVDA"))
        self.assertTrue(tradingview.is_us_symbol("msft"))
        self.assertFalse(tradingview.is_us_symbol("RELIANCE"))
        self.assertFalse(tradingview.is_us_symbol("INFY"))

    def test_get_tradingview_symbol(self):
        """get_tradingview_symbol resolves exchange prefix."""
        self.assertEqual(tradingview.get_tradingview_symbol("RELIANCE"), "NSE:RELIANCE")
        self.assertEqual(tradingview.get_tradingview_symbol("AAPL"), "NASDAQ:AAPL")
        self.assertEqual(tradingview.get_tradingview_symbol("BRK-B"), "NYSE:BRK.B")
        self.assertEqual(tradingview.get_tradingview_symbol("JPM"), "NYSE:JPM")
        self.assertEqual(tradingview.get_tradingview_symbol("UNKNOWN_SYM"), "NSE:UNKNOWN_SYM")

    def test_get_tradingview_url(self):
        """get_tradingview_url generates correct regional URLs."""
        url_us = tradingview.get_tradingview_url("AAPL")
        self.assertIn("https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL", url_us)

        url_in = tradingview.get_tradingview_url("RELIANCE")
        self.assertIn("https://in.tradingview.com/chart/?symbol=NSE%3ARELIANCE", url_in)

    def test_parse_timestamp_to_seconds(self):
        """_parse_timestamp_to_seconds handles ISO and date formats."""
        sec_iso = tradingview._parse_timestamp_to_seconds("2026-11-23T10:00:00+00:00")
        self.assertGreater(sec_iso, 1700000000)

        sec_date = tradingview._parse_timestamp_to_seconds("2026-11-23")
        self.assertGreater(sec_date, 1700000000)

        sec_invalid = tradingview._parse_timestamp_to_seconds("INVALID")
        self.assertEqual(sec_invalid, 0)

    def test_render_tradingview_lightweight_chart_serialization(self):
        """render_tradingview_lightweight_chart serializes candles into HTML5 canvas JSON."""
        mock_st = MagicMock()
        mock_components = MagicMock()
        mock_st.components.v1 = mock_components

        candles_data = {
            "candles": [
                {"timestamp": "2026-11-23T10:00:00Z", "open": 2500, "high": 2520, "low": 2490, "close": 2510, "volume": 1000},
                {"timestamp": "2026-11-23T11:00:00Z", "open": 2510, "high": 2530, "low": 2505, "close": 2525, "volume": 1500},
            ]
        }
        indicators_data = {
            "timestamps": ["2026-11-23T10:00:00Z", "2026-11-23T11:00:00Z"],
            "ema_fast": [2505.0, 2515.0],
            "ema_slow": [2500.0, 2505.0],
        }

        with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_components}):
            tradingview.render_tradingview_lightweight_chart("RELIANCE", candles_data, indicators_data)
            self.assertTrue(mock_components.html.called)
            html_content = mock_components.html.call_args[0][0]
            self.assertIn("lightweight-charts", html_content)
            self.assertIn("RELIANCE", html_content)
            self.assertIn("India (NSE)", html_content)
            self.assertIn("addCandlestickSeries", html_content)

    def test_render_tradingview_lightweight_chart_empty_candles(self):
        """render_tradingview_lightweight_chart displays warning when candle data is empty."""
        mock_st = MagicMock()
        mock_components = MagicMock()
        mock_st.components.v1 = mock_components

        with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_components}):
            tradingview.render_tradingview_lightweight_chart("RELIANCE", {"candles": []})
            self.assertFalse(mock_components.html.called)

    def test_render_tradingview_embed_widget_us_vs_nse(self):
        """render_tradingview_embed_widget embeds iframe for US and renders notice for NSE."""
        mock_st = MagicMock()
        mock_components = MagicMock()
        mock_st.components.v1 = mock_components

        with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_components}):
            # US equity -> embeds widget
            tradingview.render_tradingview_embed_widget("AAPL")
            self.assertTrue(mock_components.html.called)

            # NSE equity -> renders notice because TradingView restricts 3rd party iframe embeds for NSE
            mock_components.html.reset_mock()
            tradingview.render_tradingview_embed_widget("RELIANCE")
            self.assertFalse(mock_components.html.called)
            self.assertTrue(mock_st.warning.called)

    def test_clean_symbol_name_adversarial_none_and_types(self):
        """clean_symbol_name safely handles None, empty strings, whitespace, and non-string inputs."""
        self.assertEqual(tradingview.clean_symbol_name(None), "INSTRUMENT")
        self.assertEqual(tradingview.clean_symbol_name(""), "INSTRUMENT")
        self.assertEqual(tradingview.clean_symbol_name("   "), "INSTRUMENT")
        self.assertEqual(tradingview.clean_symbol_name(123), "123")
        self.assertEqual(tradingview.clean_symbol_name("INFY.NS"), "INFY")

    def test_render_tradingview_adversarial_none_timeframe_and_symbol(self):
        """render_tradingview functions gracefully handle None timeframe and symbol."""
        mock_st = MagicMock()
        mock_components = MagicMock()
        mock_st.components.v1 = mock_components

        with patch.dict(sys.modules, {"streamlit": mock_st, "streamlit.components.v1": mock_components}):
            candles_data = {
                "candles": [
                    {"timestamp": "2026-11-23T10:00:00Z", "open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
                ]
            }
            # Should not raise AttributeError when timeframe=None or symbol=None
            tradingview.render_tradingview_lightweight_chart(None, candles_data, timeframe=None)
            self.assertTrue(mock_components.html.called)
            html_call = mock_components.html.call_args[0][0]
            self.assertIn("1D", html_call)

            mock_components.html.reset_mock()
            tradingview.render_tradingview_embed_widget("AAPL", timeframe=None)
            self.assertTrue(mock_components.html.called)

            mock_components.html.reset_mock()
            tradingview.render_tradingview_chart(None, timeframe=None, candles_data=candles_data)
            self.assertTrue(mock_components.html.called)


class TestRadialConfluenceVisualization(unittest.TestCase):
    """Tests deterministic confluence score classification and radial gauge helpers."""

    def test_confluence_tier_classification(self):
        """Validates score-to-tier color mapping across all ranges."""
        tier_high = get_confluence_tier(88.0)
        self.assertEqual(tier_high["status"], "CYAN")
        self.assertEqual(tier_high["color"], "#00F2FE")

        tier_buy = get_confluence_tier(75.0)
        self.assertEqual(tier_buy["status"], "GREEN")
        self.assertEqual(tier_buy["color"], "#00E676")

        tier_neutral = get_confluence_tier(55.0)
        self.assertEqual(tier_neutral["status"], "AMBER")
        self.assertEqual(tier_neutral["color"], "#FF9900")

        tier_bear = get_confluence_tier(30.0)
        self.assertEqual(tier_bear["status"], "CRIMSON")
        self.assertEqual(tier_bear["color"], "#FF3366")

    def test_gauge_radial_degree_mapping(self):
        """Converts confluence score [0, 100] to 180-degree semi-circle gauge rotation."""
        self.assertEqual(score_to_gauge_degrees(0.0), 0.0)
        self.assertEqual(score_to_gauge_degrees(50.0), 90.0)
        self.assertEqual(score_to_gauge_degrees(100.0), 180.0)
        self.assertEqual(score_to_gauge_degrees(85.0), 153.0)
        self.assertEqual(score_to_gauge_degrees(-10.0), 0.0)
        self.assertEqual(score_to_gauge_degrees(150.0), 180.0)


if __name__ == "__main__":
    unittest.main()
