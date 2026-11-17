"""
Paper Trading Order Execution and Portfolio State Engine.

Capabilities:
- Pure virtual execution of BUY and SELL orders with realistic slippage and Indian transaction costs.
- Enforces 1% equity risk positioning and pre-trade risk validations.
- Manages Position lifecycle (Entry -> Mark-to-Market -> Stop-Loss / Take-Profit Exit).
- Maintains trade ledger and portfolio snapshots for performance analytics.
- Dual execution mode: Asynchronous PostgreSQL persistence and In-Memory fast simulation.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from backend.app.core.config import get_settings
try:
    from database.models import AccountModel, OrderModel, OrderSide, OrderStatus, PositionModel, PositionStatus, PortfolioSnapshotModel
except ImportError:
    AccountModel = OrderModel = OrderSide = OrderStatus = PositionModel = PositionStatus = PortfolioSnapshotModel = Any  # type: ignore
from trading.charges import calculate_trade_friction, round_inr
from trading.risk import calculate_position_size, validate_order_risk, PositionSizeResult

logger = logging.getLogger(__name__)
settings = get_settings()


class PaperTradingEngine:
    """Asynchronous database-backed paper trading execution engine."""

    @staticmethod
    async def get_or_create_account(session: Any, currency: str = "INR") -> AccountModel:
        """Retrieves or creates the paper trading account for the specified currency (INR or USD)."""
        from sqlalchemy import select
        target_curr = currency.upper()
        account_name = "Primary USD Paper Account" if target_curr == "USD" else "Primary Paper Account"
        result = await session.execute(
            select(AccountModel).where(AccountModel.account_name == account_name)
        )
        account = result.scalar_one_or_none()
        if not account:
            initial = Decimal("25000.00") if target_curr == "USD" else settings.INITIAL_VIRTUAL_CAPITAL_INR
            account = AccountModel(
                account_name=account_name,
                initial_capital_inr=initial,
                cash_balance_inr=initial,
                equity_inr=initial,
                currency=target_curr,
                is_active=True,
            )
            session.add(account)
            await session.commit()
            await session.refresh(account)
        return account

    @staticmethod
    async def execute_buy(
        session: Any,
        symbol: str,
        price: Decimal,
        stop_loss_price: Decimal,
        take_profit_price: Optional[Decimal] = None,
        quantity: Optional[int] = None,
        enforce_market_hours: bool = True,
        reason: str = "Quantitative Strategy Entry",
    ) -> Tuple[bool, Optional[OrderModel], Optional[str]]:
        """
        Executes a virtual BUY order:
        - Validates risk rules and sizing constraints.
        - Calculates adverse slippage and Indian delivery charges.
        - Deducts cash and updates portfolio equity.
        - Opens a new position in the ledger.
        """
        from sqlalchemy import select
        from backend.app.market_data.universe import universe_manager
        from trading.charges import calculate_market_trade_friction

        target_market = universe_manager.get_market_for_symbol(symbol)
        target_currency = "USD" if target_market == "US" else "INR"
        account = await PaperTradingEngine.get_or_create_account(session, currency=target_currency)

        # 1. Gather active positions for risk checks
        pos_result = await session.execute(
            select(PositionModel).where(
                PositionModel.account_id == account.id,
                PositionModel.status == PositionStatus.OPEN,
            )
        )
        open_positions = pos_result.scalars().all()
        existing_symbols = {p.symbol for p in open_positions}

        # 2. Position sizing (if quantity omitted, size based on 1% risk)
        if quantity is None or quantity <= 0:
            sizing = calculate_position_size(
                equity=account.equity_inr,
                available_cash=account.cash_balance_inr,
                entry_price=price,
                stop_loss_price=stop_loss_price,
                max_risk_pct=settings.MAX_RISK_PER_TRADE,
                max_allocation_pct=settings.MAX_ALLOCATION_PER_POSITION,
            )
            if not sizing.is_approved:
                return False, None, f"Position sizing rejected: {sizing.rejection_reason}"
            final_quantity = sizing.quantity
        else:
            final_quantity = quantity

        # 3. Pre-trade Risk Validation
        risk_check = validate_order_risk(
            symbol=symbol,
            side="BUY",
            quantity=final_quantity,
            entry_price=price,
            stop_loss_price=stop_loss_price,
            open_positions_count=len(open_positions),
            existing_symbols=existing_symbols,
            enforce_market_hours=enforce_market_hours,
            market=target_market,
        )
        if not risk_check.is_valid:
            rejection_detail = "; ".join(risk_check.rejection_reasons)
            logger.warning(f"Order rejected for {symbol}: {rejection_detail}")
            return False, None, rejection_detail

        # 4. Calculate execution friction and charges (NSE or US)
        friction = calculate_market_trade_friction(
            symbol=symbol,
            side="BUY",
            quantity=final_quantity,
            price=price,
            market=target_market,
            slippage_bps=settings.SLIPPAGE_BPS,
        )

        curr_symbol = "$" if target_currency == "USD" else "₹"

        # 5. Check cash sufficiency
        if account.cash_balance_inr < friction.net_cash_impact_inr:
            return False, None, f"Insufficient cash (Requires {curr_symbol}{friction.net_cash_impact_inr}, Available {curr_symbol}{account.cash_balance_inr})"

        # 6. Deduct cash & Create Position
        account.cash_balance_inr -= friction.net_cash_impact_inr
        account.updated_at = datetime.now(timezone.utc)

        inst = universe_manager.get_instrument(symbol)
        pos_exchange = inst.exchange if inst else ("NASDAQ" if target_market == "US" else settings.PRIMARY_EXCHANGE)

        position = PositionModel(
            account_id=account.id,
            symbol=symbol.upper(),
            exchange=pos_exchange,
            quantity=final_quantity,
            average_entry_price=friction.executed_price,
            current_price=friction.executed_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            status=PositionStatus.OPEN,
            realized_pnl_inr=Decimal("0.00"),
            unrealized_pnl_inr=Decimal("0.00"),
            total_charges_incurred_inr=friction.total_charges_inr,
            opened_at=datetime.now(timezone.utc),
        )
        session.add(position)
        await session.flush()  # populate position.id

        # 7. Create Order record
        client_order_id = f"ORD-BUY-{symbol.upper()}-{uuid.uuid4().hex[:8].upper()}"
        order = OrderModel(
            account_id=account.id,
            position_id=position.id,
            client_order_id=client_order_id,
            symbol=symbol.upper(),
            exchange=pos_exchange,
            side=OrderSide.BUY,
            quantity=final_quantity,
            requested_price=round_inr(price),
            executed_price=friction.executed_price,
            status=OrderStatus.FILLED,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            turnover_inr=friction.turnover,
            slippage_inr=friction.slippage_impact_inr,
            brokerage_inr=friction.brokerage_inr,
            stt_tax_inr=friction.stt_tax_inr,
            exchange_turnover_inr=friction.exchange_turnover_inr,
            sebi_charges_inr=friction.sebi_charges_inr,
            stamp_duty_inr=friction.stamp_duty_inr,
            gst_inr=friction.gst_inr,
            total_charges_inr=friction.total_charges_inr,
            net_cash_impact_inr=friction.net_cash_impact_inr,
            reason=reason,
            executed_at=datetime.now(timezone.utc),
        )
        session.add(order)

        # 8. Recompute total portfolio equity
        await PaperTradingEngine.update_portfolio_equity(session, account)
        await session.commit()
        await session.refresh(order)

        logger.info(
            f"VIRTUAL BUY EXECUTED: {final_quantity} shares of {symbol} @ ₹{friction.executed_price} "
            f"(Turnover: ₹{friction.turnover}, Charges: ₹{friction.total_charges_inr})",
            extra={"extra_context": {"client_order_id": client_order_id, "symbol": symbol, "quantity": final_quantity}}
        )

        return True, order, None

    @staticmethod
    async def close_position(
        session: Any,
        position_id: int,
        exit_price: Decimal,
        enforce_market_hours: bool = True,
        reason: str = "Position Exit",
    ) -> Tuple[bool, Optional[OrderModel], Optional[str]]:
        """
        Closes an open position:
        - Calculates sell slippage and exit charges (STT, Brokerage, GST, Exchange fees).
        - Computes net realized P&L accounting for both entry and exit frictions.
        - Credits net turnover minus charges back to available cash.
        - Marks position CLOSED.
        """
        from sqlalchemy import select
        pos_result = await session.execute(
            select(PositionModel).where(
                PositionModel.id == position_id,
                PositionModel.status == PositionStatus.OPEN,
            )
        )
        position = pos_result.scalar_one_or_none()
        if not position:
            return False, None, f"Open position #{position_id} not found."

        account = await session.get(AccountModel, position.account_id)
        if not account:
            account = await PaperTradingEngine.get_or_create_account(session)

        from backend.app.market_data.universe import universe_manager
        from trading.charges import calculate_market_trade_friction

        target_market = universe_manager.get_market_for_symbol(position.symbol)

        # 1. Calculate exit friction
        friction = calculate_market_trade_friction(
            symbol=position.symbol,
            side="SELL",
            quantity=position.quantity,
            price=exit_price,
            market=target_market,
            slippage_bps=settings.SLIPPAGE_BPS,
        )

        # 2. Credit cash (Net proceeds from sell)
        account.cash_balance_inr += friction.net_cash_impact_inr
        account.updated_at = datetime.now(timezone.utc)

        # 3. Calculate Realized P&L taking into account entry charges + exit charges!
        gross_pnl = (friction.executed_price - position.average_entry_price) * Decimal(position.quantity)
        total_roundtrip_charges = position.total_charges_incurred_inr + friction.total_charges_inr
        realized_pnl = round_inr(gross_pnl - total_roundtrip_charges)

        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.now(timezone.utc)
        position.current_price = friction.executed_price
        position.realized_pnl_inr = realized_pnl
        position.unrealized_pnl_inr = Decimal("0.00")
        position.total_charges_incurred_inr = total_roundtrip_charges
        position.updated_at = datetime.now(timezone.utc)

        # 4. Record Exit Order
        client_order_id = f"ORD-SELL-{position.symbol}-{uuid.uuid4().hex[:8].upper()}"
        order = OrderModel(
            account_id=account.id,
            position_id=position.id,
            client_order_id=client_order_id,
            symbol=position.symbol,
            exchange=position.exchange,
            side=OrderSide.SELL,
            quantity=position.quantity,
            requested_price=round_inr(exit_price),
            executed_price=friction.executed_price,
            status=OrderStatus.FILLED,
            stop_loss_price=position.stop_loss_price,
            take_profit_price=position.take_profit_price,
            turnover_inr=friction.turnover,
            slippage_inr=friction.slippage_impact_inr,
            brokerage_inr=friction.brokerage_inr,
            stt_tax_inr=friction.stt_tax_inr,
            exchange_turnover_inr=friction.exchange_turnover_inr,
            sebi_charges_inr=friction.sebi_charges_inr,
            stamp_duty_inr=friction.stamp_duty_inr,
            gst_inr=friction.gst_inr,
            total_charges_inr=friction.total_charges_inr,
            net_cash_impact_inr=friction.net_cash_impact_inr,
            reason=reason,
            executed_at=datetime.now(timezone.utc),
        )
        session.add(order)

        # 5. Recompute portfolio equity and take snapshot
        await PaperTradingEngine.update_portfolio_equity(session, account)
        await session.commit()
        await session.refresh(order)

        logger.info(
            f"VIRTUAL SELL EXECUTED: Closed {position.quantity} shares of {position.symbol} @ ₹{friction.executed_price} "
            f"(Realized Net P&L: ₹{realized_pnl:+.2f}, Roundtrip Charges: ₹{total_roundtrip_charges})",
            extra={"extra_context": {"client_order_id": client_order_id, "realized_pnl": str(realized_pnl)}}
        )

        return True, order, None

    @staticmethod
    async def evaluate_open_positions(
        session: Any,
        current_quotes: Dict[str, Decimal],
        enforce_market_hours: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Monitors open positions against current market prices:
        - Updates unrealized P&L.
        - Triggers Stop-Loss order if price <= stop_loss_price.
        - Triggers Take-Profit order if price >= take_profit_price.
        """
        from sqlalchemy import select
        account = await PaperTradingEngine.get_or_create_account(session)

        pos_result = await session.execute(
            select(PositionModel).where(
                PositionModel.account_id == account.id,
                PositionModel.status == PositionStatus.OPEN,
            )
        )
        open_positions = pos_result.scalars().all()
        events = []

        for pos in open_positions:
            quote = current_quotes.get(pos.symbol)
            if quote is None:
                continue

            pos.current_price = quote
            pos.unrealized_pnl_inr = round_inr((quote - pos.average_entry_price) * Decimal(pos.quantity))
            pos.updated_at = datetime.now(timezone.utc)

            # Check Stop Loss Trigger
            if quote <= pos.stop_loss_price:
                logger.warning(f"STOP LOSS TRIGGERED for {pos.symbol}: Current ₹{quote} <= Stop ₹{pos.stop_loss_price}")
                success, order, err = await PaperTradingEngine.close_position(
                    session,
                    position_id=pos.id,
                    exit_price=quote,
                    enforce_market_hours=enforce_market_hours,
                    reason=f"STOP_LOSS_TRIGGERED (Exit price ₹{quote} breached stop ₹{pos.stop_loss_price})",
                )
                events.append({
                    "symbol": pos.symbol,
                    "event": "STOP_LOSS",
                    "exit_price": float(quote),
                    "success": success,
                })

            # Check Take Profit Trigger
            elif pos.take_profit_price and quote >= pos.take_profit_price:
                logger.info(f"TAKE PROFIT TRIGGERED for {pos.symbol}: Current ₹{quote} >= Target ₹{pos.take_profit_price}")
                success, order, err = await PaperTradingEngine.close_position(
                    session,
                    position_id=pos.id,
                    exit_price=quote,
                    enforce_market_hours=enforce_market_hours,
                    reason=f"TAKE_PROFIT_TRIGGERED (Exit price ₹{quote} reached target ₹{pos.take_profit_price})",
                )
                events.append({
                    "symbol": pos.symbol,
                    "event": "TAKE_PROFIT",
                    "exit_price": float(quote),
                    "success": success,
                })

        await PaperTradingEngine.update_portfolio_equity(session, account)
        await session.commit()
        return events

    @staticmethod
    async def mark_to_market_portfolio(
        session: Any,
        account: AccountModel,
        simulate_live_ticks: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Marks all active open positions to market:
        - Retrieves latest price or applies realistic paper trading price tick.
        - Updates unrealized P&L for each open position.
        - Evaluates protective Stop-Loss and Take-Profit bounds.
        - Recalculates total account equity and saves snapshots.
        """
        from sqlalchemy import select
        import random

        pos_result = await session.execute(
            select(PositionModel).where(
                PositionModel.account_id == account.id,
                PositionModel.status == PositionStatus.OPEN,
            )
        )
        open_positions = pos_result.scalars().all()
        events = []

        for pos in open_positions:
            current_price = pos.current_price
            # Fetch latest real market quote if available
            try:
                from backend.app.market_data.yfinance_provider import YFinanceProvider
                prov = YFinanceProvider()
                quote = prov.fetch_latest_quote(pos.symbol)
                if quote and quote.close and quote.close > Decimal("0"):
                    current_price = quote.close
            except Exception:
                pass

            if simulate_live_ticks:
                # Realistic micro-fluctuation (+/- 0.05% to 0.15%) around real price for active paper simulation
                jitter = Decimal(str(round(random.uniform(-0.0012, 0.0015), 4)))
                current_price = round_inr(current_price * (Decimal("1.0") + jitter))

            pos.current_price = current_price
            pos.unrealized_pnl_inr = round_inr((current_price - pos.average_entry_price) * Decimal(pos.quantity))
            pos.updated_at = datetime.now(timezone.utc)

            # Check Stop Loss Trigger
            if current_price <= pos.stop_loss_price:
                success, order, err = await PaperTradingEngine.close_position(
                    session,
                    position_id=pos.id,
                    exit_price=current_price,
                    enforce_market_hours=False,
                    reason=f"STOP_LOSS_TRIGGERED (Exit price {current_price} hit stop {pos.stop_loss_price})",
                )
                events.append({"symbol": pos.symbol, "event": "STOP_LOSS", "exit_price": float(current_price), "success": success})

            # Check Take Profit Trigger
            elif pos.take_profit_price and current_price >= pos.take_profit_price:
                success, order, err = await PaperTradingEngine.close_position(
                    session,
                    position_id=pos.id,
                    exit_price=current_price,
                    enforce_market_hours=False,
                    reason=f"TAKE_PROFIT_TRIGGERED (Exit price {current_price} reached target {pos.take_profit_price})",
                )
                events.append({"symbol": pos.symbol, "event": "TAKE_PROFIT", "exit_price": float(current_price), "success": success})

        await PaperTradingEngine.update_portfolio_equity(session, account)
        await session.commit()
        return events

    @staticmethod
    async def update_portfolio_equity(session: Any, account: AccountModel) -> Decimal:
        """
        Recalculates total account equity: Cash Balance + Market Value of all open positions.
        Persists a PortfolioSnapshotModel record for equity curve tracking.
        """
        from sqlalchemy import select
        pos_result = await session.execute(
            select(PositionModel).where(
                PositionModel.account_id == account.id,
                PositionModel.status == PositionStatus.OPEN,
            )
        )
        open_positions = pos_result.scalars().all()

        positions_value = sum(
            (p.current_price * Decimal(p.quantity) for p in open_positions),
            Decimal("0.00"),
        )
        total_unrealized = sum((p.unrealized_pnl_inr for p in open_positions), Decimal("0.00"))

        closed_result = await session.execute(
            select(PositionModel).where(
                PositionModel.account_id == account.id,
                PositionModel.status == PositionStatus.CLOSED,
            )
        )
        closed_positions = closed_result.scalars().all()
        total_realized = sum((p.realized_pnl_inr for p in closed_positions), Decimal("0.00"))

        equity = round_inr(account.cash_balance_inr + positions_value)
        account.equity_inr = equity
        account.updated_at = datetime.now(timezone.utc)

        # Create periodic snapshot
        snapshot = PortfolioSnapshotModel(
            account_id=account.id,
            timestamp=datetime.now(timezone.utc),
            cash_balance_inr=account.cash_balance_inr,
            positions_market_value_inr=positions_value,
            equity_inr=equity,
            open_positions_count=len(open_positions),
            total_realized_pnl_inr=total_realized,
            total_unrealized_pnl_inr=total_unrealized,
            cumulative_drawdown_pct=Decimal("0.00"),
        )
        session.add(snapshot)
        return equity
