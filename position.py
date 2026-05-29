"""Position model - current open positions."""
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin


class PositionSide(str, enum.Enum):
    LONG = "long"
    SHORT = "short"
    BOTH = "both"  # Hedge mode


class Position(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "positions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(30), nullable=False, index=True)
    side = Column(Enum(PositionSide), nullable=False)
    is_open = Column(Boolean, default=True, nullable=False, index=True)

    # Position size
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float)
    leverage = Column(Float, default=1.0)
    notional_value = Column(Float)

    # Risk
    liquidation_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)

    # P&L
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_percent = Column(Float, default=0.0)
    margin_used = Column(Float)

    # Sync
    last_synced = Column(String(50))
    exchange_data = Column(JSONB)

    # Relationships
    user = relationship("User", back_populates="positions")

    def __repr__(self):
        return f"<Position(symbol={self.symbol}, side={self.side}, qty={self.quantity})>"
