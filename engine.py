"""
NWH Risk Engine - Core risk validation and management.
THIS IS THE MOST CRITICAL MODULE. Every trade passes through here.
NO TRADE EXECUTES WITHOUT PASSING ALL RISK CHECKS.
"""
import asyncio
from typing import Optional, Dict, List
from ..core.logging import get_logger, get_trade_logger
from ..core.config import settings
from .models import TradeSignal, RiskValidationResult, RiskStatus, RejectionReason
from .position_sizer import PositionSizer
from .drawdown_guard import DrawdownGuard

logger = get_logger(__name__)
trade_logger = get_trade_logger()


class RiskEngine:
    """
    Central risk management engine.
    
    Validates every trade signal before execution.
    Manages position sizing, drawdown, and circuit breakers.
    
    RULES (NON-NEGOTIABLE):
    1. Every trade MUST have a stop loss
    2. Risk/Reward must meet minimum threshold
    3. Daily drawdown must not exceed limit
    4. Max simultaneous trades must not be exceeded
    5. Position size must not exceed account % limit
    """

    def __init__(
        self,
        max_simultaneous_trades: int = None,
        max_daily_drawdown_percent: float = None,
        default_risk_per_trade_percent: float = None,
        min_risk_reward_ratio: float = None,
        max_position_size_percent: float = None,
    ):
        self.max_simultaneous_trades = max_simultaneous_trades or settings.trading.MAX_SIMULTANEOUS_TRADES
        self.max_daily_drawdown_percent = max_daily_drawdown_percent or settings.trading.MAX_DAILY_DRAWDOWN_PERCENT
        self.default_risk_per_trade_percent = default_risk_per_trade_percent or settings.trading.DEFAULT_RISK_PER_TRADE_PERCENT
        self.min_risk_reward_ratio = min_risk_reward_ratio or settings.trading.MIN_RISK_REWARD_RATIO
        self.max_position_size_percent = max_position_size_percent or settings.trading.MAX_POSITION_SIZE_PERCENT

        self.position_sizer = PositionSizer()
        self.drawdown_guard = DrawdownGuard(
            max_daily_drawdown_percent=self.max_daily_drawdown_percent
        )

        # In-memory state (should be synced with DB in production)
        self._open_trades: Dict[str, List[str]] = {}  # user_id -> [trade_ids]
        self._lock = asyncio.Lock()

    async def validate_trade(
        self,
        signal: TradeSignal,
        user_id: str,
        account_balance: float,
        open_trade_count: int,
        daily_pnl_percent: float = 0.0,
    ) -> RiskValidationResult:
        """
        MAIN ENTRY POINT: Validate a trade signal against all risk rules.
        
        This method is the gatekeeper. It returns a RiskValidationResult
        with status APPROVED only if ALL checks pass.
        """
        async with self._lock:
            result = RiskValidationResult(
                status=RiskStatus.APPROVED,
                current_daily_drawdown=abs(daily_pnl_percent) if daily_pnl_percent < 0 else 0,
                open_trades_count=open_trade_count,
                available_balance=account_balance,
            )

            # ============================================================
            # CHECK 1: Trading halt check (circuit breaker)
            # ============================================================
            if self.drawdown_guard.is_trading_halted(user_id):
                reason = self.drawdown_guard.get_halt_reason(user_id)
                result.status = RiskStatus.TRADING_HALTED
                result.add_rejection(RejectionReason.TRADING_HALTED, f"Trading halted: {reason}")
                trade_logger.log_trade_rejected("trading_halted", {"user_id": user_id, "symbol": signal.symbol})
                return result

            # ============================================================
            # CHECK 2: MANDATORY STOP LOSS (NON-NEGOTIABLE)
            # ============================================================
            if signal.stop_loss is None:
                result.add_rejection(
                    RejectionReason.NO_STOP_LOSS,
                    "CRITICAL: Stop loss is MANDATORY. Trade rejected."
                )
                trade_logger.log_trade_rejected("no_stop_loss", {"symbol": signal.symbol, "user_id": user_id})
                return result  # Hard stop — no further checks needed

            # ============================================================
            # CHECK 3: Stop loss validity
            # ============================================================
            sl_valid, sl_message = self._validate_stop_loss(signal)
            if not sl_valid:
                result.add_rejection(RejectionReason.INVALID_STOP_LOSS, sl_message)

            # ============================================================
            # CHECK 4: Daily drawdown limit
            # ============================================================
            current_drawdown = self.drawdown_guard.get_daily_drawdown(user_id)
            if current_drawdown >= self.max_daily_drawdown_percent:
                await self.drawdown_guard._halt_trading(
                    user_id,
                    f"Daily drawdown {current_drawdown:.2f}% >= limit {self.max_daily_drawdown_percent}%"
                )
                result.status = RiskStatus.TRADING_HALTED
                result.add_rejection(
                    RejectionReason.DAILY_DRAWDOWN_EXCEEDED,
                    f"Daily drawdown limit reached: {current_drawdown:.2f}%"
                )
                return result

            # ============================================================
            # CHECK 5: Maximum simultaneous trades
            # ============================================================
            if open_trade_count >= self.max_simultaneous_trades:
                result.add_rejection(
                    RejectionReason.MAX_TRADES_REACHED,
                    f"Maximum simultaneous trades reached: {open_trade_count}/{self.max_simultaneous_trades}"
                )

            # ============================================================
            # CHECK 6: Position sizing
            # ============================================================
            risk_percent = signal.risk_percent or self.default_risk_per_trade_percent
            
            try:
                quantity = PositionSizer.fixed_fractional(
                    account_balance=account_balance,
                    risk_percent=risk_percent,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    leverage=signal.leverage
                )
                
                risk_amount = account_balance * (risk_percent / 100)
                position_value = quantity * signal.entry_price
                
                result.approved_quantity = quantity
                result.risk_amount_usd = risk_amount
                result.risk_percent = risk_percent
                result.position_size_usd = position_value

                # Validate position size doesn't exceed max
                size_valid, size_msg = PositionSizer.validate_position_size(
                    quantity=quantity,
                    entry_price=signal.entry_price,
                    account_balance=account_balance,
                    max_position_percent=self.max_position_size_percent
                )
                if not size_valid:
                    result.add_rejection(RejectionReason.POSITION_TOO_LARGE, size_msg)

                # Check risk amount
                if risk_amount > account_balance * 0.05:  # Hard cap at 5% per trade
                    result.add_rejection(
                        RejectionReason.RISK_AMOUNT_TOO_HIGH,
                        f"Risk amount ${risk_amount:.2f} exceeds hard cap of 5% of balance"
                    )

            except ValueError as e:
                result.add_rejection(RejectionReason.INVALID_STOP_LOSS, str(e))

            # ============================================================
            # CHECK 7: Risk/Reward ratio (if take profit provided)
            # ============================================================
            if signal.take_profit_1:
                rr_ratio = PositionSizer.calculate_risk_reward(
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit_1,
                    direction=signal.direction
                )
                result.risk_reward_ratio = rr_ratio
                result.approved_take_profit_1 = signal.take_profit_1
                result.approved_take_profit_2 = signal.take_profit_2
                result.approved_take_profit_3 = signal.take_profit_3

                if rr_ratio < self.min_risk_reward_ratio:
                    result.add_rejection(
                        RejectionReason.POOR_RISK_REWARD,
                        f"Risk/Reward ratio {rr_ratio:.2f} below minimum {self.min_risk_reward_ratio:.2f}"
                    )

            # ============================================================
            # CHECK 8: Minimum balance check
            # ============================================================
            if account_balance < 100:  # Minimum $100 to trade
                result.add_rejection(
                    RejectionReason.INSUFFICIENT_BALANCE,
                    f"Insufficient balance: ${account_balance:.2f}. Minimum required: $100"
                )

            # ============================================================
            # Final determination
            # ============================================================
            if result.rejection_reasons:
                if result.status != RiskStatus.TRADING_HALTED:
                    result.status = RiskStatus.REJECTED
                trade_logger.log_trade_rejected(
                    ", ".join(r.value for r in result.rejection_reasons),
                    {
                        "symbol": signal.symbol,
                        "user_id": user_id,
                        "reasons": result.rejection_messages
                    }
                )
            else:
                result.status = RiskStatus.APPROVED
                result.approved_stop_loss = signal.stop_loss
                logger.info(
                    f"Trade approved: {signal.symbol} {signal.direction} "
                    f"qty={result.approved_quantity:.6f} risk={result.risk_percent:.2f}%"
                )

            return result

    def _validate_stop_loss(self, signal: TradeSignal) -> tuple[bool, str]:
        """Validate stop loss is on the correct side of entry."""
        if signal.direction == "long":
            if signal.stop_loss >= signal.entry_price:
                return False, (
                    f"Long trade stop loss ({signal.stop_loss}) must be below entry ({signal.entry_price})"
                )
        else:  # short
            if signal.stop_loss <= signal.entry_price:
                return False, (
                    f"Short trade stop loss ({signal.stop_loss}) must be above entry ({signal.entry_price})"
                )
        return True, "Stop loss is valid"

    async def register_trade_opened(self, user_id: str, trade_id: str):
        """Register that a trade has been opened."""
        async with self._lock:
            if user_id not in self._open_trades:
                self._open_trades[user_id] = []
            self._open_trades[user_id].append(trade_id)

    async def register_trade_closed(self, user_id: str, trade_id: str, pnl: float, new_balance: float):
        """Register that a trade has been closed and update drawdown guard."""
        async with self._lock:
            if user_id in self._open_trades:
                self._open_trades[user_id] = [t for t in self._open_trades[user_id] if t != trade_id]
        
        await self.drawdown_guard.update_balance(user_id, new_balance, pnl)

    def get_open_trade_count(self, user_id: str) -> int:
        return len(self._open_trades.get(user_id, []))

    def get_risk_summary(self, user_id: str) -> dict:
        return {
            "open_trades": self.get_open_trade_count(user_id),
            "max_simultaneous_trades": self.max_simultaneous_trades,
            "daily_drawdown": self.drawdown_guard.get_daily_drawdown(user_id),
            "max_daily_drawdown": self.max_daily_drawdown_percent,
            "trading_halted": self.drawdown_guard.is_trading_halted(user_id),
            "halt_reason": self.drawdown_guard.get_halt_reason(user_id),
        }


# Global singleton
_risk_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine()
    return _risk_engine
