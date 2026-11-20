"""
Virtual Exchange Matching Engine & Simulated Exchange-Side GTT Bracket Orders.

Provides:
- Virtual Good-Till-Triggered (GTT) Stop-Loss and Take-Profit bracket order management.
- Decouples strategy signal generation from exchange order matching.
- Sub-second tick evaluation with realistic market order slippage.
- Guaranteed trigger execution even if the primary AI strategy engine encounters network lag.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import enum
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GTTOrderType(str, enum.Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class GTTOrderStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    CANCELLED = "CANCELLED"


@dataclass
class VirtualGTTOrder:
    order_id: str
    account_id: int
    position_id: int
    symbol: str
    order_type: GTTOrderType
    trigger_price: Decimal
    limit_price: Optional[Decimal]
    quantity: int
    status: GTTOrderStatus = GTTOrderStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggered_at: Optional[datetime] = None
    execution_price: Optional[Decimal] = None
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "account_id": self.account_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "order_type": self.order_type.value,
            "trigger_price": float(self.trigger_price),
            "limit_price": float(self.limit_price) if self.limit_price else None,
            "quantity": self.quantity,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "execution_price": float(self.execution_price) if self.execution_price else None,
            "reason": self.reason,
        }


@dataclass
class GTTTriggerEvent:
    order: VirtualGTTOrder
    exit_price: Decimal
    trigger_reason: str


class VirtualExchangeMatchingEngine:
    """
    Simulates institutional exchange matching engine with persistent bracket orders.
    Matches live ticks against registered GTT stop-loss and take-profit levels.
    """

    def __init__(self, slippage_bps: float = 5.0) -> None:
        self.slippage_bps = slippage_bps
        # In-memory index of active GTT orders by position_id
        self._orders: Dict[str, VirtualGTTOrder] = {}

    def register_bracket_order(
        self,
        account_id: int,
        position_id: int,
        symbol: str,
        quantity: int,
        stop_loss_price: Decimal,
        take_profit_price: Optional[Decimal] = None,
    ) -> List[VirtualGTTOrder]:
        """Registers exchange-side Stop-Loss and Take-Profit triggers for a position."""
        created_orders = []

        # Cancel any preexisting active orders for this position
        self.cancel_orders_for_position(position_id, reason="New bracket order registration")

        # 1. Stop-Loss GTT Order
        sl_id = f"GTT-SL-{symbol}-{position_id}"
        sl_order = VirtualGTTOrder(
            order_id=sl_id,
            account_id=account_id,
            position_id=position_id,
            symbol=symbol,
            order_type=GTTOrderType.STOP_LOSS,
            trigger_price=stop_loss_price,
            limit_price=stop_loss_price,
            quantity=quantity,
            reason="Protective Stop-Loss Bracket",
        )
        self._orders[sl_id] = sl_order
        created_orders.append(sl_order)

        # 2. Take-Profit GTT Order (Optional)
        if take_profit_price and take_profit_price > Decimal("0.00"):
            tp_id = f"GTT-TP-{symbol}-{position_id}"
            tp_order = VirtualGTTOrder(
                order_id=tp_id,
                account_id=account_id,
                position_id=position_id,
                symbol=symbol,
                order_type=GTTOrderType.TAKE_PROFIT,
                trigger_price=take_profit_price,
                limit_price=take_profit_price,
                quantity=quantity,
                reason="Target Take-Profit Bracket",
            )
            self._orders[tp_id] = tp_order
            created_orders.append(tp_order)

        logger.info(
            f"Virtual Exchange registered {len(created_orders)} bracket order(s) for {symbol} "
            f"[Pos #{position_id}, SL={stop_loss_price}, TP={take_profit_price}]"
        )
        return created_orders

    def cancel_orders_for_position(self, position_id: int, reason: str = "Position closed") -> int:
        """Cancels all active GTT orders associated with a position."""
        cancelled_count = 0
        for order in list(self._orders.values()):
            if order.position_id == position_id and order.status == GTTOrderStatus.ACTIVE:
                order.status = GTTOrderStatus.CANCELLED
                order.reason = reason
                cancelled_count += 1
        return cancelled_count

    def process_tick(self, symbol: str, current_price: Decimal) -> List[GTTTriggerEvent]:
        """
        Evaluates incoming real market tick against all active GTT orders for the symbol.
        Returns triggered events with simulated slippage.
        """
        triggers: List[GTTTriggerEvent] = []
        slippage_factor = Decimal(str(self.slippage_bps / 10000.0))

        for order in list(self._orders.values()):
            if order.symbol != symbol or order.status != GTTOrderStatus.ACTIVE:
                continue

            is_triggered = False
            trigger_reason = ""

            # Stop-Loss Check: Triggers if price is less than or equal to stop trigger
            if order.order_type == GTTOrderType.STOP_LOSS:
                if current_price <= order.trigger_price:
                    is_triggered = True
                    trigger_reason = f"EXCHANGE_SL_TRIGGERED (Price {current_price} <= SL {order.trigger_price})"

            # Take-Profit Check: Triggers if price is greater than or equal to TP trigger
            elif order.order_type == GTTOrderType.TAKE_PROFIT:
                if current_price >= order.trigger_price:
                    is_triggered = True
                    trigger_reason = f"EXCHANGE_TP_TRIGGERED (Price {current_price} >= TP {order.trigger_price})"

            if is_triggered:
                # Calculate executed price with realistic sell slippage (slightly below current)
                exec_price = (current_price * (Decimal("1.0") - slippage_factor)).quantize(Decimal("0.05"))
                order.status = GTTOrderStatus.TRIGGERED
                order.triggered_at = datetime.now(timezone.utc)
                order.execution_price = exec_price
                order.reason = trigger_reason

                triggers.append(GTTTriggerEvent(order=order, exit_price=exec_price, trigger_reason=trigger_reason))

                # Automatically cancel the opposite order of the bracket (OCO - One Cancels the Other)
                for other in list(self._orders.values()):
                    if (
                        other.position_id == order.position_id
                        and other.order_id != order.order_id
                        and other.status == GTTOrderStatus.ACTIVE
                    ):
                        other.status = GTTOrderStatus.CANCELLED
                        other.reason = f"OCO Cancelled: Opposite leg {order.order_id} triggered"

        return triggers

    def get_active_orders(self, symbol: Optional[str] = None) -> List[VirtualGTTOrder]:
        """Returns all currently active GTT bracket orders."""
        orders = [o for o in self._orders.values() if o.status == GTTOrderStatus.ACTIVE]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def clear(self) -> None:
        """Clears all in-memory GTT order state."""
        self._orders.clear()


# Global singleton instance
virtual_exchange = VirtualExchangeMatchingEngine()
