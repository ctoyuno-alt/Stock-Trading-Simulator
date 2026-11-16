"""
Unit Tests for Phase 6: Google Gemini AI Market Analysis Integration.
Validates prompt grounding, schema compliance, mandatory disclaimers, and deterministic fallback.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
import unittest
from zoneinfo import ZoneInfo

from backend.app.ai.gemini_analyzer import GeminiMarketAnalyzer, SYSTEM_PROMPT
from backend.app.ai.schemas import AI_DISCLAIMER_TEXT, MarketAnalysisSummary
from backend.app.market_data.yfinance_provider import YFinanceProvider
from indicators.engine import TechnicalIndicatorEngine
from strategies.swing_strategy import EMAMACDSwingStrategy

IST_ZONE = ZoneInfo("Asia/Kolkata")


class TestPhase6AIAnalysis(unittest.TestCase):

    def setUp(self):
        self.analyzer = GeminiMarketAnalyzer(api_key="TEST_DUMMY_KEY")
        self.indicator_engine = TechnicalIndicatorEngine()
        self.strategy = EMAMACDSwingStrategy()

        # Build realistic sample data
        batch = YFinanceProvider.generate_synthetic_history("RELIANCE", days=80)
        self.candles = batch.candles
        self.series = self.indicator_engine.compute("RELIANCE", self.candles)
        self.snapshot = self.series.snapshot
        self.signal = self.strategy.generate_signal("RELIANCE", self.candles)

    def test_mandatory_disclaimer_content(self):
        """Verify that the institutional disclaimer explicitly clarifies AI confidence is not profit probability."""
        self.assertIn("NOT financial advice", AI_DISCLAIMER_TEXT)
        self.assertIn("guarantees zero profit", AI_DISCLAIMER_TEXT)
        self.assertIn("NOT the mathematical probability of a winning trade", AI_DISCLAIMER_TEXT)

    def test_grounded_prompt_embeds_exact_measurements(self):
        """Verify that the generated prompt embeds exact quantitative values without extrapolation."""
        prompt = self.analyzer._build_grounded_prompt(
            symbol="RELIANCE",
            snapshot=self.snapshot,
            signal=self.signal,
            news_headlines=["Reliance reports Q3 EBITDA growth."],
        )

        # Prompt must include system rules
        self.assertIn("GROUND TRUTH ONLY", prompt)
        self.assertIn("NO PROFIT PROMISES", prompt)

        # Prompt must contain exact close price and indicator numbers
        self.assertIn(str(float(self.snapshot.close_price)), prompt)
        self.assertIn(str(round(self.snapshot.rsi_14, 2)), prompt)
        self.assertIn(str(round(self.snapshot.macd_histogram, 4)), prompt)
        self.assertIn("Reliance reports Q3 EBITDA growth.", prompt)

    def test_deterministic_fallback_synthesis(self):
        """Verify deterministic fallback produces compliant MarketAnalysisSummary when API is offline."""
        analyzer_offline = GeminiMarketAnalyzer(api_key="")
        self.assertFalse(analyzer_offline.is_api_configured())

        summary = asyncio.run(
            analyzer_offline.analyze_market_state(
                symbol="RELIANCE",
                snapshot=self.snapshot,
                signal=self.signal,
            )
        )

        self.assertEqual(summary.symbol, "RELIANCE")
        self.assertGreater(len(summary.trend_analysis), 10)
        self.assertGreater(len(summary.momentum_analysis), 10)
        self.assertGreater(len(summary.macd_interpretation), 10)
        self.assertGreater(len(summary.vwap_relationship), 10)
        self.assertGreater(len(summary.key_risks), 0)
        self.assertIn("DISCLAIMER", summary.disclaimer)
        self.assertEqual(summary.disclaimer, AI_DISCLAIMER_TEXT)
        self.assertEqual(summary.ai_confidence_score, self.signal.technical_score)

    def test_json_parsing_and_markdown_stripping(self):
        """Verify that responses wrapped in markdown code fences are cleanly sanitized."""
        sample_payload = {
            "symbol": "TCS",
            "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "trend_analysis": "EMA 20 is above EMA 50.",
            "momentum_analysis": "RSI at 55.4 is in the expansion zone.",
            "macd_interpretation": "Histogram is positive.",
            "vwap_relationship": "Price is above VWAP.",
            "confirming_signals": ["EMA Bullish"],
            "conflicting_signals": [],
            "key_risks": ["Stop loss hit"],
            "ai_confidence_score": 80.0,
            "ai_confidence_rationale": "High confluence.",
            "recommended_action_opinion": "FAVORS_ACCUMULATION",
            "disclaimer": AI_DISCLAIMER_TEXT,
        }

        raw_wrapped = f"```json\n{json.dumps(sample_payload)}\n```"
        parsed = self.analyzer._parse_and_validate_response("TCS", raw_wrapped)

        self.assertEqual(parsed.symbol, "TCS")
        self.assertEqual(parsed.ai_confidence_score, 80.0)
        self.assertEqual(parsed.recommended_action_opinion, "FAVORS_ACCUMULATION")
        self.assertEqual(parsed.disclaimer, AI_DISCLAIMER_TEXT)


if __name__ == "__main__":
    unittest.main()
