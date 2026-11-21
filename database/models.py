"""
SQLAlchemy 2.0 Async ORM Models for AI Paper Trading Platform.

Schema defines:
- AccountModel: Equity, available cash, currency (INR).
- PositionModel: Open and closed positions with stop-loss/take-profit.
- OrderModel: Virtual execution audit trail with itemized Indian tax breakdowns.
- PortfolioSnapshotModel: Periodic equity curve for drawdown and Sharpe ratio tracking.
- MarketCandleModel: Historical and ingested OHLCV cache.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    salt: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.TRADER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    api_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    accounts: Mapped[List["AccountModel"]] = relationship("AccountModel", back_populates="user")


class PositionStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class AccountModel(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    account_name: Mapped[str] = mapped_column(String(64), unique=True, default="Primary Paper Account")
    initial_capital_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("100000.00"), nullable=False)
    cash_balance_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("100000.00"), nullable=False)
    equity_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("100000.00"), nullable=False)
    daily_starting_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), default=Decimal("100000.00"), nullable=True)
    circuit_breaker_tripped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    circuit_breaker_reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped[Optional["UserModel"]] = relationship("UserModel", back_populates="accounts")
    positions: Mapped[List["PositionModel"]] = relationship("PositionModel", back_populates="account")
    orders: Mapped[List["OrderModel"]] = relationship("OrderModel", back_populates="account")
    snapshots: Mapped[List["PortfolioSnapshotModel"]] = relationship("PortfolioSnapshotModel", back_populates="account")


class PositionModel(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), default="NSE", nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    average_entry_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stop_loss_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[PositionStatus] = mapped_column(
        SQLEnum(PositionStatus), default=PositionStatus.OPEN, index=True, nullable=False
    )
    realized_pnl_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    unrealized_pnl_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_charges_incurred_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    account: Mapped["AccountModel"] = relationship("AccountModel", back_populates="positions")
    orders: Mapped[List["OrderModel"]] = relationship("OrderModel", back_populates="position")


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), nullable=False)
    position_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("positions.id"), nullable=True)
    client_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), default="NSE", nullable=False)
    side: Mapped[OrderSide] = mapped_column(SQLEnum(OrderSide), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    executed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus), default=OrderStatus.PENDING, index=True, nullable=False
    )

    # Risk constraints attached to the order
    stop_loss_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    take_profit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    # Indian Frictions and Tax Breakdown
    turnover_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    slippage_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    brokerage_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    stt_tax_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    exchange_turnover_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    sebi_charges_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    stamp_duty_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    gst_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    total_charges_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    net_cash_impact_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["AccountModel"] = relationship("AccountModel", back_populates="orders")
    position: Mapped[Optional["PositionModel"]] = relationship("PositionModel", back_populates="orders")


class PortfolioSnapshotModel(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False
    )
    cash_balance_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    positions_market_value_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    equity_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    open_positions_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_realized_pnl_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    total_unrealized_pnl_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    cumulative_drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0000"), nullable=False)

    account: Mapped["AccountModel"] = relationship("AccountModel", back_populates="snapshots")


class MarketCandleModel(Base):
    __tablename__ = "market_candles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), default="NSE", nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), default="1d", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vwap: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="yfinance", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("idx_candle_symbol_timeframe_ts", "symbol", "timeframe", "timestamp", unique=True),
    )
