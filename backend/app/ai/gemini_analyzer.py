"""
Google Gemini AI Market Analysis Service.

Responsibilities:
- Builds grounded, non-hallucinatory prompts embedding exact quantitative indicator measurements.
- Enforces structured JSON output matching MarketAnalysisSummary.
- Implements strict safety guardrails: forbids price invention, requires institutional disclaimers,
  and clarifies that AI confidence is NOT a probability of profit.
- Provides a deterministic rule-based fallback when offline, unauthenticated, or rate-limited.
"""

from datetime import datetime, timezone
import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.app.ai.schemas import AI_DISCLAIMER_TEXT, MarketAnalysisSummary
from backend.app.core.config import get_settings
from indicators.base import IndicatorSnapshot
from strategies.base import TradeSignal

logger = logging.getLogger(__name__)
settings = get_settings()


SYSTEM_PROMPT = """You are an Institutional Quantitative Research Assistant specializing in Indian Stock Market (NSE/BSE) swing trading.
Your role is to explain technical indicator signals, evaluate trend confluence, identify conflicting technical readings, and highlight key downside risks.

CRITICAL OPERATIONAL RULES:
1. GROUND TRUTH ONLY: Analyze ONLY the provided structured quantitative data. NEVER invent, extrapolate, or hallucinate prices, indicators, corporate actions, or news.
2. NO PROFIT PROMISES: Never promise profits or treat AI confidence as a probability of financial gain. AI confidence measures the clarity and confluence of technical indicators.
3. STRUCTURED OUTPUT: You MUST reply with valid JSON adhering strictly to the requested schema. No conversational filler outside the JSON.
"""


