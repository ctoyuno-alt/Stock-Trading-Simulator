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
import math
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


def validate_sector_concentration(
    symbol: str,
    existing_symbols: Set[str],
    max_per_sector: int = 2,
) -> tuple[bool, Optional[str]]:
    """Enforces that no more than `max_per_sector` positions belong to the same industry sector."""
    try:
        from backend.app.market_data.universe import universe_manager
        cand_inst = universe_manager.get_instrument(symbol)
        cand_sector = cand_inst.sector if cand_inst else None
        if not cand_sector:
            return True, None

        sector_count = 0
        for s in existing_symbols:
            inst = universe_manager.get_instrument(s)
            if inst and inst.sector == cand_sector:
                sector_count += 1

        if sector_count >= max_per_sector:
            return False, (
                f"Sector concentration limit reached: {sector_count} position(s) already open in "
                f"'{cand_sector}' (Maximum allowed: {max_per_sector})."
            )
    except Exception:
        pass
    return True, None


def check_daily_circuit_breaker(
    current_equity: Decimal,
    daily_starting_equity: Optional[Decimal],
    max_daily_drawdown_pct: float = 0.02,
) -> tuple[bool, Optional[str]]:
    """
    Evaluates whether account daily loss has breached the daily circuit breaker limit.
    Default: -2.0% daily maximum loss.
    """
    if daily_starting_equity is None or daily_starting_equity <= Decimal("0.00"):
        return True, None

    if current_equity < daily_starting_equity:
        loss_inr = daily_starting_equity - current_equity
        loss_pct = float(loss_inr / daily_starting_equity)
        if loss_pct >= max_daily_drawdown_pct:
            return False, (
                f"DAILY CIRCUIT BREAKER TRIPPED: Current daily drawdown of {loss_pct*100:.2f}% "
                f"exceeds maximum allowed limit of {max_daily_drawdown_pct*100:.2f}%. All new entries halted."
            )
    return True, None


def validate_order_risk(
    symbol: str,
    side: str,
    quantity: int,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    open_positions_count: int,
    existing_symbols: Set[str],
    enforce_market_hours: bool = True,
    market: Optional[str] = None,
    current_equity: Optional[Decimal] = None,
    daily_starting_equity: Optional[Decimal] = None,
    max_per_sector: int = 2,
    max_daily_drawdown_pct: float = 0.02,
) -> RiskValidationResult:
    """
    Validates comprehensive pre-trade risk constraints:
    - Kill switch status.
    - Daily circuit breaker status (-2.0% drawdown).
    - Sector concentration limits (max 2 per sector).
    - Market session & holiday check (NSE or US).
    - Concurrent position limit.
    - Duplicate position prevention.
    - Minimum stop loss distance.
    """
    rejections: List[str] = []

    # 1. Kill Switch
    if settings.PAPER_TRADING_KILL_SWITCH:
        rejections.append("Order rejected: Emergency Paper Trading Kill Switch is ACTIVE.")

    # 2. Daily Circuit Breaker Check
    if current_equity and daily_starting_equity:
        is_cb_ok, cb_err = check_daily_circuit_breaker(
            current_equity=current_equity,
            daily_starting_equity=daily_starting_equity,
            max_daily_drawdown_pct=max_daily_drawdown_pct,
        )
        if not is_cb_ok and cb_err:
            rejections.append(f"Order rejected: {cb_err}")

    # 3. Market Session Hours & Holidays
    if enforce_market_hours:
        from backend.app.market_data.universe import universe_manager
        target_market = (market or universe_manager.get_market_for_symbol(symbol)).upper()
        is_open, reason = is_market_open(market=target_market)
        if not is_open:
            rejections.append(f"Order rejected: Outside market hours ({reason}).")

    # 4. Quantity check
    if quantity <= 0:
        rejections.append(f"Order rejected: Quantity must be positive integer (got {quantity}).")

    # 5. Long-only Buy validation
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

        # Sector Concentration Check
        is_sector_ok, sector_err = validate_sector_concentration(
            symbol=clean_symbol,
            existing_symbols=existing_symbols,
            max_per_sector=max_per_sector,
        )
        if not is_sector_ok and sector_err:
            rejections.append(f"Order rejected: {sector_err}")

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


def calculate_rr_preview(entry: float, stop_loss: float, take_profit: float) -> dict:
    """Calculates Risk:Reward ratio and validation status for UI preview."""
    try:
        e, sl, tp = float(entry), float(stop_loss), float(take_profit)
    except (ValueError, TypeError):
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Invalid numerical parameters."}
    if math.isnan(e) or math.isnan(sl) or math.isnan(tp) or math.isinf(e) or math.isinf(sl) or math.isinf(tp):
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Parameters cannot be NaN or infinite."}
    if e <= 0:
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Entry price must be positive."}
    if sl >= e:
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Stop-loss must be strictly below entry price."}
    if tp <= e:
        return {"is_valid": False, "rr_ratio": 0.0, "reason": "Take-profit must be strictly above entry price."}

    risk_per_sh = e - sl
    reward_per_sh = tp - e
    rr_ratio = reward_per_sh / risk_per_sh if risk_per_sh > 0 else 0.0
    sl_pct = (risk_per_sh / e) * 100.0
    tp_pct = (reward_per_sh / e) * 100.0

    if rr_ratio >= 2.0:
        tier = "OPTIMAL"
        status_color = "#00E676"  # Green
    elif rr_ratio >= 1.5:
        tier = "SUBOPTIMAL"
        status_color = "#FF9900"  # Amber
    else:
        tier = "REJECTED"
        status_color = "#FF3366"  # Red

    return {
        "is_valid": True,
        "rr_ratio": round(rr_ratio, 2),
        "risk_per_share": round(risk_per_sh, 2),
        "reward_per_share": round(reward_per_sh, 2),
        "stop_loss_pct": round(sl_pct, 2),
        "take_profit_pct": round(tp_pct, 2),
        "tier": tier,
        "status_color": status_color,
    }

