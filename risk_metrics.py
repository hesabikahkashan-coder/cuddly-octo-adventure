"""Risk metrics models."""
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin, UUIDMixin


class RiskMetrics(Base, UUIDMixin, TimestampMixin):
    """Real-time risk metrics per user."""
    __tablename__ = "risk_metrics"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exchange = Column(String(50), nullable=False)

    # Balance
    total_balance = Column(Float)
    available_balance = Column(Float)
    used_margin = Column(Float)

    # Current risk state
    open_trades_count = Column(Integer, default=0)
    daily_pnl = Column(Float, default=0.0)
    daily_pnl_percent = Column(Float, default=0.0)
    daily_drawdown_percent = Column(Float, default=0.0)
    max_daily_drawdown_reached = Column(Boolean, default=False)

    # Session risk
    session_pnl = Column(Float, default=0.0)
    total_exposure = Column(Float, default=0.0)
    total_exposure_percent = Column(Float, default=0.0)

    # Risk state
    trading_halted = Column(Boolean, default=False)
    halt_reason = Column(String(500))
    last_updated = Column(String(50))

    # Relationships
    user = relationship("User", back_populates="risk_metrics")


class DailyRiskSnapshot(Base, UUIDMixin, TimestampMixin):
    """Daily snapshot of risk metrics for historical analysis."""
    __tablename__ = "daily_risk_snapshots"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(20), nullable=False, index=True)
    exchange = Column(String(50), nullable=False)

    opening_balance = Column(Float)
    closing_balance = Column(Float)
    daily_pnl = Column(Float)
    daily_pnl_percent = Column(Float)
    max_drawdown_percent = Column(Float)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_fees = Column(Float, default=0.0)
    largest_win = Column(Float)
    largest_loss = Column(Float)
    snapshot_data = Column(JSONB)
