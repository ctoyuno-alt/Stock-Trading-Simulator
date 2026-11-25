"""
Tab 5: Trade Ledger & Performance Analytics for Quantum Trader.
Displays portfolio performance metrics, Sharpe ratio, drawdown,
authentic multi-point reconstructed equity curve chart, searchable/filterable
order history, and CSV download.
"""

import csv
import io
from typing import Any, Dict

try:
    import streamlit as st
except ImportError:
    st = None

from dashboard.components.charts import create_equity_curve_chart
from trading.metrics import reconstruct_multipoint_equity_curve


def render_tab(
    api_client: Any,
    state: Dict[str, Any],
    market: str,
    symbol: str,
    timeframe: str,
) -> None:
    """
    Renders Tab 5: Trade Ledger & Performance Analytics.
    """
    active_currency = state.get("active_currency") or "INR"
    curr_sym = state.get("curr_sym", "₹")
    portfolio = state.get("portfolio", {})
    if not isinstance(portfolio, dict):
        portfolio = {}

    default_cap = float(state.get("default_cap", 100000.0) or 100000.0)
    init_cap = float(portfolio.get("initial_capital_inr", default_cap) or default_cap)
    equity_val = float(portfolio.get("equity_inr", state.get("equity_val", default_cap)) or default_cap)
    unrealized_pnl = float(portfolio.get("total_unrealized_pnl_inr", 0.0) or 0.0)

    st.markdown(f"### **Trade Ledger & Performance Analytics ({active_currency})**")

    metrics_data = api_client.get_metrics(currency=active_currency)
    if not isinstance(metrics_data, dict) or metrics_data.get("error"):
        metrics_data = {}

    orders_data = api_client.get_orders(limit=100, currency=active_currency)
    if not isinstance(orders_data, list):
        orders_data = []

    closed_positions = api_client.get_positions(status_filter="CLOSED", currency=active_currency)
    if not isinstance(closed_positions, list):
        closed_positions = []

    # 1. Floating Exposure & Portfolio P&L Overview (3 Columns)
    k_col1, k_col2, k_col3 = st.columns(3)
    k_col1.metric(
        "Open Floating P&L",
        f"{curr_sym}{unrealized_pnl:+,.2f}",
        f"{portfolio.get('open_positions_count', 0)} Active Positions",
    )
    k_col2.metric(
        "Net Closed Realized P&L",
        f"{curr_sym}{metrics_data.get('total_net_realized_pnl_inr', 0.0):+,.2f}",
        f"{metrics_data.get('total_trades', len(closed_positions))} Closed Trades",
    )
    k_col3.metric(
        "Total Account P&L",
        f"{curr_sym}{portfolio.get('total_pnl_inr', (equity_val - init_cap)):+,.2f}",
        delta=f"{portfolio.get('return_on_initial_capital_pct', ((equity_val - init_cap) / init_cap * 100.0 if init_cap else 0.0)):+.2f}%",
    )

    st.markdown("##### **Institutional Performance & Efficiency Metrics**")
    # 2. KPI Summary Cards (7 Columns)
    m_c1, m_c2, m_c3, m_c4, m_c5, m_c6, m_c7 = st.columns(7)
    m_c1.metric(
        "Win Rate",
        f"{metrics_data.get('win_rate_pct', 0.0):.1f}%",
        f"{metrics_data.get('winning_trades', 0)}W / {metrics_data.get('losing_trades', 0)}L",
    )
    m_c2.metric("Profit Factor", f"{metrics_data.get('profit_factor', 0.0):.2f}")
    m_c3.metric("Realized P&L", f"{curr_sym}{metrics_data.get('total_net_realized_pnl_inr', 0.0):+,.2f}")
    m_c4.metric("Unrealized P&L", f"{curr_sym}{unrealized_pnl:+,.2f}")
    m_c5.metric("Charges & Taxes", f"{curr_sym}{metrics_data.get('total_charges_paid_inr', 0.0):,.2f}")
    m_c6.metric(
        "Max Drawdown",
        f"{metrics_data.get('max_drawdown_pct', 0.0):.2f}%",
        f"-{curr_sym}{metrics_data.get('max_drawdown_inr', 0.0):,.2f}",
    )
    sharpe_display = metrics_data.get("sharpe_ratio")
    m_c7.metric("Sharpe Ratio", f"{sharpe_display:.2f}" if isinstance(sharpe_display, (int, float)) else "N/A")

    st.divider()

    # 3. Authentic Multi-Point Historical Equity Curve (N+2 Points)
    st.markdown(f"#### **Portfolio Equity Progression & Drawdown Trajectory ({active_currency})**")

    # Sequence closed trade P&Ls chronologically (oldest to newest)
    sorted_closed = sorted(
        closed_positions,
        key=lambda x: str(x.get("closed_at") or x.get("opened_at") or ""),
    )
    pnl_series = [float(p.get("realized_pnl_inr", 0.0) or 0.0) for p in sorted_closed]
    ts_labels = [
        str(p.get("closed_at") or p.get("opened_at") or f"Trade {i + 1}")
        for i, p in enumerate(sorted_closed)
    ]

    recon_curve = reconstruct_multipoint_equity_curve(
        initial_capital=init_cap,
        closed_trades_pnl=pnl_series,
        unrealized_pnl=unrealized_pnl,
        trade_timestamps=ts_labels,
    )

    eq_col_chart, eq_col_stats = st.columns([4, 1])
    with eq_col_chart:
        eq_fig = create_equity_curve_chart(
            recon_curve["labels"],
            recon_curve["equity_curve"],
            initial_capital=init_cap,
        )
        if eq_fig:
            st.plotly_chart(eq_fig, use_container_width=True)

    with eq_col_stats:
        st.markdown("##### **Curve Analytics**")
        st.metric("Total Curve Points", f"{recon_curve['total_points']}")
        st.metric("Peak-to-Trough DD", f"{recon_curve['max_drawdown_pct']:.2f}%")
        st.metric("Max DD Amount", f"{curr_sym}{recon_curve['max_drawdown_amount']:,.2f}")
        st.metric("Terminal Equity", f"{curr_sym}{recon_curve['final_equity']:,.2f}")

    st.divider()

    # 4. Searchable, Filterable Executed Orders Audit Trail & CSV Download
    hdr_c1, hdr_c2 = st.columns([3, 1])
    hdr_c1.markdown(f"#### **Executed Virtual Orders Audit Trail ({active_currency})**")

    # Interactive Filters
    flt_col1, flt_col2, flt_col3 = st.columns(3)
    status_choices = ["ALL", "FILLED", "CANCELLED", "REJECTED"]
    selected_status = flt_col1.selectbox("Filter by Status", status_choices, index=0, key="ledger_flt_status")

    side_choices = ["ALL", "BUY", "SELL"]
    selected_side = flt_col2.selectbox("Filter by Side", side_choices, index=0, key="ledger_flt_side")

    available_symbols = sorted(list({str(o.get("symbol", "")).upper() for o in orders_data if o.get("symbol")}))
    symbol_choices = ["ALL"] + available_symbols
    selected_symbol = flt_col3.selectbox("Filter by Symbol", symbol_choices, index=0, key="ledger_flt_symbol")

    # Apply In-Memory Filtering
    filtered_orders = []
    for o in orders_data:
        if not isinstance(o, dict):
            continue
        o_status = str(o.get("status", "FILLED")).upper()
        o_side = str(o.get("side", "")).upper()
        o_sym = str(o.get("symbol", "")).upper()

        if selected_status != "ALL" and o_status != selected_status:
            continue
        if selected_side != "ALL" and o_side != selected_side:
            continue
        if selected_symbol != "ALL" and o_sym != selected_symbol:
            continue
        filtered_orders.append(o)

    # Export to CSV
    csv_buffer = io.StringIO()
    fieldnames = [
        "id",
        "client_order_id",
        "symbol",
        "side",
        "status",
        "quantity",
        "executed_price",
        "turnover_inr",
        "total_charges_inr",
        "net_cash_impact_inr",
        "executed_at",
        "reason",
    ]
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for o_row in (filtered_orders if filtered_orders else orders_data):
        writer.writerow(o_row)

    with hdr_c2:
        st.download_button(
            label="📥 Export Ledger to CSV",
            data=csv_buffer.getvalue(),
            file_name=f"quantum_trader_orders_{active_currency.lower()}.csv",
            mime="text/csv",
            key="btn_download_ledger_csv",
            use_container_width=True,
        )

    if not filtered_orders:
        if not orders_data:
            st.info(f"No {active_currency} orders executed yet in this session.")
        else:
            st.warning("No orders match the selected filters.")
    else:
        st.caption(f"Displaying {len(filtered_orders)} of {len(orders_data)} recorded orders.")
        st.dataframe(
            filtered_orders,
            use_container_width=True,
            column_config={
                "client_order_id": "Order ID",
                "symbol": "Symbol",
                "side": "Side",
                "status": "Status",
                "quantity": "Qty",
                "executed_price": st.column_config.NumberColumn(
                    f"Fill Price ({active_currency})",
                    format=f"{curr_sym}%.2f",
                ),
                "turnover_inr": st.column_config.NumberColumn(
                    f"Turnover ({active_currency})",
                    format=f"{curr_sym}%.2f",
                ),
                "total_charges_inr": st.column_config.NumberColumn(
                    f"Charges ({active_currency})",
                    format=f"{curr_sym}%.2f",
                ),
                "net_cash_impact_inr": st.column_config.NumberColumn(
                    f"Net Cash ({active_currency})",
                    format=f"{curr_sym}%.2f",
                ),
                "executed_at": "Execution Time",
                "reason": "Reason",
            },
        )
