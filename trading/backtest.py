"""
Institutional Backtesting Engine for Indian Equities.

Key Quantitative Features:
- Strictly chronological, sequential bar-by-bar execution without look-ahead bias.
- Warmup isolation: No trades allowed before indicator convergence (minimum 50 bars).
- Realistic execution modeling:
  - Intrabar Stop-Loss and Take-Profit fills using high/low price bounds.
  - Adverse price slippage simulation (default 5 bps).
  - Indian regulatory delivery friction (Brokerage ₹20, STT 0.1%, Exchange fee, GST 18%, Stamp Duty 0.015%, SEBI fee).
  - Gap-down and gap-up open simulation at stop-loss/take-profit boundaries.
- Complete trade log, equity curve time series, and institutional performance metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Sequence

from backend.app.market_data.base import Candle
from strategies.base import BaseStrategy, SignalAction
from strategies.swing_strategy import EMAMACDSwingStrategy
from trading.charges import calculate_trade_friction, round_inr
from trading.metrics import PerformanceMetrics, calculate_performance_metrics
from trading.risk import calculate_position_size

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Individual trade record within a backtest run."""
    trade_id: int
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: int
    stop_loss_price: Decimal
    take_profit_price: Optional[Decimal]
    exit_reason: str  # "STOP_LOSS", "TAKE_PROFIT", "STRATEGY_EXIT", "END_OF_DATA"
    gross_pnl_inr: Decimal
    entry_charges_inr: Decimal
    exit_charges_inr: Decimal
    total_charges_inr: Decimal
    net_pnl_inr: Decimal
    return_pct: float
    holding_period_bars: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price),
            "quantity": self.quantity,
            "stop_loss_price": float(self.stop_loss_price),
            "take_profit_price": float(self.take_profit_price) if self.take_profit_price else None,
            "exit_reason": self.exit_reason,
            "gross_pnl_inr": float(self.gross_pnl_inr),
            "total_charges_inr": float(self.total_charges_inr),
            "net_pnl_inr": float(self.net_pnl_inr),
            "return_pct": round(self.return_pct, 2),
            "holding_period_bars": self.holding_period_bars,
        }


@dataclass
class BacktestResult:
    """Consolidated backtest summary and time series output."""
    symbol: str
    strategy_name: str
    start_time: datetime
    end_time: datetime
    total_bars: int
    initial_capital_inr: Decimal
    final_equity_inr: Decimal
    total_net_profit_inr: Decimal
    total_return_pct: float
    trades: List[BacktestTrade]
    equity_curve: List[Dict[str, Any]]
    metrics: PerformanceMetrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy_name": self.strategy_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_bars": self.total_bars,
            "initial_capital_inr": float(self.initial_capital_inr),
            "final_equity_inr": float(self.final_equity_inr),
            "total_net_profit_inr": float(self.total_net_profit_inr),
            "total_return_pct": round(self.total_return_pct, 2),
            "total_trades_count": len(self.trades),
            "metrics": self.metrics.to_dict(),
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": self.equity_curve,
        }


