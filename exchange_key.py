"""Exchange API Key model - encrypted storage."""
from sqlalchemy import Column, String, Boolean, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin


class ExchangeName(str, enum.Enum):
    BINANCE = "binance"
    BYBIT = "bybit"


class TradingMode(str, enum.Enum):
    SPOT = "spot"
    FUTURES = "futures"
    BOTH = "both"


class ExchangeApiKey(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "exchange_api_keys"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exchange = Column(Enum(ExchangeName), nullable=False)
    label = Column(String(100))  # User-defined label
    encrypted_api_key = Column(String(500), nullable=False)  # AES-256 encrypted
    encrypted_api_secret = Column(String(500), nullable=False)  # AES-256 encrypted
    trading_mode = Column(Enum(TradingMode), default=TradingMode.SPOT, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_testnet = Column(Boolean, default=False, nullable=False)
    withdrawals_enabled = Column(Boolean, default=False, nullable=False)  # ALWAYS False
    permissions = Column(String(500))  # JSON string of allowed permissions
    last_validated = Column(String(50))

    # Relationships
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<ExchangeApiKey(exchange={self.exchange}, user_id={self.user_id})>"
