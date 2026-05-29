"""Order model - individual exchange orders."""
from sqlalchemy import Column, String, Float, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class Order(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "orders"

    trade_id = Column(UUID(as_uuid=True), ForeignKey("trades.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(30), nullable=False, index=True)
    exchange_order_id = Column(String(100), index=True)
    order_type = Column(Enum(OrderType), nullable=False)
    side = Column(Enum(OrderSide), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True)
    price = Column(Float)
    quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, default=0.0)
    average_fill_price = Column(Float)
    fee = Column(Float, default=0.0)
    fee_currency = Column(String(20))
    raw_response = Column(JSONB)  # Full exchange response

    # Relationships
    trade = relationship("Trade", back_populates="orders")

    def __repr__(self):
        return f"<Order(symbol={self.symbol}, type={self.order_type}, status={self.status})>"
