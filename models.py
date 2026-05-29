"""Risk engine data models and types."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class RiskStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_ADJUSTMENT = "needs_adjustment"
    TRADING_HALTED = "trading_halted"


class RejectionReason(str, Enum):
    NO_STOP_LOSS = "no_stop_loss"
    POOR_RISK_REWARD = "poor_risk_reward"
    DAILY_DRAWDOWN_EXCEEDED = "daily_drawdown_exceeded"
    MAX_TRADES_REACHED = "max_trades_reached"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    POSITION_TOO_LARGE = "position_too_large"
    TRADING_HALTED = "trading_halted"
    CORRELATED_POSITION = "correlated_position"
    INVALID_STOP_LOSS = "invalid_stop_loss"
    RISK_AMOUNT_TOO_HIGH = "risk_amount_too_high"


@dataclass
class TradeSignal:
    """Incoming trade signal to be validated by risk engine."""
    symbol: str
    direction: str  # "long" or "short"
    exchange: str
    entry_price: float
    stop_loss: Optional[float]  # MUST be provided
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    quantity: Optional[float] = None  # Can be auto-calculated
    risk_percent: Optional[float] = None  # % of balance to risk
    strategy_id: Optional[str] = None
    timeframe: str = "1h"
    signal_metadata: Dict[str, Any] = field(default_factory=dict)
    use_trailing_stop: bool = False
    trailing_stop_percent: Optional[float] = None
    leverage: float = 1.0
    trade_type: str = "spot"  # spot or futures


@dataclass
class RiskValidationResult:
    """Result of risk engine validation."""
    status: RiskStatus
    rejection_reasons: List[RejectionReason] = field(default_factory=list)
    rejection_messages: List[str] = field(default_factory=list)
    
    # Calculated values
    approved_quantity: Optional[float] = None
    approved_stop_loss: Optional[float] = None
    approved_take_profit_1: Optional[float] = None
    approved_take_profit_2: Optional[float] = None
    approved_take_profit_3: Optional[float] = None
    risk_amount_usd: Optional[float] = None
    risk_percent: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    position_size_usd: Optional[float] = None
    
    # Risk metrics at time of validation
    current_daily_drawdown: Optional[float] = None
    open_trades_count: Optional[int] = None
    available_balance: Optional[float] = None
    
    @property
    def is_approved(self) -> bool:
        return self.status == RiskStatus.APPROVED

    def add_rejection(self, reason: RejectionReason, message: str):
        self.rejection_reasons.append(reason)
        self.rejection_messages.append(message)
        if self.status != RiskStatus.TRADING_HALTED:
            self.status = RiskStatus.REJECTED
