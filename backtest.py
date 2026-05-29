"""Backtest models."""
from sqlalchemy import Column, String, Float, ForeignKey, Enum, Text, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from .base import Base, TimestampMixin, UUIDMixin


class BacktestStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Backtest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "backtests"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=False, index=True)
    name = Column(String(200))
    status = Column(Enum(BacktestStatus), default=BacktestStatus.QUEUED, nullable=False)

    # Period
    start_date = Column(String(30), nullable=False)
    end_date = Column(String(30), nullable=False)
    timeframe = Column(String(10), nullable=False)
    symbols = Column(JSONB, nullable=False)

    # Capital
    initial_balance = Column(Float, nullable=False, default=10000.0)
    final_balance = Column(Float)

    # Performance metrics
    total_return_percent = Column(Float)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    calmar_ratio = Column(Float)
    max_drawdown_percent = Column(Float)
    max_drawdown_duration_days = Column(Integer)
    avg_trade_duration_hours = Column(Float)
    avg_win = Column(Float)
    avg_loss = Column(Float)
    best_trade = Column(Float)
    worst_trade = Column(Float)
    total_fees_paid = Column(Float)

    # Configuration used
    strategy_params = Column(JSONB)

    # Equity curve data (stored as compressed JSON)
    equity_curve = Column(JSONB)
    drawdown_curve = Column(JSONB)

    error_message = Column(Text)

    # Relationships
    strategy = relationship("Strategy", back_populates="backtests")
    backtest_trades = relationship("BacktestTrade", back_populates="backtest", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Backtest(strategy={self.strategy_id}, status={self.status})>"


class BacktestTrade(Base, UUIDMixin, TimestampMixin):
    """Individual trades within a backtest."""
    __tablename__ = "backtest_trades"

    backtest_id = Column(UUID(as_uuid=True), ForeignKey("backtests.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(30), nullable=False)
    direction = Column(String(10), nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    quantity = Column(Float, nullable=False)
    entry_time = Column(String(50))
    exit_time = Column(String(50))
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float)
    pnl = Column(Float)
    pnl_percent = Column(Float)
    exit_reason = Column(String(50))  # stop_loss, take_profit, signal, trailing_stop
    fees = Column(Float, default=0.0)
    signal_data = Column(JSONB)

    # Relationships
    backtest = relationship("Backtest", back_populates="backtest_trades")
