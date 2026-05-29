"""
Equity Protection Mode
Automatically reduces risk or stops trading when:
- Daily profit target is reached (lock in gains)
- Drawdown is accelerating (protect capital)
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict
from dataclasses import dataclass
from ..core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProtectionStatus:
    is_active: bool
    mode: str  # normal / reduced_risk / locked
    current_risk_multiplier: float  # 1.0 = normal, 0.5 = half risk
    reason: str
    daily_pnl_percent: float
    triggered_at: Optional[str] = None


class EquityProtectionMode:
    """
    Equity Protection — adjusts risk dynamically.

    Rules:
    1. Daily gain >= profit_lock_percent → reduce risk to 50%
    2. Daily gain >= max_daily_target → stop trading (lock gains)
    3. Drawdown accelerating (3 consecutive losses) → reduce risk
    4. Balance below minimum threshold → stop trading
    """

    def __init__(
        self,
        profit_lock_percent: float = 5.0,     # Reduce risk after +5% day
        max_daily_target_percent: float = 10.0, # Stop trading after +10% day
        min_balance_usd: float = 500.0,         # Emergency stop if balance drops below
        consecutive_loss_threshold: int = 3,    # Reduce risk after N losses
        reduced_risk_multiplier: float = 0.5,   # 50% of normal risk
    ):
        self.profit_lock_pct = profit_lock_percent
        self.max_daily_target_pct = max_daily_target_percent
        self.min_balance = min_balance_usd
        self.loss_threshold = consecutive_loss_threshold
        self.reduced_risk_mult = reduced_risk_multiplier

        self._daily_start_balance: Dict[str, float] = {}
        self._current_balance: Dict[str, float] = {}
        self._consecutive_losses: Dict[str, int] = {}
        self._protection_mode: Dict[str, str] = {}  # normal/reduced/locked
        self._lock = asyncio.Lock()

    async def initialize(self, user_id: str, balance: float):
        async with self._lock:
            self._daily_start_balance[user_id] = balance
            self._current_balance[user_id] = balance
            self._consecutive_losses[user_id] = 0
            self._protection_mode[user_id] = "normal"

    async def evaluate(self, user_id: str, current_balance: float, last_trade_pnl: float) -> ProtectionStatus:
        """
        Evaluate current state and return protection status.
        Call this after every trade closes.
        """
        async with self._lock:
            self._current_balance[user_id] = current_balance
            start = self._daily_start_balance.get(user_id, current_balance)

            daily_pnl_pct = ((current_balance - start) / start * 100) if start > 0 else 0

            # Track consecutive losses
            if last_trade_pnl < 0:
                self._consecutive_losses[user_id] = self._consecutive_losses.get(user_id, 0) + 1
            elif last_trade_pnl > 0:
                self._consecutive_losses[user_id] = 0

            consecutive_losses = self._consecutive_losses.get(user_id, 0)

            # ── LOCKED: Max daily target reached ──
            if daily_pnl_pct >= self.max_daily_target_pct:
                self._protection_mode[user_id] = "locked"
                return ProtectionStatus(
                    is_active=True,
                    mode="locked",
                    current_risk_multiplier=0.0,
                    reason=f"Daily target {self.max_daily_target_pct}% reached (+{daily_pnl_pct:.2f}%) — locking gains",
                    daily_pnl_percent=daily_pnl_pct,
                    triggered_at=datetime.now(timezone.utc).isoformat(),
                )

            # ── LOCKED: Balance too low ──
            if current_balance < self.min_balance:
                self._protection_mode[user_id] = "locked"
                return ProtectionStatus(
                    is_active=True,
                    mode="locked",
                    current_risk_multiplier=0.0,
                    reason=f"Balance ${current_balance:.2f} below minimum ${self.min_balance:.2f}",
                    daily_pnl_percent=daily_pnl_pct,
                    triggered_at=datetime.now(timezone.utc).isoformat(),
                )

            # ── REDUCED RISK: Profit lock ──
            if daily_pnl_pct >= self.profit_lock_pct:
                self._protection_mode[user_id] = "reduced_risk"
                return ProtectionStatus(
                    is_active=True,
                    mode="reduced_risk",
                    current_risk_multiplier=self.reduced_risk_mult,
                    reason=f"Profit lock at +{daily_pnl_pct:.2f}% — risk reduced to {self.reduced_risk_mult*100:.0f}%",
                    daily_pnl_percent=daily_pnl_pct,
                    triggered_at=datetime.now(timezone.utc).isoformat(),
                )

            # ── REDUCED RISK: Consecutive losses ──
            if consecutive_losses >= self.loss_threshold:
                self._protection_mode[user_id] = "reduced_risk"
                return ProtectionStatus(
                    is_active=True,
                    mode="reduced_risk",
                    current_risk_multiplier=self.reduced_risk_mult,
                    reason=f"{consecutive_losses} consecutive losses — risk reduced",
                    daily_pnl_percent=daily_pnl_pct,
                    triggered_at=datetime.now(timezone.utc).isoformat(),
                )

            # ── NORMAL ──
            self._protection_mode[user_id] = "normal"
            return ProtectionStatus(
                is_active=False,
                mode="normal",
                current_risk_multiplier=1.0,
                reason="Normal trading conditions",
                daily_pnl_percent=daily_pnl_pct,
            )

    def get_risk_multiplier(self, user_id: str) -> float:
        mode = self._protection_mode.get(user_id, "normal")
        if mode == "locked":
            return 0.0
        elif mode == "reduced_risk":
            return self.reduced_risk_mult
        return 1.0

    def is_locked(self, user_id: str) -> bool:
        return self._protection_mode.get(user_id) == "locked"
