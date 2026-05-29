"""Trade model - complete trade lifecycle."""
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Enum, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin


class TradeDirection(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradeType(str, enum.Enum):
    SPOT = "spot"
    FUTURES = "futures"


class TradingModeType(str, enum.Enum):
    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"


class Trade(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trades"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(30), nullable=False, index=True)
    direction = Column(Enum(TradeDirection), nullable=False)
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING, nullable=False, index=True)
    trade_type = Column(Enum(TradeType), default=TradeType.SPOT, nullable=False)
    trading_mode = Column(Enum(TradingModeType), default=TradingModeType.PAPER, nullable=False, index=True)

    # Entry
    entry_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    entry_time = Column(String(50))

    # Exit
    exit_price = Column(Float)
    exit_time = Column(String(50))

    # Risk Management (MANDATORY)
    stop_loss = Column(Float, nullable=False)  # NEVER null
    take_profit_1 = Column(Float)
    take_profit_2 = Column(Float)
    take_profit_3 = Column(Float)
    trailing_stop = Column(Float)
    trailing_stop_distance = Column(Float)

    # P&L
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    fee_paid = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)

    # Risk Metrics
    risk_reward_ratio = Column(Float)
    risk_amount = Column(Float)  # Amount at risk in USD
    risk_percent = Column(Float)  # Risk as % of balance

    # Exchange data
    exchange_order_id = Column(String(100))
    leverage = Column(Float, default=1.0)

    # Metadata
    notes = Column(Text)
    tags = Column(JSONB)
    signal_data = Column(JSONB)  # Technical analysis signals that triggered trade

    # Relationships
    user = relationship("User", back_populates="trades")
    orders = relationship("Order", back_populates="trade", cascade="all, delete-orphan")
    strategy = relationship("Strategy", back_populates="trades")

    def __repr__(self):
        return f"<Trade(symbol={self.symbol}, direction={self.direction}, status={self.status})>"
