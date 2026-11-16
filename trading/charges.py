"""
Indian Stock Market Transaction Costs and Regulatory Charges Calculator.

Accurately models Indian equity delivery friction:
- Brokerage: Flat ₹20 per executed order (Discount broker model: Zerodha, Groww).
- STT (Securities Transaction Tax): 0.1% on delivery turnover (both Buy & Sell).
- Exchange Turnover Charges (NSE): 0.00345% on turnover.
- SEBI Turnover Charges: ₹10 per crore (0.0001% of turnover).
- Stamp Duty: 0.015% on turnover (Applicable on Buy orders only).
- GST: 18% applied to (Brokerage + Exchange Charges + SEBI Charges).
- Simulated Slippage: Default 5 bps (0.05%) applied adverse to execution price.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


def round_inr(value: Decimal) -> Decimal:
    """Rounds to 2 decimal places (Paise precision in INR)."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TradeCostBreakdown:
    symbol: str
    side: str
    quantity: int
    requested_price: Decimal
    executed_price: Decimal
    turnover: Decimal
    slippage_impact_inr: Decimal
    brokerage_inr: Decimal
    stt_tax_inr: Decimal
    exchange_turnover_inr: Decimal
    sebi_charges_inr: Decimal
    stamp_duty_inr: Decimal
    gst_inr: Decimal
    total_charges_inr: Decimal
    net_cash_impact_inr: Decimal


def calculate_trade_friction(
    symbol: str,
    side: str,
    quantity: int,
    price: Decimal,
    slippage_bps: float = 5.0,
    brokerage_flat_inr: Decimal = Decimal("20.00"),
    stt_rate: Decimal = Decimal("0.001"),
    exchange_rate: Decimal = Decimal("0.0000345"),
    sebi_rate: Decimal = Decimal("0.000001"),
    stamp_duty_rate: Decimal = Decimal("0.00015"),
    gst_rate: Decimal = Decimal("0.18"),
) -> TradeCostBreakdown:
    """
    Calculates detailed execution price, slippage, and Indian regulatory charges.
    
    For a BUY order:
      - Slippage increases executed price (adverse fill).
      - Net cash deducted = (Quantity * Executed Price) + Total Charges.
      - Stamp duty applies.
      
    For a SELL order:
      - Slippage decreases executed price (adverse fill).
      - Net cash credited = (Quantity * Executed Price) - Total Charges.
      - Stamp duty is 0.
    """
    side_normalized = side.upper()
    if side_normalized not in ("BUY", "SELL"):
        raise ValueError(f"Invalid trade side: {side}. Must be 'BUY' or 'SELL'.")
    if quantity <= 0:
        raise ValueError(f"Quantity must be positive integer. Got: {quantity}")

    # 1. Apply simulated slippage
    # 1 bps = 0.0001 (e.g. 5 bps = 0.0005)
    slippage_factor = Decimal(str(slippage_bps / 10000.0))
    if side_normalized == "BUY":
        executed_price = round_inr(price * (Decimal("1.0") + slippage_factor))
        slippage_impact = round_inr((executed_price - price) * Decimal(quantity))
    else:
        executed_price = round_inr(price * (Decimal("1.0") - slippage_factor))
        slippage_impact = round_inr((price - executed_price) * Decimal(quantity))

    # 2. Turnover based on executed fill
    turnover = round_inr(executed_price * Decimal(quantity))

    # 3. Regulatory and broker charges
    brokerage = round_inr(brokerage_flat_inr)
    stt_tax = round_inr(turnover * stt_rate)
    exchange_turnover = round_inr(turnover * exchange_rate)
    sebi_charges = round_inr(turnover * sebi_rate)

    # Stamp duty is charged only on buy side turnover in India
    stamp_duty = round_inr(turnover * stamp_duty_rate) if side_normalized == "BUY" else Decimal("0.00")

    # GST is 18% on (Brokerage + Exchange turnover fees + SEBI charges)
    gst_taxable_amount = brokerage + exchange_turnover + sebi_charges
    gst = round_inr(gst_taxable_amount * gst_rate)

    total_charges = round_inr(brokerage + stt_tax + exchange_turnover + sebi_charges + stamp_duty + gst)

    # 4. Total cash impact
    if side_normalized == "BUY":
        net_cash_impact = round_inr(turnover + total_charges)
    else:
        net_cash_impact = round_inr(turnover - total_charges)

    return TradeCostBreakdown(
        symbol=symbol.upper(),
        side=side_normalized,
        quantity=quantity,
        requested_price=round_inr(price),
        executed_price=executed_price,
        turnover=turnover,
        slippage_impact_inr=slippage_impact,
        brokerage_inr=brokerage,
        stt_tax_inr=stt_tax,
        exchange_turnover_inr=exchange_turnover,
        sebi_charges_inr=sebi_charges,
        stamp_duty_inr=stamp_duty,
        gst_inr=gst,
        total_charges_inr=total_charges,
        net_cash_impact_inr=net_cash_impact,
    )
