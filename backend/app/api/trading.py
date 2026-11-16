"""
Paper Trading Execution and Portfolio API Routes.

Exposes:
- Virtual Buy and Sell order placement with 1% risk budgeting.
- Real-time Position monitoring (Open & Closed positions).
- Portfolio equity, cash balance, and trade ledger history.
- Performance metrics (Win Rate, Profit Factor, Max Drawdown, Sharpe Ratio).
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.market_data.universe import universe_manager
from database.models import AccountModel, OrderModel, PositionModel, PositionStatus, PortfolioSnapshotModel
from database.session import get_db
from trading.engine import PaperTradingEngine
from trading.metrics import calculate_performance_metrics

router = APIRouter(prefix="/api/v1/trading", tags=["Paper Trading Engine"])


class BuyOrderRequest(BaseModel):
    symbol: str = Field(description="NSE Ticker symbol (e.g. RELIANCE, TCS)")
    price: float = Field(gt=0, description="Order execution / market price in INR")
    stop_loss_price: float = Field(gt=0, description="Mandatory protective stop loss price in INR")
    take_profit_price: Optional[float] = Field(default=None, gt=0, description="Target take profit price in INR")
    quantity: Optional[int] = Field(default=None, ge=1, description="Quantity. If omitted, sized via 1% risk rule")
    enforce_market_hours: bool = Field(default=True, description="Enforce 09:15-15:30 IST session rules")
    reason: str = Field(default="Manual Strategy Trigger", description="Order reason / rationale")


class ClosePositionRequest(BaseModel):
    exit_price: float = Field(gt=0, description="Exit price in INR")
    reason: str = Field(default="Manual Position Close", description="Reason for closure")


@router.post("/orders/buy", summary="Place Virtual Buy Order")
async def place_buy_order(
    payload: BuyOrderRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Executes a virtual BUY order:
    - Sized automatically via 1% equity risk constraint if quantity is omitted.
    - Validates market session hours and duplicate position constraints.
    - Applies simulated slippage and Indian transaction taxes (Brokerage, STT, GST, etc.).
    """
    clean_symbol = universe_manager.normalize_symbol(payload.symbol)
    if clean_symbol not in universe_manager.get_symbols():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{clean_symbol}' not found in active trading universe.",
        )

    price_dec = Decimal(str(round(payload.price, 2)))
    sl_dec = Decimal(str(round(payload.stop_loss_price, 2)))
    tp_dec = Decimal(str(round(payload.take_profit_price, 2))) if payload.take_profit_price else None

    success, order, err = await PaperTradingEngine.execute_buy(
        session=db,
        symbol=clean_symbol,
        price=price_dec,
        stop_loss_price=sl_dec,
        take_profit_price=tp_dec,
        quantity=payload.quantity,
        enforce_market_hours=payload.enforce_market_hours,
        reason=payload.reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order rejected by Risk Engine: {err}",
        )

    return {
        "status": "FILLED",
        "order_id": order.client_order_id,
        "symbol": order.symbol,
        "side": order.side.value,
        "quantity": order.quantity,
        "executed_price": float(order.executed_price),
        "turnover_inr": float(order.turnover_inr),
        "total_charges_inr": float(order.total_charges_inr),
        "net_cash_impact_inr": float(order.net_cash_impact_inr),
        "stop_loss": float(order.stop_loss_price),
        "take_profit": float(order.take_profit_price) if order.take_profit_price else None,
        "executed_at": order.executed_at.isoformat() if order.executed_at else None,
    }


