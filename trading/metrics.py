"""
Institutional Performance Metrics and Equity Curve Analytics.

Calculates:
- Win rate, profit factor, gross profit, gross loss.
- Total regulatory charges and taxes paid (STT, Brokerage, GST, SEBI, Stamp Duty).
- Net realized P&L and average trade return.
- Maximum drawdown (peak-to-trough in INR and percentage).
- Annualized Sharpe Ratio using Indian risk-free benchmark (6.5% RBI T-Bill rate).
"""

from dataclasses import dataclass
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class PerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate_pct: float
    profit_factor: float
    total_gross_profit_inr: Decimal
    total_gross_loss_inr: Decimal
    total_charges_paid_inr: Decimal
    total_net_realized_pnl_inr: Decimal
    average_trade_pnl_inr: Decimal
    largest_win_inr: Decimal
    largest_loss_inr: Decimal
    max_drawdown_inr: Decimal
    max_drawdown_pct: float
    sharpe_ratio: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "breakeven_trades": self.breakeven_trades,
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 2),
            "total_gross_profit_inr": float(self.total_gross_profit_inr),
            "total_gross_loss_inr": float(self.total_gross_loss_inr),
            "total_charges_paid_inr": float(self.total_charges_paid_inr),
            "total_net_realized_pnl_inr": float(self.total_net_realized_pnl_inr),
            "average_trade_pnl_inr": float(self.average_trade_pnl_inr),
            "largest_win_inr": float(self.largest_win_inr),
            "largest_loss_inr": float(self.largest_loss_inr),
            "max_drawdown_inr": float(self.max_drawdown_inr),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2) if self.sharpe_ratio is not None else None,
        }


def calculate_performance_metrics(
    realized_pnls: Sequence[Decimal],
    charges_paid: Sequence[Decimal],
    equity_curve: Sequence[Decimal],
    annual_risk_free_rate: float = 0.065,  # 6.5% typical for RBI 91-day Treasury Bills
) -> PerformanceMetrics:
    """
    Computes institutional trade ledger and equity curve metrics.
    """
    total_trades = len(realized_pnls)
    if total_trades == 0:
        total_charges = sum(charges_paid, Decimal("0.00"))
        max_dd_inr = Decimal("0.00")
        max_dd_pct = 0.0

        if len(equity_curve) >= 2:
            peak = equity_curve[0]
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd_inr = peak - eq
                if dd_inr > max_dd_inr:
                    max_dd_inr = dd_inr
                if peak > Decimal("0.00"):
                    dd_pct = float((dd_inr / peak) * Decimal("100.0"))
                    if dd_pct > max_dd_pct:
                        max_dd_pct = dd_pct

        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            breakeven_trades=0,
            win_rate_pct=0.0,
            profit_factor=0.0,
            total_gross_profit_inr=Decimal("0.00"),
            total_gross_loss_inr=Decimal("0.00"),
            total_charges_paid_inr=total_charges,
            total_net_realized_pnl_inr=Decimal("0.00"),
            average_trade_pnl_inr=Decimal("0.00"),
            largest_win_inr=Decimal("0.00"),
            largest_loss_inr=Decimal("0.00"),
            max_drawdown_inr=max_dd_inr,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=None,
        )

    winning = 0
    losing = 0
    breakeven = 0
    gross_profit = Decimal("0.00")
    gross_loss = Decimal("0.00")
    largest_win = Decimal("0.00")
    largest_loss = Decimal("0.00")

    for pnl in realized_pnls:
        if pnl > Decimal("0.00"):
            winning += 1
            gross_profit += pnl
            if pnl > largest_win:
                largest_win = pnl
        elif pnl < Decimal("0.00"):
            losing += 1
            gross_loss += abs(pnl)
            if pnl < largest_loss:
                largest_loss = pnl
        else:
            breakeven += 1

    win_rate = (winning / total_trades) * 100.0 if total_trades > 0 else 0.0
    profit_factor = float(gross_profit / gross_loss) if gross_loss > Decimal("0.00") else (99.0 if gross_profit > 0 else 0.0)

    total_charges = sum(charges_paid, Decimal("0.00"))
    total_net_pnl = sum(realized_pnls, Decimal("0.00"))
    avg_pnl = total_net_pnl / Decimal(str(total_trades))

    # --- Maximum Drawdown Calculation ---
    max_dd_inr = Decimal("0.00")
    max_dd_pct = 0.0

    if len(equity_curve) >= 2:
        peak = equity_curve[0]
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd_inr = peak - eq
            if dd_inr > max_dd_inr:
                max_dd_inr = dd_inr
            if peak > Decimal("0.00"):
                dd_pct = float((dd_inr / peak) * Decimal("100.0"))
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct

    # --- Sharpe Ratio Calculation ---
    sharpe_ratio = None
    if len(equity_curve) >= 5:
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev = float(equity_curve[i - 1])
            curr = float(equity_curve[i])
            if prev > 0:
                daily_returns.append((curr - prev) / prev)

        if len(daily_returns) >= 4:
            mean_ret = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std_dev = math.sqrt(variance)

            # Annualize (252 trading days)
            daily_rf = annual_risk_free_rate / 252.0
            if std_dev > 1e-8:
                sharpe_ratio = ((mean_ret - daily_rf) / std_dev) * math.sqrt(252.0)

    return PerformanceMetrics(
        total_trades=total_trades,
        winning_trades=winning,
        losing_trades=losing,
        breakeven_trades=breakeven,
        win_rate_pct=win_rate,
        profit_factor=profit_factor,
        total_gross_profit_inr=gross_profit,
        total_gross_loss_inr=gross_loss,
        total_charges_paid_inr=total_charges,
        total_net_realized_pnl_inr=total_net_pnl,
        average_trade_pnl_inr=avg_pnl,
        largest_win_inr=largest_win,
        largest_loss_inr=largest_loss,
        max_drawdown_inr=max_dd_inr,
        max_drawdown_pct=max_dd_pct,
        sharpe_ratio=sharpe_ratio,
    )


def reconstruct_multipoint_equity_curve(
    initial_capital: float,
    closed_trades_pnl: list,
    unrealized_pnl: float = 0.0,
    trade_timestamps: Optional[list] = None,
) -> dict:
    """
    Reconstructs chronological multi-point equity curve (N+2 points).
    Prevents the Tab 5 straight-line 2-point bug.
    """
    points = []
    labels = []

    # Point 0: Start
    labels.append("Start")
    points.append(float(initial_capital))

    cum_equity = initial_capital
    for idx, pnl in enumerate(closed_trades_pnl):
        cum_equity += float(pnl)
        lbl = trade_timestamps[idx] if trade_timestamps and idx < len(trade_timestamps) else f"Trade {idx + 1}"
        labels.append(lbl)
        points.append(round(cum_equity, 2))

    # Terminal Point: Current (including mark-to-market unrealized P&L)
    terminal_equity = cum_equity + float(unrealized_pnl)
    labels.append("Current")
    points.append(round(terminal_equity, 2))

    # Peak-to-trough Drawdown %
    peak = points[0]
    max_dd_val = 0.0
    max_dd_pct = 0.0
    for p in points:
        if p > peak:
            peak = p
        dd = peak - p
        if dd > max_dd_val:
            max_dd_val = dd
        if peak > 0:
            dd_pct = (dd / peak) * 100.0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

    return {
        "labels": labels,
        "equity_curve": points,
        "total_points": len(points),  # Exactly N + 2
        "final_equity": points[-1],
        "max_drawdown_amount": round(max_dd_val, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
    }

