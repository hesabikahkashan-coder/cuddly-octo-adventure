"""Notification models."""
from sqlalchemy import Column, String, Boolean, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin


class NotificationType(str, enum.Enum):
    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"
    TAKE_PROFIT_HIT = "take_profit_hit"
    STOP_LOSS_HIT = "stop_loss_hit"
    RISK_WARNING = "risk_warning"
    API_ERROR = "api_error"
    SYSTEM_ERROR = "system_error"
    DAILY_REPORT = "daily_report"
    WEEKLY_REPORT = "weekly_report"
    DRAWDOWN_ALERT = "drawdown_alert"
    POSITION_LIQUIDATION_WARNING = "position_liquidation_warning"


class NotificationChannel(str, enum.Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    IN_APP = "in_app"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class Notification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = Column(Enum(NotificationType), nullable=False, index=True)
    channel = Column(Enum(NotificationChannel), nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSONB)  # Extra context data
    sent_at = Column(String(50))
    read_at = Column(String(50))
    error = Column(Text)

    # Relationships
    user = relationship("User", back_populates="notifications")


class NotificationConfig(Base, UUIDMixin, TimestampMixin):
    """User notification preferences."""
    __tablename__ = "notification_configs"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(Enum(NotificationChannel), nullable=False)
    is_enabled = Column(Boolean, default=True)

    # Channel-specific settings
    telegram_chat_id = Column(String(100))
    email_address = Column(String(255))
    whatsapp_number = Column(String(30))

    # Event settings
    notify_trade_opened = Column(Boolean, default=True)
    notify_trade_closed = Column(Boolean, default=True)
    notify_stop_loss = Column(Boolean, default=True)
    notify_take_profit = Column(Boolean, default=True)
    notify_risk_warnings = Column(Boolean, default=True)
    notify_daily_report = Column(Boolean, default=True)
    notify_weekly_report = Column(Boolean, default=True)
    notify_errors = Column(Boolean, default=True)
