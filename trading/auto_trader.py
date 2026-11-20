"""
Autonomous AI Auto-Trading Engine for Indian (NSE) and US (NYSE/NASDAQ) Markets.

Provides:
- Fully automated, hands-free order execution driven by quantitative strategy confluence and Gemini AI.
- Automated Stop-Loss and Take-Profit monitoring and liquidation.
- Automated Reversal Exits when technical regime shifts to SELL.
- 1% Equity Risk position sizing per trade.
- Comprehensive decision audit trail and execution logs.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

from backend.app.ai.gemini_analyzer import GeminiMarketAnalyzer
from backend.app.market_data.universe import universe_manager
from backend.app.market_data.yfinance_provider import YFinanceProvider
try:
    from database.models import AccountModel, OrderModel, PositionModel, PositionStatus
except ImportError:
    AccountModel = OrderModel = PositionModel = Any  # type: ignore
    import enum
    class PositionStatus(str, enum.Enum):  # type: ignore
        OPEN = "OPEN"
        CLOSED = "CLOSED"
from strategies.base import SignalAction
from strategies.swing_strategy import EMAMACDSwingStrategy
from trading.charges import round_inr
from trading.engine import PaperTradingEngine

logger = logging.getLogger(__name__)


@dataclass
class AutoTraderConfig:
    enabled: bool = False
    min_confluence_score: int = 70
    require_ai_approval: bool = True
    auto_exit_on_reversal: bool = True
    max_open_positions: int = 5
    enforce_market_hours: bool = False
    timeframe: str = "1d"
    allow_synthetic: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "min_confluence_score": self.min_confluence_score,
            "require_ai_approval": self.require_ai_approval,
            "auto_exit_on_reversal": self.auto_exit_on_reversal,
            "max_open_positions": self.max_open_positions,
            "enforce_market_hours": self.enforce_market_hours,
            "timeframe": self.timeframe,
            "allow_synthetic": self.allow_synthetic,
        }


@dataclass
class AutoTraderDecision:
    timestamp: str
    symbol: str
    market: str
    action: str  # "BUY", "SELL_TP", "SELL_SL", "SELL_REVERSAL", "HOLD", "SKIP"
    reason: str
    executed: bool
    order_id: Optional[str] = None
    pnl: Optional[float] = None
    score: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "market": self.market,
            "action": self.action,
            "reason": self.reason,
            "executed": self.executed,
            "order_id": self.order_id,
            "pnl": self.pnl,
            "score": self.score,
        }


class AutoTradingBot:
    """Autonomous algorithmic and AI paper trading executor."""

    def __init__(self, max_history_size: int = 100) -> None:
        self.config = AutoTraderConfig()
        self.strategy = EMAMACDSwingStrategy()
        self.market_provider = YFinanceProvider()
        self.ai_analyzer = GeminiMarketAnalyzer()
        self._history: deque[AutoTraderDecision] = deque(maxlen=max_history_size)
        self.last_cycle_at: Optional[datetime] = None

    def get_history(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in reversed(self._history)]

    def clear_history(self) -> None:
        self._history.clear()

    def record_decision(self, decision: AutoTraderDecision) -> None:
        self._history.append(decision)

    async def run_cycle(
        self,
        session: Any,
        market: str = "IN",
        config_override: Optional[AutoTraderConfig] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single autonomous evaluation and execution cycle for the specified market:
        1. Checks all open positions for stop-loss, take-profit, or technical reversal exits.
        2. Scans universe for high-confluence BUY signals and executes approved entries.
        """
        cfg = config_override or self.config
        market = market.upper()
        target_currency = "USD" if market == "US" else "INR"
        cycle_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.last_cycle_at = datetime.now(timezone.utc)

        # Retrieve relevant paper account
        account = await PaperTradingEngine.get_or_create_account(session, currency=target_currency)
        await PaperTradingEngine.update_portfolio_equity(session, account)

        try:
            from sqlalchemy import select
            pos_stmt = select(PositionModel).where(
                PositionModel.account_id == account.id,
                PositionModel.status == PositionStatus.OPEN,
            )
            pos_res = await session.execute(pos_stmt)
        except Exception:
            pos_res = await session.execute("mock_stmt")
        open_positions = list(pos_res.scalars().all())
        existing_symbols = {p.symbol for p in open_positions}

        cycle_decisions: List[AutoTraderDecision] = []
        orders_executed: List[str] = []
        positions_closed: List[str] = []

        # ======================================================================
        # PHASE 1: Monitor and Autonomously Manage Open Positions
        # ======================================================================
        for pos in list(open_positions):
            try:
                # Fetch recent candles for current position
                batch = self.market_provider.fetch_historical_ohlcv(pos.symbol, timeframe=cfg.timeframe, period="5d")
                if not batch.candles:
                    continue
                current_price = batch.candles[-1].close

                # Update mark-to-market
                pos.current_price = current_price
                pos.unrealized_pnl_inr = round_inr((current_price - pos.average_entry_price) * Decimal(pos.quantity))

                # Check Stop-Loss
                if current_price <= pos.stop_loss_price:
                    success, order, err = await PaperTradingEngine.close_position(
                        session,
                        position_id=pos.id,
                        exit_price=current_price,
                        enforce_market_hours=cfg.enforce_market_hours,
                        reason="Autonomous AI: Stop-Loss Triggered",
                    )
                    if success and order:
                        pnl_val = float(pos.realized_pnl_inr)
                        dec = AutoTraderDecision(
                            timestamp=cycle_time_str,
                            symbol=pos.symbol,
                            market=market,
                            action="SELL_SL",
                            reason=f"Stop-Loss hit @ {current_price} (SL: {pos.stop_loss_price})",
                            executed=True,
                            order_id=order.client_order_id,
                            pnl=pnl_val,
                        )
                        self.record_decision(dec)
                        cycle_decisions.append(dec)
                        positions_closed.append(pos.symbol)
                        existing_symbols.discard(pos.symbol)
                    continue

                # Check Take-Profit
                if pos.take_profit_price and current_price >= pos.take_profit_price:
                    success, order, err = await PaperTradingEngine.close_position(
                        session,
                        position_id=pos.id,
                        exit_price=current_price,
                        enforce_market_hours=cfg.enforce_market_hours,
                        reason="Autonomous AI: Take-Profit Target Reached",
                    )
                    if success and order:
                        pnl_val = float(pos.realized_pnl_inr)
                        dec = AutoTraderDecision(
                            timestamp=cycle_time_str,
                            symbol=pos.symbol,
                            market=market,
                            action="SELL_TP",
                            reason=f"Take-Profit hit @ {current_price} (TP: {pos.take_profit_price})",
                            executed=True,
                            order_id=order.client_order_id,
                            pnl=pnl_val,
                        )
                        self.record_decision(dec)
                        cycle_decisions.append(dec)
                        positions_closed.append(pos.symbol)
                        existing_symbols.discard(pos.symbol)
                    continue

                # Check Strategy Reversal Exit (if enabled)
                if cfg.auto_exit_on_reversal:
                    full_batch = self.market_provider.fetch_historical_ohlcv(pos.symbol, timeframe=cfg.timeframe, period="6mo")
                    if full_batch.candles and len(full_batch.candles) >= 50:
                        rev_signal = self.strategy.generate_signal(pos.symbol, full_batch.candles)
                        if rev_signal.action == SignalAction.SELL:
                            success, order, err = await PaperTradingEngine.close_position(
                                session,
                                position_id=pos.id,
                                exit_price=current_price,
                                enforce_market_hours=cfg.enforce_market_hours,
                                reason=f"Autonomous AI: Technical Reversal to SELL ({rev_signal.primary_trigger})",
                            )
                            if success and order:
                                pnl_val = float(pos.realized_pnl_inr)
                                dec = AutoTraderDecision(
                                    timestamp=cycle_time_str,
                                    symbol=pos.symbol,
                                    market=market,
                                    action="SELL_REVERSAL",
                                    reason=f"Strategy Reversal to SELL ({rev_signal.primary_trigger})",
                                    executed=True,
                                    order_id=order.client_order_id,
                                    pnl=pnl_val,
                                )
                                self.record_decision(dec)
                                cycle_decisions.append(dec)
                                positions_closed.append(pos.symbol)
                                existing_symbols.discard(pos.symbol)
                            continue

                # Position holding safely
                dec = AutoTraderDecision(
                    timestamp=cycle_time_str,
                    symbol=pos.symbol,
                    market=market,
                    action="HOLD",
                    reason=f"Active position holding safely @ {current_price} (Unrealized P&L: {pos.unrealized_pnl_inr})",
                    executed=False,
                )
                cycle_decisions.append(dec)

            except Exception as exc:
                logger.error(f"Error evaluating open position for {pos.symbol}: {exc}")

        # Commit position updates
        await session.commit()

        # Re-query open positions count
        slots_available = cfg.max_open_positions - len(existing_symbols)

        # ======================================================================
        # PHASE 2: Autonomous Signal Scanning & New Order Execution
        # ======================================================================
        candidate_symbols = universe_manager.get_symbols(market=market, scan_only=True)

        for sym in candidate_symbols:
            if slots_available <= 0:
                break
            if sym in existing_symbols:
                continue

            try:
                # Fetch candle history for signal generation
                batch = self.market_provider.fetch_historical_ohlcv(sym, timeframe=cfg.timeframe, period="6mo")
                if not batch.candles or len(batch.candles) < 20:
                    batch = YFinanceProvider.generate_synthetic_history(sym, days=120)

                # Guard: Never place live paper orders on synthetic fallback data
                if batch.provider == "synthetic_fixture" and not cfg.allow_synthetic:
                    logger.warning(f"Skipping auto-trade entry for {sym}: candles sourced from synthetic fixture fallback.")
                    continue

                signal = self.strategy.generate_signal(sym, batch.candles)

                # Filter by BUY action and Confluence Threshold
                if signal.action == SignalAction.BUY and signal.technical_score >= cfg.min_confluence_score:
                    ai_approved = True
                    ai_opinion = "ALGORITHMIC_CONFIRMED"

                    # Optional Gemini AI Confirmation Gate
                    if cfg.require_ai_approval:
                        try:
                            snapshot = signal.snapshot
                            if not snapshot:
                                from indicators.engine import TechnicalIndicatorEngine
                                series = TechnicalIndicatorEngine().compute(sym, batch.candles)
                                snapshot = series.snapshot

                            ai_analysis = await self.ai_analyzer.analyze_market_state(
                                symbol=sym,
                                snapshot=snapshot,
                                signal=signal,
                            )
                            ai_stance = ai_analysis.recommended_action_opinion.upper()
                            ai_opinion = ai_stance

                            # Approve if AI stance is positive or aligns with upside
                            if "SELL" in ai_stance or "AVOID" in ai_stance or "BEARISH" in ai_stance:
                                ai_approved = False
                        except Exception as ai_err:
                            logger.warning(f"AI confirmation fallback for {sym}: {ai_err}")
                            ai_approved = True  # Fallback to deterministic confluence

                    if ai_approved:
                        entry_price = signal.entry_price
                        sl_price = signal.suggested_stop_loss
                        tp_price = signal.suggested_take_profit

                        success, order, err = await PaperTradingEngine.execute_buy(
                            session=session,
                            symbol=sym,
                            price=entry_price,
                            stop_loss_price=sl_price,
                            take_profit_price=tp_price,
                            quantity=None,  # 1% equity risk positioning
                            enforce_market_hours=cfg.enforce_market_hours,
                            reason=f"Autonomous AI: Confluence {signal.technical_score}/100, AI: {ai_opinion}",
                        )

                        if success and order:
                            slots_available -= 1
                            existing_symbols.add(sym)
                            orders_executed.append(order.client_order_id)

                            dec = AutoTraderDecision(
                                timestamp=cycle_time_str,
                                symbol=sym,
                                market=market,
                                action="BUY",
                                reason=f"Executed BUY {order.quantity} shs @ {order.executed_price} (Score: {signal.technical_score}/100, AI: {ai_opinion})",
                                executed=True,
                                order_id=order.client_order_id,
                                score=signal.technical_score,
                            )
                            self.record_decision(dec)
                            cycle_decisions.append(dec)
                        else:
                            dec = AutoTraderDecision(
                                timestamp=cycle_time_str,
                                symbol=sym,
                                market=market,
                                action="SKIP",
                                reason=f"Order rejected: {err}",
                                executed=False,
                                score=signal.technical_score,
                            )
                            self.record_decision(dec)
                            cycle_decisions.append(dec)
                    else:
                        dec = AutoTraderDecision(
                            timestamp=cycle_time_str,
                            symbol=sym,
                            market=market,
                            action="SKIP",
                            reason=f"AI gate declined entry (Stance: {ai_opinion}, Technical Score: {signal.technical_score})",
                            executed=False,
                            score=signal.technical_score,
                        )
                        self.record_decision(dec)
                        cycle_decisions.append(dec)
                else:
                    dec = AutoTraderDecision(
                        timestamp=cycle_time_str,
                        symbol=sym,
                        market=market,
                        action="SKIP",
                        reason=f"Signal {signal.action.value} (Score {signal.technical_score}/{cfg.min_confluence_score})",
                        executed=False,
                        score=signal.technical_score,
                    )
                    # Don't flood history with passive skips, only add to cycle
                    cycle_decisions.append(dec)

            except Exception as sym_err:
                logger.error(f"Error scanning candidate symbol {sym}: {sym_err}")

        # Final portfolio equity update
        await PaperTradingEngine.update_portfolio_equity(session, account)
        await session.commit()

        return {
            "cycle_timestamp": cycle_time_str,
            "market": market,
            "currency": target_currency,
            "orders_executed_count": len(orders_executed),
            "orders_executed": orders_executed,
            "positions_closed_count": len(positions_closed),
            "positions_closed": positions_closed,
            "decisions": [d.to_dict() for d in cycle_decisions],
            "account_equity": float(account.equity_inr),
            "available_cash": float(account.cash_balance_inr),
        }


# Singleton AutoTradingBot instance
auto_trading_bot = AutoTradingBot()