class BacktestEngine:
    """Vector-assisted sequential event-driven backtesting engine."""

    def __init__(
        self,
        strategy: Optional[BaseStrategy] = None,
        initial_capital_inr: Decimal = Decimal("100000.00"),
        max_risk_per_trade: float = 0.01,
        max_allocation_per_position: float = 0.20,
        slippage_bps: float = 5.0,
        warmup_bars: int = 50,
    ) -> None:
        self.strategy = strategy or EMAMACDSwingStrategy()
        self.initial_capital_inr = initial_capital_inr
        self.max_risk_per_trade = max_risk_per_trade
        self.max_allocation_per_position = max_allocation_per_position
        self.slippage_bps = slippage_bps
        self.warmup_bars = warmup_bars

    def run(
        self,
        symbol: str,
        candles: Sequence[Candle],
    ) -> BacktestResult:
        """
        Executes a chronological, walk-forward simulation across the provided candle history.
        """
        n = len(candles)
        if n < self.warmup_bars:
            raise ValueError(
                f"Insufficient data for backtesting {symbol}: provided {n} bars, "
                f"minimum warmup requires {self.warmup_bars} bars."
            )

        cash = self.initial_capital_inr
        equity = cash
        active_position: Optional[Dict[str, Any]] = None
        closed_trades: List[BacktestTrade] = []
        equity_curve_points: List[Dict[str, Any]] = []
        equity_values: List[Decimal] = []
        trade_counter = 0

        for i in range(n):
            current_candle = candles[i]
            bar_ts = current_candle.timestamp
            open_p = current_candle.open
            high_p = current_candle.high
            low_p = current_candle.low
            close_p = current_candle.close

            # ------------------------------------------------------------------
            # 1. Evaluate Intrabar Exits on Active Position (Stop-Loss / Take-Profit)
            # ------------------------------------------------------------------
            if active_position is not None:
                pos = active_position
                sl_price = pos["stop_loss_price"]
                tp_price = pos["take_profit_price"]
                exit_triggered = False
                exit_price = Decimal("0.00")
                exit_reason = ""

                # Check Stop-Loss breach (Adverse fill simulation)
                if low_p <= sl_price:
                    exit_triggered = True
                    # If open gapped below stop loss, fill at open (slippage applied on open)
                    exit_price = min(open_p, sl_price)
                    exit_reason = "STOP_LOSS"
                # Check Take-Profit reached (Favorable fill simulation)
                elif tp_price is not None and high_p >= tp_price:
                    exit_triggered = True
                    # If open gapped above take profit, fill at open
                    exit_price = max(open_p, tp_price)
                    exit_reason = "TAKE_PROFIT"

                if exit_triggered:
                    trade_counter += 1
                    # Compute exit friction
                    exit_friction = calculate_trade_friction(
                        symbol=symbol,
                        side="SELL",
                        quantity=pos["quantity"],
                        price=exit_price,
                        slippage_bps=self.slippage_bps,
                    )
                    # Credit cash
                    cash += exit_friction.net_cash_impact_inr

                    # Compute P&L accounting for roundtrip charges
                    gross_pnl = (exit_friction.executed_price - pos["entry_price"]) * Decimal(pos["quantity"])
                    total_charges = pos["entry_charges"] + exit_friction.total_charges_inr
                    net_pnl = round_inr(gross_pnl - total_charges)
                    ret_pct = float((net_pnl / (pos["entry_price"] * Decimal(pos["quantity"]))) * Decimal("100.0"))

                    trade_record = BacktestTrade(
                        trade_id=trade_counter,
                        symbol=symbol,
                        side="BUY",
                        entry_time=pos["entry_time"],
                        exit_time=bar_ts,
                        entry_price=pos["entry_price"],
                        exit_price=exit_friction.executed_price,
                        quantity=pos["quantity"],
                        stop_loss_price=sl_price,
                        take_profit_price=tp_price,
                        exit_reason=exit_reason,
                        gross_pnl_inr=round_inr(gross_pnl),
                        entry_charges_inr=pos["entry_charges"],
                        exit_charges_inr=exit_friction.total_charges_inr,
                        total_charges_inr=total_charges,
                        net_pnl_inr=net_pnl,
                        return_pct=ret_pct,
                        holding_period_bars=i - pos["entry_bar_idx"],
                    )
                    closed_trades.append(trade_record)
                    active_position = None

            # ------------------------------------------------------------------
            # 2. Strategy Signal Evaluation (Only after warmup period)
            # ------------------------------------------------------------------
            if i >= self.warmup_bars - 1:
                # Historical slice up to and including current bar (zero look-ahead bias)
                history_slice = candles[:i + 1]
                signal = self.strategy.generate_signal(symbol, history_slice)

                # Entry: If flat and signal is BUY
                if active_position is None and signal.action == SignalAction.BUY:
                    # Size position using 1% equity risk
                    sizing = calculate_position_size(
                        equity=cash,  # When flat, equity == cash
                        available_cash=cash,
                        entry_price=close_p,
                        stop_loss_price=signal.suggested_stop_loss,
                        max_risk_pct=self.max_risk_per_trade,
                        max_allocation_pct=self.max_allocation_per_position,
                    )

                    if sizing.is_approved and sizing.quantity > 0:
                        buy_friction = calculate_trade_friction(
                            symbol=symbol,
                            side="BUY",
                            quantity=sizing.quantity,
                            price=close_p,
                            slippage_bps=self.slippage_bps,
                        )

                        if cash >= buy_friction.net_cash_impact_inr:
                            cash -= buy_friction.net_cash_impact_inr
                            active_position = {
                                "entry_bar_idx": i,
                                "entry_time": bar_ts,
                                "entry_price": buy_friction.executed_price,
                                "quantity": sizing.quantity,
                                "stop_loss_price": signal.suggested_stop_loss,
                                "take_profit_price": signal.suggested_take_profit,
                                "entry_charges": buy_friction.total_charges_inr,
                            }

                # Exit on Strategy Breakdown (if open and signal is SELL)
                elif active_position is not None and signal.action == SignalAction.SELL:
                    pos = active_position
                    trade_counter += 1
                    exit_friction = calculate_trade_friction(
                        symbol=symbol,
                        side="SELL",
                        quantity=pos["quantity"],
                        price=close_p,
                        slippage_bps=self.slippage_bps,
                    )
                    cash += exit_friction.net_cash_impact_inr
                    gross_pnl = (exit_friction.executed_price - pos["entry_price"]) * Decimal(pos["quantity"])
                    total_charges = pos["entry_charges"] + exit_friction.total_charges_inr
                    net_pnl = round_inr(gross_pnl - total_charges)
                    ret_pct = float((net_pnl / (pos["entry_price"] * Decimal(pos["quantity"]))) * Decimal("100.0"))

                    trade_record = BacktestTrade(
                        trade_id=trade_counter,
                        symbol=symbol,
                        side="BUY",
                        entry_time=pos["entry_time"],
                        exit_time=bar_ts,
                        entry_price=pos["entry_price"],
                        exit_price=exit_friction.executed_price,
                        quantity=pos["quantity"],
                        stop_loss_price=pos["stop_loss_price"],
                        take_profit_price=pos["take_profit_price"],
                        exit_reason="STRATEGY_EXIT",
                        gross_pnl_inr=round_inr(gross_pnl),
                        entry_charges_inr=pos["entry_charges"],
                        exit_charges_inr=exit_friction.total_charges_inr,
                        total_charges_inr=total_charges,
                        net_pnl_inr=net_pnl,
                        return_pct=ret_pct,
                        holding_period_bars=i - pos["entry_bar_idx"],
                    )
                    closed_trades.append(trade_record)
                    active_position = None

            # ------------------------------------------------------------------
            # 3. Mark-to-Market Portfolio Equity Calculation
            # ------------------------------------------------------------------
            open_position_val = (
                (close_p * Decimal(active_position["quantity"])) if active_position else Decimal("0.00")
            )
            equity = round_inr(cash + open_position_val)
            equity_values.append(equity)
            equity_curve_points.append({
                "timestamp": bar_ts.isoformat(),
                "equity": float(equity),
                "cash": float(cash),
                "in_position": active_position is not None,
            })

        # ----------------------------------------------------------------------
        # 4. Final Position Liquidation at End of Backtest Period
        # ----------------------------------------------------------------------
        if active_position is not None:
            pos = active_position
            final_candle = candles[-1]
            trade_counter += 1
            exit_friction = calculate_trade_friction(
                symbol=symbol,
                side="SELL",
                quantity=pos["quantity"],
                price=final_candle.close,
                slippage_bps=self.slippage_bps,
            )
            cash += exit_friction.net_cash_impact_inr
            gross_pnl = (exit_friction.executed_price - pos["entry_price"]) * Decimal(pos["quantity"])
            total_charges = pos["entry_charges"] + exit_friction.total_charges_inr
            net_pnl = round_inr(gross_pnl - total_charges)
            ret_pct = float((net_pnl / (pos["entry_price"] * Decimal(pos["quantity"]))) * Decimal("100.0"))

            trade_record = BacktestTrade(
                trade_id=trade_counter,
                symbol=symbol,
                side="BUY",
                entry_time=pos["entry_time"],
                exit_time=final_candle.timestamp,
                entry_price=pos["entry_price"],
                exit_price=exit_friction.executed_price,
                quantity=pos["quantity"],
                stop_loss_price=pos["stop_loss_price"],
                take_profit_price=pos["take_profit_price"],
                exit_reason="END_OF_DATA",
                gross_pnl_inr=round_inr(gross_pnl),
                entry_charges_inr=pos["entry_charges"],
                exit_charges_inr=exit_friction.total_charges_inr,
                total_charges_inr=total_charges,
                net_pnl_inr=net_pnl,
                return_pct=ret_pct,
                holding_period_bars=len(candles) - 1 - pos["entry_bar_idx"],
            )
            closed_trades.append(trade_record)
            equity = cash
            equity_values[-1] = equity
            equity_curve_points[-1]["equity"] = float(equity)
            equity_curve_points[-1]["in_position"] = False

        # ----------------------------------------------------------------------
        # 5. Calculate Metrics
        # ----------------------------------------------------------------------
        realized_pnls = [t.net_pnl_inr for t in closed_trades]
        charges = [t.total_charges_inr for t in closed_trades]

        metrics = calculate_performance_metrics(
            realized_pnls=realized_pnls,
            charges_paid=charges,
            equity_curve=equity_values,
        )

        total_net_profit = equity - self.initial_capital_inr
        total_ret_pct = float(total_net_profit / self.initial_capital_inr * Decimal("100.0"))

        return BacktestResult(
            symbol=symbol,
            strategy_name=self.strategy.strategy_name,
            start_time=candles[0].timestamp,
            end_time=candles[-1].timestamp,
            total_bars=n,
            initial_capital_inr=self.initial_capital_inr,
            final_equity_inr=equity,
            total_net_profit_inr=total_net_profit,
            total_return_pct=total_ret_pct,
            trades=closed_trades,
            equity_curve=equity_curve_points,
            metrics=metrics,
        )
