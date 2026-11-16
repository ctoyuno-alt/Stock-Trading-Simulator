"""
Risk Management and Quantitative Position Sizing Engine.

Enforces:
- 1.0% Virtual Equity Risk per position:
    Quantity = min(
        floor((Equity * 0.01) / (Entry - StopLoss)),
        floor((Equity * MaxAllocationPct) / Entry),
        floor(Cash / Entry)
    )
- Mandatory stop-loss rules.
- Maximum concurrent open positions (default 5).
- Duplicate position prevention per instrument.
- Exchange trading session & holiday enforcement.
- Global Emergency Kill Switch verification.
"""

from dataclasses import dataclass
from decimal import Decimal
import logging
from typing import List, Optional, Set
from backend.app.core.config import get_settings
from backend.app.core.market_schedule import is_market_open

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class PositionSizeResult:
    quantity: int
    entry_price: Decimal
    stop_loss_price: Decimal
    risk_per_share_inr: Decimal
    total_risk_inr: Decimal
    capital_required_inr: Decimal
    allocation_pct: float
    is_approved: bool
    rejection_reason: Optional[str] = None


@dataclass
class RiskValidationResult:
    is_valid: bool
    rejection_reasons: List[str]


def calculate_position_size(
    equity: Decimal,
    available_cash: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    max_risk_pct: float = 0.01,
    max_allocation_pct: float = 0.20,
) -> PositionSizeResult:
    """
    Computes optimal integer share quantity based on the 1% equity risk constraint,
    portfolio concentration limits, and available purchasing power.
    """
    if entry_price <= Decimal("0.00"):
        return PositionSizeResult(
            quantity=0,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            risk_per_share_inr=Decimal("0.00"),
            total_risk_inr=Decimal("0.00"),
            capital_required_inr=Decimal("0.00"),
            allocation_pct=0.0,
            is_approved=False,
            rejection_reason="Entry price must be strictly positive.",
        )

    if stop_loss_price >= entry_price:
        return PositionSizeResult(
            quantity=0,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            risk_per_share_inr=Decimal("0.00"),
            total_risk_inr=Decimal("0.00"),
            capital_required_inr=Decimal("0.00"),
            allocation_pct=0.0,
            is_approved=False,
            rejection_reason="Stop-loss price must be strictly below entry price for long positions.",
        )

    # 1. Risk budget in INR (1.0% of virtual equity)
    max_risk_inr = equity * Decimal(str(max_risk_pct))
    risk_per_share = entry_price - stop_loss_price

    # 2. Maximum shares allowed by 1% risk budget
    qty_risk_limit = int(max_risk_inr // risk_per_share)

    # 3. Maximum shares allowed by concentration cap (e.g. 20% of equity)
    max_capital_allocation = equity * Decimal(str(max_allocation_pct))
    qty_allocation_limit = int(max_capital_allocation // entry_price)

    # 4. Maximum shares purchasable with available cash
    qty_cash_limit = int(available_cash // entry_price)

    # Final approved quantity is the most conservative bound
    final_quantity = min(qty_risk_limit, qty_allocation_limit, qty_cash_limit)

    if final_quantity <= 0:
        if qty_cash_limit <= 0:
            reason = f"Insufficient cash (₹{available_cash}) to purchase 1 share @ ₹{entry_price}."
        elif qty_risk_limit <= 0:
            reason = (
                f"1% risk budget (₹{max_risk_inr:.2f}) is smaller than single-share stop-loss distance "
                f"(₹{risk_per_share:.2f})."
            )
        else:
            reason = "Position size rounded down to zero under risk and concentration constraints."

        return PositionSizeResult(
            quantity=0,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            risk_per_share_inr=risk_per_share,
            total_risk_inr=Decimal("0.00"),
            capital_required_inr=Decimal("0.00"),
            allocation_pct=0.0,
            is_approved=False,
            rejection_reason=reason,
        )

    capital_required = (entry_price * Decimal(final_quantity)).quantize(Decimal("0.01"))
    total_risk = (risk_per_share * Decimal(final_quantity)).quantize(Decimal("0.01"))
    allocation_pct = float((capital_required / equity) * Decimal("100.0"))

    return PositionSizeResult(
        quantity=final_quantity,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        risk_per_share_inr=risk_per_share,
        total_risk_inr=total_risk,
        capital_required_inr=capital_required,
        allocation_pct=allocation_pct,
        is_approved=True,
        rejection_reason=None,
    )


def validate_order_risk(
    symbol: str,
    side: str,
    quantity: int,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    open_positions_count: int,
    existing_symbols: Set[str],
    enforce_market_hours: bool = True,
) -> RiskValidationResult:
    """
    Validates comprehensive pre-trade risk constraints:
    - Kill switch status.
    - Market session & holiday check.
    - Concurrent position limit.
    - Duplicate position prevention.
    - Minimum stop loss distance.
    """
    rejections: List[str] = []

    # 1. Kill Switch
    if settings.PAPER_TRADING_KILL_SWITCH:
        rejections.append("Order rejected: Emergency Paper Trading Kill Switch is ACTIVE.")

    # 2. Market Session Hours & Holidays
    if enforce_market_hours:
        is_open, reason = is_market_open()
        if not is_open:
            rejections.append(f"Order rejected: Outside market hours ({reason}).")

    # 3. Quantity check
    if quantity <= 0:
        rejections.append(f"Order rejected: Quantity must be positive integer (got {quantity}).")

    # 4. Long-only Buy validation
    if side.upper() == "BUY":
        # Max open positions
        if open_positions_count >= settings.MAX_OPEN_POSITIONS:
            rejections.append(
                f"Order rejected: Maximum concurrent open positions ({settings.MAX_OPEN_POSITIONS}) reached."
            )

        # Duplicate order / position check
        clean_symbol = symbol.strip().upper()
        if clean_symbol in existing_symbols:
            rejections.append(f"Order rejected: An open position already exists for symbol '{clean_symbol}'.")

        # Mandatory stop-loss check
        if stop_loss_price <= Decimal("0.00"):
            rejections.append("Order rejected: Every position must have a valid positive stop-loss.")
        elif stop_loss_price >= entry_price:
            rejections.append("Order rejected: Stop-loss must be lower than entry price.")
        else:
            sl_pct = float((entry_price - stop_loss_price) / entry_price)
            if sl_pct < settings.MIN_STOP_LOSS_PCT:
                rejections.append(
                    f"Order rejected: Stop-loss distance ({sl_pct*100:.2f}%) is tighter than minimum required ({settings.MIN_STOP_LOSS_PCT*100:.2f}%)."
                )

    return RiskValidationResult(
        is_valid=len(rejections) == 0,
        rejection_reasons=rejections,
    )
