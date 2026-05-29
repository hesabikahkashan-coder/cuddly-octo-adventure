"""Audit log model for compliance and security tracking."""
from sqlalchemy import Column, String, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin


class AuditAction(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    TWO_FA_ENABLED = "two_fa_enabled"
    TWO_FA_DISABLED = "two_fa_disabled"
    API_KEY_ADDED = "api_key_added"
    API_KEY_DELETED = "api_key_deleted"
    TRADE_PLACED = "trade_placed"
    TRADE_CANCELLED = "trade_cancelled"
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"
    SETTINGS_CHANGED = "settings_changed"
    RISK_LIMIT_CHANGED = "risk_limit_changed"
    TRADING_HALTED = "trading_halted"
    TRADING_RESUMED = "trading_resumed"


class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(Enum(AuditAction), nullable=False, index=True)
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    resource_type = Column(String(100))  # e.g., 'trade', 'strategy', 'api_key'
    resource_id = Column(String(100))
    details = Column(JSONB)  # Action-specific details
    result = Column(String(20))  # success, failure
    error_message = Column(Text)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(action={self.action}, user_id={self.user_id})>"