class GeminiMarketAnalyzer:
    """Orchestrates Gemini API requests with schema validation and deterministic fallback."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self.timeout_seconds = settings.GEMINI_TIMEOUT_SECONDS

    def is_api_configured(self) -> bool:
        """Checks if a valid, non-placeholder Gemini API key is configured."""
        if not self.api_key:
            return False
        cleaned = self.api_key.strip()
        if not cleaned or "YOUR_GEMINI" in cleaned or cleaned == "********":
            return False
        return len(cleaned) >= 20

    async def analyze_market_state(
        self,
        symbol: str,
        snapshot: IndicatorSnapshot,
        signal: TradeSignal,
        news_headlines: Optional[List[str]] = None,
    ) -> MarketAnalysisSummary:
        """
        Generates schema-validated AI market analysis for a given instrument.
        Falls back seamlessly to deterministic rule-based synthesis if API is unavailable.
        """
        if not self.is_api_configured():
            logger.info(
                f"Gemini API key unconfigured or placeholder. Utilizing deterministic fallback for {symbol}."
            )
            return self._generate_deterministic_fallback(symbol, snapshot, signal, reason="API key not configured")

        prompt = self._build_grounded_prompt(symbol, snapshot, signal, news_headlines)

        try:
            raw_response = await self._call_gemini_api(prompt)
            parsed_summary = self._parse_and_validate_response(symbol, raw_response)
            return parsed_summary
        except Exception as exc:
            logger.warning(
                f"Gemini API call failed for {symbol} ({str(exc)}). Switching to deterministic fallback."
            )
            return self._generate_deterministic_fallback(
                symbol, snapshot, signal, reason=f"Gemini API call failed: {str(exc)}"
            )

    def _build_grounded_prompt(
        self,
        symbol: str,
        snapshot: IndicatorSnapshot,
        signal: TradeSignal,
        news_headlines: Optional[List[str]] = None,
    ) -> str:
        """Constructs an unalterable, grounded prompt embedding exact quantitative measurements."""
        payload = {
            "symbol": symbol,
            "market_price_inr": float(snapshot.close_price),
            "timestamp": snapshot.timestamp.isoformat(),
            "indicators": {
                "ema_fast_20": float(snapshot.ema_fast_20) if snapshot.ema_fast_20 else None,
                "ema_slow_50": float(snapshot.ema_slow_50) if snapshot.ema_slow_50 else None,
                "ema_trend_regime": snapshot.ema_trend_regime.value,
                "ema_spread_pct": snapshot.ema_spread_pct,
                "rsi_14": snapshot.rsi_14,
                "rsi_regime": snapshot.rsi_regime.value,
                "macd_line": snapshot.macd_line,
                "macd_signal": snapshot.macd_signal,
                "macd_histogram": snapshot.macd_histogram,
                "macd_state": snapshot.macd_state.value,
                "vwap": float(snapshot.vwap) if snapshot.vwap else None,
                "price_to_vwap_pct": snapshot.price_to_vwap_pct,
            },
            "deterministic_strategy": {
                "strategy_action": signal.action.value,
                "strategy_strength": signal.strength.value,
                "technical_score": signal.technical_score,
                "suggested_stop_loss": float(signal.suggested_stop_loss),
                "suggested_take_profit": float(signal.suggested_take_profit),
                "risk_reward_ratio": signal.risk_reward_ratio,
                "confirming_factors": signal.confirming_factors,
                "conflicting_factors": signal.conflicting_factors,
            },
            "news_context": news_headlines or ["No verified external news available."],
        }

        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"INPUT QUANTITATIVE DATA FOR {symbol}:\n"
            f"```json\n{json.dumps(payload, indent=2)}\n```\n\n"
            f"Respond with a valid JSON object matching the MarketAnalysisSummary schema:\n"
            f"- symbol (string)\n"
            f"- analysis_timestamp_utc (string)\n"
            f"- trend_analysis (string: evaluate EMA20 vs EMA50)\n"
            f"- momentum_analysis (string: evaluate RSI 14)\n"
            f"- macd_interpretation (string: evaluate MACD momentum)\n"
            f"- vwap_relationship (string: evaluate institutional value vs VWAP)\n"
            f"- confirming_signals (list of strings)\n"
            f"- conflicting_signals (list of strings)\n"
            f"- key_risks (list of strings)\n"
            f"- ai_confidence_score (float 0.0 - 100.0: technical clarity rating, NOT probability of profit)\n"
            f"- ai_confidence_rationale (string: explanation of score)\n"
            f"- recommended_action_opinion (string)\n"
            f"- disclaimer (string)\n"
        )

    async def _call_gemini_api(self, prompt: str) -> str:
        """Executes API request to Google Gemini with timeout protection."""
        # Attempt modern google-genai SDK first
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=settings.GEMINI_TEMPERATURE,
                    response_mime_type="application/json",
                ),
            )
            return response.text
        except ImportError:
            pass

        # Fallback to direct HTTP request using httpx
        import httpx

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": settings.GEMINI_TEMPERATURE,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as http_client:
            resp = await http_client.post(url, headers=headers, json=request_body)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Empty response candidates received from Gemini API.")
            return candidates[0]["content"]["parts"][0]["text"]

    def _parse_and_validate_response(self, symbol: str, raw_text: str) -> MarketAnalysisSummary:
        """Parses JSON response and validates against MarketAnalysisSummary schema."""
        # Strip potential markdown code blocks
        clean_json = raw_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        parsed = json.loads(clean_json)
        parsed["symbol"] = symbol.upper()
        parsed["disclaimer"] = AI_DISCLAIMER_TEXT
        if "analysis_timestamp_utc" not in parsed:
            parsed["analysis_timestamp_utc"] = datetime.now(timezone.utc).isoformat()

        if hasattr(MarketAnalysisSummary, "model_validate"):
            return MarketAnalysisSummary.model_validate(parsed)
        return MarketAnalysisSummary(**parsed)

    def _generate_deterministic_fallback(
        self,
        symbol: str,
        snapshot: IndicatorSnapshot,
        signal: TradeSignal,
        reason: str = "Deterministic Rule-Based Fallback",
    ) -> MarketAnalysisSummary:
        """
        High-fidelity deterministic synthesizer that produces compliant MarketAnalysisSummary
        directly from indicator math when Gemini is offline or unconfigured.
        """
        # Trend
        if snapshot.ema_trend_regime.value == "BULLISH":
            trend_desc = (
                f"Bullish alignment: EMA 20 (₹{snapshot.ema_fast_20}) is established above EMA 50 (₹{snapshot.ema_slow_50}). "
                f"The spread is {snapshot.ema_spread_pct:.2f}%, confirming upward medium-term trend structure."
            )
        elif snapshot.ema_trend_regime.value == "BEARISH":
            trend_desc = (
                f"Bearish alignment: EMA 20 (₹{snapshot.ema_fast_20}) is below EMA 50 (₹{snapshot.ema_slow_50}), "
                f"reflecting ongoing downward pressure or trend deterioration."
            )
        else:
            trend_desc = "Neutral/Converging EMAs: Moving averages are tightly compressed, indicating range-bound chop."

        # Momentum
        rsi_val = snapshot.rsi_14 or 50.0
        if rsi_val >= 70.0:
            momentum_desc = f"Overbought condition: RSI 14 stands at {rsi_val:.1f} (> 70.0). High risk of mean-reversion pullback."
        elif rsi_val <= 30.0:
            momentum_desc = f"Oversold condition: RSI 14 stands at {rsi_val:.1f} (< 30.0). Selling momentum is severely stretched."
        elif 50.0 <= rsi_val < 70.0:
            momentum_desc = f"Constructive momentum: RSI 14 at {rsi_val:.1f} resides in the optimal bullish expansion corridor (50-70)."
        else:
            momentum_desc = f"Defensive momentum: RSI 14 at {rsi_val:.1f} remains sub-50, reflecting lack of buying power."

        # MACD
        hist_val = snapshot.macd_histogram or 0.0
        macd_desc = (
            f"MACD line at {snapshot.macd_line} with Signal line at {snapshot.macd_signal}. "
            f"Histogram is {'positive' if hist_val > 0 else 'negative'} ({hist_val:+.3f}), "
            f"indicating {snapshot.macd_state.value.lower().replace('_', ' ')}."
        )

        # VWAP
        vwap_pct = snapshot.price_to_vwap_pct or 0.0
        vwap_desc = (
            f"Price (₹{snapshot.close_price}) is trading {abs(vwap_pct):.2f}% "
            f"{'above' if vwap_pct >= 0 else 'below'} daily VWAP (₹{snapshot.vwap}), "
            f"indicating institutional {'accumulation' if vwap_pct >= 0 else 'distribution'} bias."
        )

        key_risks = [
            f"Mandatory stop-loss must be placed at ₹{signal.suggested_stop_loss} ({signal.stop_loss_pct:.1f}% risk).",
            "General market volatility, RBI interest-rate shifts, or sudden gap-down session opens.",
        ]
        if signal.conflicting_factors:
            key_risks.extend(signal.conflicting_factors[:2])

        confidence = signal.technical_score
        confidence_rationale = (
            f"Confidence heuristic rated at {confidence:.1f}/100 based on {len(signal.confirming_factors)} confirming factors "
            f"vs {len(signal.conflicting_factors)} conflicting signals. [{reason}]."
        )

        action_opinion = {
            "BUY": "FAVORS_ACCUMULATION",
            "SELL": "FAVORS_EXIT_OR_PRESERVATION",
            "HOLD": "FAVORS_PATIENCE",
        }.get(signal.action.value, "FAVORS_PATIENCE")

        payload = {
            "symbol": symbol.upper(),
            "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "trend_analysis": trend_desc,
            "momentum_analysis": momentum_desc,
            "macd_interpretation": macd_desc,
            "vwap_relationship": vwap_desc,
            "confirming_signals": signal.confirming_factors or ["No strong confluence factors identified."],
            "conflicting_signals": signal.conflicting_factors or ["No significant conflicting signals detected."],
            "key_risks": key_risks,
            "ai_confidence_score": confidence,
            "ai_confidence_rationale": confidence_rationale,
            "recommended_action_opinion": action_opinion,
            "disclaimer": AI_DISCLAIMER_TEXT,
        }

        if hasattr(MarketAnalysisSummary, "model_validate"):
            return MarketAnalysisSummary.model_validate(payload)
        return MarketAnalysisSummary(**payload)
