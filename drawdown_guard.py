"""
Drawdown Guard - Monitors and enforces daily drawdown limits.
Auto-halts trading when risk thresholds are breached.
"""
import asyncio
from datetime import datetime, timezone, date
from typing import Optional, Dict
from .logger import get_logger, get_trade_logger

logger = get_logger(__name__)
trade_logger = get_trade_logger()


class DrawdownGuard:
    """
    Monitors real-time drawdown and enforces daily loss limits.
    This is a critical safety mechanism — when limits are hit,
    ALL trading is immediately halted regardless of strategy.
    """

    def __init__(
        self,
        max_daily_drawdown_percent: float = 5.0,
        warning_threshold_percent: float = 3.0,
        max_consecutive_losses: int = 5
    ):
        self.max_daily_drawdown_percent = max_daily_drawdown_percent
        self.warning_threshold_percent = warning_threshold_percent
        self.max_consecutive_losses = max_consecutive_losses

        self._daily_start_balance: Dict[str, float] = {}  # user_id -> balance
        self._current_balance: Dict[str, float] = {}
        self._trading_halted: Dict[str, bool] = {}
        self._halt_reasons: Dict[str, str] = {}
        self._consecutive_losses: Dict[str, int] = {}
        self._last_reset_date: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def initialize_day(self, user_id: str, opening_balance: float):
        """Initialize daily tracking at start of trading day."""
        async with self._lock:
            today = date.today().isoformat()
            if self._last_reset_date.get(user_id) != today:
                self._daily_start_balance[user_id] = opening_balance
                self._current_balance[user_id] = opening_balance
                self._trading_halted[user_id] = False
                self._halt_reasons[user_id] = ""
                self._consecutive_losses[user_id] = 0
                self._last_reset_date[user_id] = today
                logger.info(f"Drawdown guard initialized for user {user_id}, balance: {opening_balance}")

    async def update_balance(self, user_id: str, new_balance: float, trade_pnl: float = 0.0):
        """
        Update current balance and check drawdown limits.
        Returns True if trading should continue, False if halted.
        """
        async with self._lock:
            if self._trading_halted.get(user_id, False):
                return False

            self._current_balance[user_id] = new_balance

            # Track consecutive losses
            if trade_pnl < 0:
                self._consecutive_losses[user_id] = self._consecutive_losses.get(user_id, 0) + 1
            elif trade_pnl > 0:
                self._consecutive_losses[user_id] = 0

            # Calculate daily drawdown
            start_balance = self._daily_start_balance.get(user_id, new_balance)
            if start_balance > 0:
                daily_drawdown = ((start_balance - new_balance) / start_balance) * 100

                # Warning threshold
                if daily_drawdown >= self.warning_threshold_percent:
                    trade_logger.log_risk_warning(
                        f"Daily drawdown warning: {daily_drawdown:.2f}%",
                        {"user_id": user_id, "drawdown": daily_drawdown, "threshold": self.warning_threshold_percent}
                    )

                # Hard stop
                if daily_drawdown >= self.max_daily_drawdown_percent:
                    await self._halt_trading(
                        user_id,
                        f"Daily drawdown limit reached: {daily_drawdown:.2f}% >= {self.max_daily_drawdown_percent}%"
                    )
                    return False

            # Consecutive losses guard
            if self._consecutive_losses.get(user_id, 0) >= self.max_consecutive_losses:
                await self._halt_trading(
                    user_id,
                    f"Maximum consecutive losses reached: {self._consecutive_losses[user_id]}"
                )
                return False

            return True

    async def _halt_trading(self, user_id: str, reason: str):
        """Emergency trading halt."""
        self._trading_halted[user_id] = True
        self._halt_reasons[user_id] = reason
        trade_logger.log_risk_warning(
            f"TRADING HALTED: {reason}",
            {"user_id": user_id, "reason": reason}
        )

    async def resume_trading(self, user_id: str, authorized_by: str):
        """Resume trading after manual review (requires authorization)."""
        async with self._lock:
            self._trading_halted[user_id] = False
            self._halt_reasons[user_id] = ""
            logger.warning(f"Trading resumed for user {user_id} by {authorized_by}")

    def is_trading_halted(self, user_id: str) -> bool:
        return self._trading_halted.get(user_id, False)

    def get_halt_reason(self, user_id: str) -> str:
        return self._halt_reasons.get(user_id, "")

    def get_daily_drawdown(self, user_id: str) -> float:
        start = self._daily_start_balance.get(user_id, 0)
        current = self._current_balance.get(user_id, 0)
        if start <= 0:
            return 0.0
        return ((start - current) / start) * 100

    def get_status(self, user_id: str) -> dict:
        return {
            "user_id": user_id,
            "trading_halted": self.is_trading_halted(user_id),
            "halt_reason": self.get_halt_reason(user_id),
            "daily_drawdown_percent": self.get_daily_drawdown(user_id),
            "max_daily_drawdown_percent": self.max_daily_drawdown_percent,
            "consecutive_losses": self._consecutive_losses.get(user_id, 0),
            "daily_start_balance": self._daily_start_balance.get(user_id, 0),
            "current_balance": self._current_balance.get(user_id, 0),
        }
