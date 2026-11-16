"""
Base Definitions and Data Structures for Quantitative Trading Strategies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import enum
from typing import Any, Dict, List, Optional, Sequence
from backend.app.market_data.base import Candle
from indicators.base import IndicatorSnapshot


class SignalAction(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStrength(str, enum.Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"


@dataclass
class TradeSignal:
    """
    Structured quantitative trading signal emitted by a strategy engine.
    Encapsulates price targets, risk management limits, and deterministic rationale.
    """
    symbol: str
    timestamp: datetime
    action: SignalAction
    strength: SignalStrength
    entry_price: Decimal
    suggested_stop_loss: Decimal
    suggested_take_profit: Decimal
    risk_reward_ratio: float
    stop_loss_pct: float
    target_profit_pct: float
    primary_trigger: str
    confirming_factors: List[str] = field(default_factory=list)
    conflicting_factors: List[str] = field(default_factory=list)
    technical_score: float = 50.0  # Normalized score from 0.0 (Extremely Bearish) to 100.0 (Extremely Bullish)
    snapshot: Optional[IndicatorSnapshot] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "strength": self.strength.value,
            "entry_price": float(self.entry_price),
            "suggested_stop_loss": float(self.suggested_stop_loss),
            "suggested_take_profit": float(self.suggested_take_profit),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "stop_loss_pct": round(self.stop_loss_pct, 2),
            "target_profit_pct": round(self.target_profit_pct, 2),
            "primary_trigger": self.primary_trigger,
            "confirming_factors": self.confirming_factors,
            "conflicting_factors": self.conflicting_factors,
            "technical_score": round(self.technical_score, 1),
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
        }


class BaseStrategy(ABC):
    """Abstract interface for all deterministic quantitative strategy models."""

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Name of the strategy."""
        pass

    @abstractmethod
    def generate_signal(
        self,
        symbol: str,
        candles: Sequence[Candle],
    ) -> TradeSignal:
        """Evaluates latest market state and returns a structured TradeSignal."""
        pass

    @abstractmethod
    def generate_signals_history(
        self,
        symbol: str,
        candles: Sequence[Candle],
    ) -> List[TradeSignal]:
        """Evaluates historical bars sequentially without look-ahead bias."""
        pass
