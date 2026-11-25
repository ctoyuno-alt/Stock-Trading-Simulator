"""
Transaction Costs and Regulatory Charges Calculator for Indian (NSE) and US (NYSE/NASDAQ) Markets.

Accurately models:
1. Indian Equity Delivery Friction:
   - Brokerage: Flat ₹20 per executed order (Discount broker model: Zerodha, Groww).
   - STT (Securities Transaction Tax): 0.1% on delivery turnover (both Buy & Sell).
   - Exchange Turnover Charges (NSE): 0.00345% on turnover.
   - SEBI Turnover Charges: ₹10 per crore (0.0001% of turnover).
   - Stamp Duty: 0.015% on turnover (Applicable on Buy orders only).
   - GST: 18% applied to (Brokerage + Exchange Charges + SEBI Charges).
   - Simulated Slippage: Default 5 bps (0.05%) applied adverse to execution price.

2. US Equity Trading Friction (Zero-Commission Retail Model: Schwab, Fidelity, Robinhood):
   - Brokerage: $0.00 per executed order.
   - SEC Section 31 Fee: 0.0000278 * turnover on SELL orders only (min $0.01).
   - FINRA Trading Activity Fee (TAF): $0.000166 per share on SELL orders only (min $0.01, max $8.30).
   - Stamp Duty / GST / SEBI: $0.00.
   - Simulated Slippage: Default 5 bps (0.05%) applied adverse to execution price.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


def round_inr(value: Decimal) -> Decimal:
    """Rounds to 2 decimal places (standard cent/paise precision)."""
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
    Calculates detailed execution price, slippage, and Indian regulatory charges (NSE).
    
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

    # 1. Apply simulated slippage (5 bps = 0.0005)
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


def calculate_us_trade_friction(
    symbol: str,
    side: str,
    quantity: int,
    price: Decimal,
    slippage_bps: float = 5.0,
    sec_fee_rate: Decimal = Decimal("0.0000278"),       # SEC Section 31 Fee on sales
    finra_taf_per_share: Decimal = Decimal("0.000166"),  # FINRA TAF on sales
    finra_taf_max: Decimal = Decimal("8.30"),
) -> TradeCostBreakdown:
    """
    Calculates execution friction and US regulatory charges (SEC & FINRA) in USD.
    
    Zero-commission broker model ($0.00 brokerage).
    Slippage applied adverse to requested price.
    Regulatory fees (SEC Section 31 + FINRA TAF) apply strictly to SELL orders:
      - SEC Fee: turnover * 0.0000278 (min $0.01)
      - FINRA TAF: quantity * 0.000166 (min $0.01, max $8.30)
    """
    side_normalized = side.upper()
    if side_normalized not in ("BUY", "SELL"):
        raise ValueError(f"Invalid trade side: {side}. Must be 'BUY' or 'SELL'.")
    if quantity <= 0:
        raise ValueError(f"Quantity must be positive integer. Got: {quantity}")

    # 1. Apply simulated slippage
    slippage_factor = Decimal(str(slippage_bps / 10000.0))
    if side_normalized == "BUY":
        executed_price = round_inr(price * (Decimal("1.0") + slippage_factor))
        slippage_impact = round_inr((executed_price - price) * Decimal(quantity))
    else:
        executed_price = round_inr(price * (Decimal("1.0") - slippage_factor))
        slippage_impact = round_inr((price - executed_price) * Decimal(quantity))

    # 2. Turnover based on executed fill
    turnover = round_inr(executed_price * Decimal(quantity))

    # 3. US Regulatory Charges (apply only on SELL side)
    brokerage = Decimal("0.00")
    if side_normalized == "SELL":
        # SEC Section 31 fee (minimum $0.01)
        raw_sec = turnover * sec_fee_rate
        sec_fee = max(round_inr(raw_sec), Decimal("0.01")) if turnover > Decimal("0.00") else Decimal("0.00")

        # FINRA TAF (min $0.01, max $8.30)
        raw_finra = Decimal(quantity) * finra_taf_per_share
        finra_fee = min(max(round_inr(raw_finra), Decimal("0.01")), finra_taf_max)
    else:
        sec_fee = Decimal("0.00")
        finra_fee = Decimal("0.00")

    total_charges = round_inr(brokerage + sec_fee + finra_fee)

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
        stt_tax_inr=sec_fee,              # Stores SEC Section 31 fee
        exchange_turnover_inr=finra_fee,    # Stores FINRA TAF fee
        sebi_charges_inr=Decimal("0.00"),
        stamp_duty_inr=Decimal("0.00"),
        gst_inr=Decimal("0.00"),
        total_charges_inr=total_charges,
        net_cash_impact_inr=net_cash_impact,
    )


def calculate_market_trade_friction(
    symbol: str,
    side: str,
    quantity: int,
    price: Decimal,
    market: Optional[str] = None,
    slippage_bps: float = 5.0,
    **kwargs,
) -> TradeCostBreakdown:
    """
    Unified entrypoint that dynamically routes trade friction calculation based on market.
    """
    try:
        from backend.app.market_data.universe import universe_manager
        target_market = (market or universe_manager.get_market_for_symbol(symbol)).upper()
    except (ImportError, Exception):
        target_market = (market or "IN").upper()
    if target_market == "US":
        return calculate_us_trade_friction(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            slippage_bps=slippage_bps,
        )

    return calculate_trade_friction(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        slippage_bps=slippage_bps,
        **kwargs,
    )
