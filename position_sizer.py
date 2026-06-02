"""
Position Sizer - Calculates optimal position sizes based on risk parameters.
Uses Kelly Criterion, Fixed Fractional, and ATR-based methods.
"""
from typing import Optional
import math
from .logger import get_logger

logger = get_logger(__name__)


class PositionSizer:
    """
    Calculates position sizes using various risk management methodologies.
    All methods ensure capital is protected based on stop loss distance.
    """

    @staticmethod
    def fixed_fractional(
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
        leverage: float = 1.0
    ) -> float:
        """
        Fixed Fractional Position Sizing.
        Risk exactly X% of account on each trade.
        
        Args:
            account_balance: Total account balance in USD
            risk_percent: Percentage of account to risk (e.g., 1.0 for 1%)
            entry_price: Entry price of the asset
            stop_loss: Stop loss price
            leverage: Position leverage (default 1.0 for spot)
        
        Returns:
            Position quantity in asset units
        """
        if entry_price <= 0 or stop_loss <= 0:
            raise ValueError("Prices must be positive")
        
        risk_amount = account_balance * (risk_percent / 100)
        stop_distance = abs(entry_price - stop_loss)
        
        if stop_distance == 0:
            raise ValueError("Stop loss cannot equal entry price")
        
        # Quantity = Risk Amount / (Stop Distance * leverage consideration)
        quantity = (risk_amount * leverage) / stop_distance
        
        logger.debug(
            f"Fixed fractional: balance={account_balance}, risk%={risk_percent}, "
            f"entry={entry_price}, sl={stop_loss}, qty={quantity:.6f}"
        )
        return quantity

    @staticmethod
    def atr_based(
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        atr_value: float,
        atr_multiplier: float = 2.0,
        leverage: float = 1.0
    ) -> tuple[float, float]:
        """
        ATR-Based Position Sizing with dynamic stop loss.
        
        Returns:
            Tuple of (quantity, calculated_stop_loss)
        """
        stop_distance = atr_value * atr_multiplier
        stop_loss = entry_price - stop_distance  # For long positions

        risk_amount = account_balance * (risk_percent / 100)
        quantity = (risk_amount * leverage) / stop_distance

        return quantity, stop_loss

    @staticmethod
    def kelly_criterion(
        account_balance: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        max_risk_percent: float = 2.0
    ) -> float:
        """
        Kelly Criterion position sizing.
        Returns conservative (half-Kelly) risk percentage.
        
        Args:
            win_rate: Historical win rate (0.0 to 1.0)
            avg_win: Average win amount
            avg_loss: Average loss amount
            max_risk_percent: Maximum allowed risk regardless of Kelly
        
        Returns:
            Risk amount in USD
        """
        if avg_loss == 0:
            return 0.0
        
        b = avg_win / avg_loss  # Win/Loss ratio
        p = win_rate
        q = 1 - win_rate
        
        # Full Kelly
        kelly = (b * p - q) / b
        
        # Half Kelly for safety
        half_kelly = kelly / 2
        
        # Apply maximum risk cap
        kelly_percent = min(half_kelly * 100, max_risk_percent)
        kelly_percent = max(kelly_percent, 0)  # Never negative
        
        return account_balance * (kelly_percent / 100)

    @staticmethod
    def validate_position_size(
        quantity: float,
        entry_price: float,
        account_balance: float,
        max_position_percent: float = 10.0
    ) -> tuple[bool, str]:
        """
        Validate that position size doesn't exceed maximum allowed.
        
        Returns:
            Tuple of (is_valid, message)
        """
        position_value = quantity * entry_price
        position_percent = (position_value / account_balance) * 100
        
        if position_percent > max_position_percent:
            return False, (
                f"Position size {position_percent:.1f}% exceeds maximum "
                f"allowed {max_position_percent:.1f}%"
            )
        return True, "Position size is valid"

    @staticmethod
    def calculate_risk_reward(
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        direction: str = "long"
    ) -> float:
        """Calculate Risk/Reward ratio."""
        if direction == "long":
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:
            risk = stop_loss - entry_price
            reward = entry_price - take_profit
        
        if risk <= 0:
            return 0.0
        
        return reward / risk

    @staticmethod
    def round_quantity(quantity: float, step_size: float) -> float:
        """Round quantity to exchange's minimum step size."""
        if step_size <= 0:
            return quantity
        decimal_places = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
        return round(math.floor(quantity / step_size) * step_size, decimal_places)
