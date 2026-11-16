"""
Pydantic and Data Schemas for Gemini-Powered Structured Market Analysis.

Guarantees:
- Schema-validated structured outputs.
- Explicit non-hallucination guardrails.
- Mandatory institutional disclaimer: AI confidence is not a probability of profit.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


AI_DISCLAIMER_TEXT = (
    "DISCLAIMER: AI-generated market analysis is provided solely for educational and paper-trading research. "
    "It is NOT financial advice, does NOT place real orders, and guarantees zero profit. "
    "AI confidence reflects indicator clarity and confluence, NOT the mathematical probability of a winning trade. "
    "Deterministic risk limits, stop-loss orders, and 1% capital allocation must always be enforced."
)


if HAS_PYDANTIC:
    class MarketAnalysisSummary(BaseModel):
        """Schema-validated structured analysis output from Gemini AI."""
        symbol: str = Field(description="NSE Ticker symbol (e.g. RELIANCE, TCS)")
        analysis_timestamp_utc: str = Field(description="ISO 8601 UTC timestamp of analysis")
        trend_analysis: str = Field(description="Detailed evaluation of EMA 20 vs EMA 50 alignment and price action")
        momentum_analysis: str = Field(description="Evaluation of RSI 14 levels, momentum corridors, and overbought/oversold states")
        macd_interpretation: str = Field(description="Interpretation of MACD line, signal line, and histogram trajectory")
        vwap_relationship: str = Field(description="Relationship between current close and daily VWAP (institutional fair value)")
        confirming_signals: List[str] = Field(description="Bullet points of quantitative indicators supporting the setup")
        conflicting_signals: List[str] = Field(description="Bullet points of conflicting indicators or divergence risks")
        key_risks: List[str] = Field(description="Identified market, volatility, or support breakdown risks")
        ai_confidence_score: float = Field(
            description="Heuristic rating from 0.0 to 100.0 reflecting technical confluence clarity. NEVER a probability of profit."
        )
        ai_confidence_rationale: str = Field(
            description="Clear explanation of why this confidence score was assigned based on indicator harmony vs conflict."
        )
        recommended_action_opinion: str = Field(
            description="Informational opinion (e.g. 'FAVORS_ACCUMULATION', 'FAVORS_PATIENCE', 'FAVORS_PROFIT_TAKING')"
        )
        disclaimer: str = Field(default=AI_DISCLAIMER_TEXT)

else:
    @dataclass
    class MarketAnalysisSummary:  # type: ignore
        """Fallback dataclass schema for pre-container environments."""
        symbol: str
        analysis_timestamp_utc: str
        trend_analysis: str
        momentum_analysis: str
        macd_interpretation: str
        vwap_relationship: str
        confirming_signals: List[str]
        conflicting_signals: List[str]
        key_risks: List[str]
        ai_confidence_score: float
        ai_confidence_rationale: str
        recommended_action_opinion: str
        disclaimer: str = AI_DISCLAIMER_TEXT

        def model_dump(self) -> Dict[str, Any]:
            return {
                "symbol": self.symbol,
                "analysis_timestamp_utc": self.analysis_timestamp_utc,
                "trend_analysis": self.trend_analysis,
                "momentum_analysis": self.momentum_analysis,
                "macd_interpretation": self.macd_interpretation,
                "vwap_relationship": self.vwap_relationship,
                "confirming_signals": self.confirming_signals,
                "conflicting_signals": self.conflicting_signals,
                "key_risks": self.key_risks,
                "ai_confidence_score": self.ai_confidence_score,
                "ai_confidence_rationale": self.ai_confidence_rationale,
                "recommended_action_opinion": self.recommended_action_opinion,
                "disclaimer": self.disclaimer,
            }
