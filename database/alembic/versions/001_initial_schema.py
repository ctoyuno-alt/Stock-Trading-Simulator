"""initial schema setup

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-16 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Accounts
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_name", sa.String(length=64), nullable=False),
        sa.Column("initial_capital_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("cash_balance_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("equity_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_name"),
    )

    # 2. Positions
    op.create_table(
        "positions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("current_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("stop_loss_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("take_profit_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("status", sa.Enum("OPEN", "CLOSED", name="positionstatus"), nullable=False),
        sa.Column("realized_pnl_inr", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unrealized_pnl_inr", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_charges_incurred_inr", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_positions_symbol", "positions", ["symbol"], unique=False)
    op.create_index("ix_positions_status", "positions", ["status"], unique=False)

    # 3. Orders
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("position_id", sa.BigInteger(), nullable=True),
        sa.Column("client_order_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("side", sa.Enum("BUY", "SELL", name="orderside"), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("requested_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("executed_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "FILLED", "REJECTED", "CANCELLED", name="orderstatus"), nullable=False),
        sa.Column("stop_loss_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("take_profit_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("turnover_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("slippage_inr", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("brokerage_inr", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("stt_tax_inr", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("exchange_turnover_inr", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("sebi_charges_inr", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("stamp_duty_inr", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("gst_inr", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("total_charges_inr", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("net_cash_impact_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id"),
    )
    op.create_index("ix_orders_symbol", "orders", ["symbol"], unique=False)
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)

    # 4. Portfolio Snapshots
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cash_balance_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("positions_market_value_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("equity_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("open_positions_count", sa.BigInteger(), nullable=False),
        sa.Column("total_realized_pnl_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_unrealized_pnl_inr", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("cumulative_drawdown_pct", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_snapshots_timestamp", "portfolio_snapshots", ["timestamp"], unique=False)

    # 5. Market Candles
    op.create_table(
        "market_candles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("high", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("low", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("close", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("vwap", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_candle_symbol_timeframe_ts",
        "market_candles",
        ["symbol", "timeframe", "timestamp"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("market_candles")
    op.drop_table("portfolio_snapshots")
    op.drop_table("orders")
    op.drop_table("positions")
    op.drop_table("accounts")
    op.execute("DROP TYPE IF EXISTS orderside")
    op.execute("DROP TYPE IF EXISTS orderstatus")
    op.execute("DROP TYPE IF EXISTS positionstatus")