@router.post("/positions/{position_id}/close", summary="Close Open Virtual Position")
async def close_position_route(
    position_id: int,
    payload: ClosePositionRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Manually closes an active virtual position at current market price.
    Calculates net realized P&L taking into account roundtrip Indian transaction charges.
    """
    exit_dec = Decimal(str(round(payload.exit_price, 2)))
    success, order, err = await PaperTradingEngine.close_position(
        session=db,
        position_id=position_id,
        exit_price=exit_dec,
        enforce_market_hours=False,  # Allow manual override closures
        reason=payload.reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to close position: {err}",
        )

    return {
        "status": "CLOSED",
        "order_id": order.client_order_id,
        "symbol": order.symbol,
        "quantity": order.quantity,
        "exit_price": float(order.executed_price),
        "turnover_inr": float(order.turnover_inr),
        "exit_charges_inr": float(order.total_charges_inr),
        "net_proceeds_inr": float(order.net_cash_impact_inr),
        "executed_at": order.executed_at.isoformat() if order.executed_at else None,
    }


@router.get("/positions", summary="List Virtual Positions")
async def list_positions(
    status_filter: Optional[str] = Query(None, regex="^(OPEN|CLOSED)$"),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Lists open and closed virtual positions with mark-to-market and P&L metrics."""
    account = await PaperTradingEngine.get_or_create_account(db)
    stmt = select(PositionModel).where(PositionModel.account_id == account.id)

    if status_filter:
        pos_status = PositionStatus.OPEN if status_filter == "OPEN" else PositionStatus.CLOSED
        stmt = stmt.where(PositionModel.status == pos_status)

    stmt = stmt.order_by(PositionModel.opened_at.desc())
    result = await db.execute(stmt)
    positions = result.scalars().all()

    return [
        {
            "id": p.id,
            "symbol": p.symbol,
            "exchange": p.exchange,
            "quantity": p.quantity,
            "entry_price": float(p.average_entry_price),
            "current_price": float(p.current_price),
            "stop_loss_price": float(p.stop_loss_price),
            "take_profit_price": float(p.take_profit_price) if p.take_profit_price else None,
            "status": p.status.value,
            "realized_pnl_inr": float(p.realized_pnl_inr),
            "unrealized_pnl_inr": float(p.unrealized_pnl_inr),
            "total_charges_incurred_inr": float(p.total_charges_incurred_inr),
            "opened_at": p.opened_at.isoformat(),
            "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        }
        for p in positions
    ]


@router.get("/orders", summary="List Order History")
async def list_orders(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Returns the chronological audit trail of all executed virtual paper orders."""
    account = await PaperTradingEngine.get_or_create_account(db)
    stmt = (
        select(OrderModel)
        .where(OrderModel.account_id == account.id)
        .order_by(OrderModel.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    return [
        {
            "id": o.id,
            "client_order_id": o.client_order_id,
            "symbol": o.symbol,
            "side": o.side.value,
            "quantity": o.quantity,
            "requested_price": float(o.requested_price),
            "executed_price": float(o.executed_price),
            "status": o.status.value,
            "turnover_inr": float(o.turnover_inr),
            "brokerage_inr": float(o.brokerage_inr),
            "stt_tax_inr": float(o.stt_tax_inr),
            "gst_inr": float(o.gst_inr),
            "total_charges_inr": float(o.total_charges_inr),
            "net_cash_impact_inr": float(o.net_cash_impact_inr),
            "reason": o.reason,
            "executed_at": o.executed_at.isoformat() if o.executed_at else None,
        }
        for o in orders
    ]


@router.get("/portfolio", summary="Get Portfolio Balance & State")
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Returns real-time account purchasing power, total equity, and open exposure."""
    account = await PaperTradingEngine.get_or_create_account(db)
    await PaperTradingEngine.update_portfolio_equity(db, account)

    # Count open positions
    open_res = await db.execute(
        select(PositionModel).where(
            PositionModel.account_id == account.id,
            PositionModel.status == PositionStatus.OPEN,
        )
    )
    open_positions = open_res.scalars().all()
    open_val = sum((p.current_price * Decimal(p.quantity) for p in open_positions), Decimal("0.00"))
    unrealized = sum((p.unrealized_pnl_inr for p in open_positions), Decimal("0.00"))

    # Closed positions realized P&L
    closed_res = await db.execute(
        select(PositionModel).where(
            PositionModel.account_id == account.id,
            PositionModel.status == PositionStatus.CLOSED,
        )
    )
    closed_positions = closed_res.scalars().all()
    realized = sum((p.realized_pnl_inr for p in closed_positions), Decimal("0.00"))

    return {
        "account_name": account.account_name,
        "currency": account.currency,
        "initial_capital_inr": float(account.initial_capital_inr),
        "cash_balance_inr": float(account.cash_balance_inr),
        "positions_market_value_inr": float(open_val),
        "equity_inr": float(account.equity_inr),
        "open_positions_count": len(open_positions),
        "total_realized_pnl_inr": float(realized),
        "total_unrealized_pnl_inr": float(unrealized),
        "total_pnl_inr": float(realized + unrealized),
        "return_on_initial_capital_pct": round(float((account.equity_inr - account.initial_capital_inr) / account.initial_capital_inr * 100.0), 2),
    }


@router.get("/metrics", summary="Get Institutional Performance Metrics")
async def get_performance_metrics_route(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Computes Win Rate, Profit Factor, Maximum Drawdown, and Sharpe Ratio
    across trade ledger and portfolio snapshots.
    """
    account = await PaperTradingEngine.get_or_create_account(db)

    # Fetch closed positions
    closed_res = await db.execute(
        select(PositionModel)
        .where(
            PositionModel.account_id == account.id,
            PositionModel.status == PositionStatus.CLOSED,
        )
        .order_by(PositionModel.closed_at.asc())
    )
    closed = closed_res.scalars().all()

    realized_pnls = [p.realized_pnl_inr for p in closed]
    charges = [p.total_charges_incurred_inr for p in closed]

    # Fetch snapshots
    snap_res = await db.execute(
        select(PortfolioSnapshotModel)
        .where(PortfolioSnapshotModel.account_id == account.id)
        .order_by(PortfolioSnapshotModel.timestamp.asc())
    )
    snapshots = snap_res.scalars().all()
    equity_curve = [s.equity_inr for s in snapshots] or [account.equity_inr]

    metrics = calculate_performance_metrics(
        realized_pnls=realized_pnls,
        charges_paid=charges,
        equity_curve=equity_curve,
    )

    return metrics.to_dict()
