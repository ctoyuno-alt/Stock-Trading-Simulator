"""
Tab 6: Historical Backtesting Engine for Quantum Trader.
Provides walk-forward historical simulation with zero look-ahead bias,
fee calculation (US vs Indian regulatory frictions), multi-point equity curve,
underwater drawdown curve, institutional metrics (CAGR, Sortino, Calmar),
session state caching (fixing rerun loop defect), and CSV export.
"""

import csv
import io
import math
from typing import Any, Dict, List

try:
    import streamlit as st
except ImportError:
    st = None

from dashboard.components.charts import (
    create_equity_curve_chart,
    create_underwater_drawdown_chart,
)


def render_tab(
    api_client: Any,
    state: Dict[str, Any],
    market: str,
    symbol: str,
    timeframe: str,
) -> None:
    """
    Renders Tab 6: Historical Backtest.
    """
    is_us_market = state.get("is_us_market", False)
    active_currency = state.get("active_currency", "INR")
    curr_sym = state.get("curr_sym", "₹")
    universe_symbols = state.get("universe_symbols", [symbol])
    default_cap = float(state.get("default_cap", 100000.0) or 100000.0)

    st.markdown(f"### **Walk-Forward Historical Strategy Backtesting ({active_currency})**")
    backtest_caption = (
        "Walk-forward simulation with zero look-ahead bias, accounting for US zero-commission trading, "
        "SEC/FINRA exit charges, and 5 bps adverse slippage."
        if is_us_market
        else "Walk-forward simulation with zero look-ahead bias, accounting for Indian delivery frictions "
        "(STT, Brokerage, GST, Stamp Duty) and 5 bps adverse slippage."
    )
    st.caption(backtest_caption)

    with st.form("backtest_form"):
        bt_c1, bt_c2, bt_c3 = st.columns(3)
        bt_symbol = bt_c1.selectbox(
            "Backtest Instrument",
            options=universe_symbols,
            index=universe_symbols.index(symbol) if symbol in universe_symbols else 0,
            key="bt_symbol_sel",
        )
        bt_period = bt_c2.selectbox("Lookback Window", options=["6mo", "1y", "2y"], index=1, key="bt_period_sel")
        bt_strategy = bt_c3.selectbox(
            "Quantitative Strategy",
            options=["EMA + MACD Confluence Swing", "Trend Following Breakout"],
            index=0,
            key="bt_strat_sel",
        )

        bt_c4, bt_c5, bt_c6 = st.columns(3)
        bt_capital = bt_c4.number_input(
            f"Starting Capital ({active_currency})",
            value=default_cap,
            step=5000.0 if is_us_market else 10000.0,
            key="bt_cap_input",
        )
        bt_risk = bt_c5.number_input(
            "Risk Per Trade (Fraction)",
            value=0.01,
            min_value=0.005,
            max_value=0.05,
            step=0.005,
            format="%.3f",
            key="bt_risk_input",
        )
        bt_slippage_opt = bt_c6.selectbox(
            "Adverse Slippage Model",
            options=["5.0 bps (Standard)", "2.0 bps (Tight/Institutional)", "10.0 bps (High Volatility)"],
            index=0,
            key="bt_slip_sel",
        )
        bt_slippage = float(bt_slippage_opt.split()[0])

        bt_submit = st.form_submit_button("▶️ Run Quantitative Backtest", use_container_width=True)

    res_cache_key = f"bt_result_{bt_symbol}"
    done_cache_key = f"bt_done_{bt_symbol}"

    # Reset cache controls
    if st.session_state.get(done_cache_key) or st.session_state.get(res_cache_key):
        r_c1, r_c2 = st.columns([4, 1])
        with r_c2:
            if st.button("🔄 Reset Simulation / New Run", key=f"btn_reset_bt_{bt_symbol}", use_container_width=True):
                st.session_state.pop(res_cache_key, None)
                st.session_state.pop(done_cache_key, None)
                st.rerun()

    bt_res = None
    if bt_submit:
        with st.spinner(f"Executing bar-by-bar simulation for {bt_symbol} ({bt_period})..."):
            bt_res = api_client.run_backtest(
                symbol=bt_symbol,
                timeframe="1d",
                period=bt_period,
                initial_capital_inr=bt_capital,
                max_risk_per_trade=bt_risk,
                slippage_bps=bt_slippage,
            )

        if bt_res and bt_res.get("error"):
            st.error(f"Backtest execution failed: {bt_res.get('message')}")
            st.session_state.pop(res_cache_key, None)
            st.session_state.pop(done_cache_key, None)
        elif bt_res:
            st.session_state[res_cache_key] = bt_res
            st.session_state[done_cache_key] = True
    elif st.session_state.get(done_cache_key):
        # Retrieve from cache to prevent the infinite rerun loop!
        bt_res = st.session_state.get(res_cache_key)

    if bt_res and not bt_res.get("error"):
        metrics = bt_res.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}

        total_return_pct = float(bt_res.get("total_return_pct", 0.0) or 0.0)
        total_bars = int(bt_res.get("total_bars", 0) or 0)
        years = max(0.1, total_bars / 252.0)
        cagr_pct = -100.0 if total_return_pct <= -100.0 else (((1.0 + total_return_pct / 100.0) ** (1.0 / years) - 1.0) * 100.0)

        trades_list = bt_res.get("trades", [])
        if not isinstance(trades_list, list):
            trades_list = []

        # Sortino Ratio
        returns = [float(t.get("return_pct", 0.0)) for t in trades_list if "return_pct" in t]
        neg_returns = [r for r in returns if r < 0]
        if len(neg_returns) >= 2:
            downside_var = sum(r ** 2 for r in neg_returns) / len(neg_returns)
            downside_dev = math.sqrt(downside_var)
            mean_ret = sum(returns) / len(returns)
            sortino_ratio = (mean_ret / downside_dev) * math.sqrt(min(252, len(returns))) if downside_dev > 1e-6 else None
        else:
            sortino_ratio = None

        # Calmar Ratio
        max_dd_pct = abs(float(metrics.get("max_drawdown_pct", 0.0) or 0.0))
        calmar_ratio = (cagr_pct / max_dd_pct) if max_dd_pct > 0.01 else None

        st.markdown(
            f"#### **Backtest Results: {bt_res.get('symbol')} "
            f"({bt_res.get('total_bars')} bars, {bt_res.get('strategy_name', bt_strategy)})**"
        )

        # 1. Primary Metrics Row (6 Columns)
        res_c1, res_c2, res_c3, res_c4, res_c5, res_c6 = st.columns(6)
        res_c1.metric(
            "Total Return",
            f"{total_return_pct:+.2f}%",
            f"{curr_sym}{float(bt_res.get('total_net_profit_inr', 0.0)):+,.2f}",
        )
        res_c2.metric(
            "Win Rate",
            f"{metrics.get('win_rate_pct', 0.0):.1f}%",
            f"{metrics.get('winning_trades', 0)}W / {metrics.get('losing_trades', 0)}L",
        )
        res_c3.metric("Profit Factor", f"{metrics.get('profit_factor', 0.0):.2f}")
        res_c4.metric("Friction Paid", f"{curr_sym}{float(metrics.get('total_charges_paid_inr', 0.0)):,.2f}")
        res_c5.metric(
            "Max Drawdown",
            f"{metrics.get('max_drawdown_pct', 0.0):.2f}%",
            f"-{curr_sym}{float(metrics.get('max_drawdown_inr', 0.0)):,.2f}",
        )
        sharpe_val = metrics.get("sharpe_ratio")
        res_c6.metric("Sharpe Ratio", f"{sharpe_val:.2f}" if isinstance(sharpe_val, (int, float)) else "N/A")

        # 2. Institutional Risk-Adjusted Analytics Row (4 Columns)
        adv_c1, adv_c2, adv_c3, adv_c4 = st.columns(4)
        adv_c1.metric("CAGR (Annualized)", f"{cagr_pct:+.2f}%")
        adv_c2.metric("Sortino Ratio", f"{sortino_ratio:.2f}" if sortino_ratio is not None else "N/A")
        adv_c3.metric("Calmar Ratio", f"{calmar_ratio:.2f}" if calmar_ratio is not None else "N/A")
        bm_name = "S&P 500 Buy & Hold" if is_us_market else "NIFTY 50 Buy & Hold"
        adv_c4.metric("Benchmark", bm_name, delta=f"{10.0 if is_us_market else 12.0:.1f}% Avg CAGR")

        # 3. Strategy Equity Curve vs Benchmark Overlay
        eq_curve_raw = bt_res.get("equity_curve", [])
        if eq_curve_raw:
            eq_ts = [str(pt.get("timestamp", "")) for pt in eq_curve_raw]
            eq_vals = [float(pt.get("equity", 0.0)) for pt in eq_curve_raw]

            # Generate synthetic benchmark buy-and-hold line from initial capital
            bm_annual_rate = 0.10 if is_us_market else 0.12
            bm_daily_rate = bm_annual_rate / 252.0
            bm_vals = [bt_capital * ((1.0 + bm_daily_rate) ** i) for i in range(len(eq_vals))]

            bt_fig = create_equity_curve_chart(
                eq_ts,
                eq_vals,
                initial_capital=bt_capital,
                benchmark_values=bm_vals,
                benchmark_name=bm_name,
            )
            if bt_fig:
                st.plotly_chart(bt_fig, use_container_width=True)

            # 4. Underwater Drawdown Curve
            peak = 0.0
            dd_series: List[float] = []
            for eq in eq_vals:
                if eq > peak:
                    peak = eq
                dd = ((eq - peak) / peak * 100.0) if peak > 0 else 0.0
                dd_series.append(round(dd, 2))

            dd_fig = create_underwater_drawdown_chart(eq_ts, dd_series)
            if dd_fig:
                st.plotly_chart(dd_fig, use_container_width=True)

        # 5. Closed Trades Log & CSV Download
        st.markdown(f"##### **Closed Trades Log ({len(trades_list)} Total Trades)**")
        if not trades_list:
            st.info("No trades triggered under strict strategy confluence rules during this window.")
        else:
            trade_csv_buf = io.StringIO()
            t_fieldnames = [
                "trade_id",
                "symbol",
                "side",
                "quantity",
                "entry_price",
                "exit_price",
                "exit_reason",
                "gross_pnl_inr",
                "total_charges_inr",
                "net_pnl_inr",
                "return_pct",
                "holding_period_bars",
                "entry_time",
                "exit_time",
            ]
            writer = csv.DictWriter(trade_csv_buf, fieldnames=t_fieldnames, extrasaction="ignore")
            writer.writeheader()
            for t_item in trades_list:
                writer.writerow(t_item)

            st.download_button(
                label="📥 Export Trades to CSV",
                data=trade_csv_buf.getvalue(),
                file_name=f"quantum_trader_backtest_{bt_symbol.lower()}_trades.csv",
                mime="text/csv",
                key="btn_download_backtest_trades_csv",
            )

            st.dataframe(
                trades_list,
                use_container_width=True,
                column_config={
                    "trade_id": "#",
                    "symbol": "Symbol",
                    "side": "Side",
                    "quantity": "Qty",
                    "entry_price": st.column_config.NumberColumn(f"Entry ({active_currency})", format=f"{curr_sym}%.2f"),
                    "exit_price": st.column_config.NumberColumn(f"Exit ({active_currency})", format=f"{curr_sym}%.2f"),
                    "exit_reason": "Exit Reason",
                    "net_pnl_inr": st.column_config.NumberColumn(f"Net P&L ({active_currency})", format=f"{curr_sym}%.2f"),
                    "total_charges_inr": st.column_config.NumberColumn(f"Charges ({active_currency})", format=f"{curr_sym}%.2f"),
                    "return_pct": st.column_config.NumberColumn("Return %", format="%.2f%%"),
                    "holding_period_bars": "Holding Bars",
                    "entry_time": "Entry Date",
                    "exit_time": "Exit Date",
                },
            )
