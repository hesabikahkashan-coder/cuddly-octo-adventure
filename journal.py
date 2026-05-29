"""
Auto Trade Journal
Records every trade automatically with full context:
strategy, indicators, market regime, confidence, result, lessons.
"""
import json
import asyncio
from datetime import datetime, timezone, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from ..core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class JournalEntry:
    """One complete trade journal entry."""
    # Identity
    trade_id: str
    symbol: str
    direction: str           # long / short
    trading_mode: str        # live / paper

    # Entry context
    entry_price: float
    entry_time: str
    stop_loss: float
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    quantity: float
    risk_percent: float
    risk_amount_usd: float

    # Strategy context
    strategy_name: str
    timeframe: str
    confidence: float
    entry_reason: str
    market_regime: str

    # Indicator snapshot at entry
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None
    ema_trend: Optional[float] = None
    atr: Optional[float] = None
    volume_ratio: Optional[float] = None
    bb_position: Optional[str] = None
    ichimoku_cloud: Optional[str] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    candlestick_pattern: Optional[str] = None
    adx: Optional[float] = None

    # Exit data (filled when trade closes)
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    fees: Optional[float] = None
    trade_duration_hours: Optional[float] = None

    # Risk/Reward actual
    actual_rr: Optional[float] = None

    # Post-trade analysis (filled automatically)
    was_profitable: Optional[bool] = None
    hit_stop_loss: bool = False
    hit_take_profit: bool = False
    max_favorable_excursion: Optional[float] = None  # Best unrealized PnL
    max_adverse_excursion: Optional[float] = None    # Worst unrealized PnL

    # Notes
    pre_trade_notes: str = ""
    post_trade_notes: str = ""
    lessons_learned: str = ""

    # Screenshot
    chart_screenshot_url: Optional[str] = None
    exit_screenshot_url: Optional[str] = None

    tags: List[str] = field(default_factory=list)


class TradeJournal:
    """
    Auto Trade Journal — records all trades with full context.
    Stores in JSON files (one per day) + in-memory for fast access.
    """

    def __init__(self, journal_dir: str = "data/journal"):
        self.journal_dir = Path(journal_dir)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, JournalEntry] = {}  # trade_id -> entry
        self._lock = asyncio.Lock()
        logger.info(f"Trade Journal initialized at {self.journal_dir}")

    # ============================================================
    # Record Trade
    # ============================================================

    async def record_trade_opened(
        self,
        trade_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        quantity: float,
        risk_percent: float,
        risk_amount_usd: float,
        strategy_name: str,
        timeframe: str,
        confidence: float,
        entry_reason: str,
        market_regime: str,
        trading_mode: str = "paper",
        take_profit_1: Optional[float] = None,
        take_profit_2: Optional[float] = None,
        take_profit_3: Optional[float] = None,
        indicators: Optional[Dict] = None,
        chart_screenshot_url: Optional[str] = None,
    ) -> JournalEntry:
        """Record a new trade opening."""
        async with self._lock:
            ind = indicators or {}

            # Extract candlestick patterns
            patterns = ind.get("patterns", {})
            active_patterns = [k for k, v in patterns.items() if v] if patterns else []

            entry = JournalEntry(
                trade_id=trade_id,
                symbol=symbol,
                direction=direction,
                trading_mode=trading_mode,
                entry_price=entry_price,
                entry_time=datetime.now(timezone.utc).isoformat(),
                stop_loss=stop_loss,
                take_profit_1=take_profit_1,
                take_profit_2=take_profit_2,
                take_profit_3=take_profit_3,
                quantity=quantity,
                risk_percent=risk_percent,
                risk_amount_usd=risk_amount_usd,
                strategy_name=strategy_name,
                timeframe=timeframe,
                confidence=confidence,
                entry_reason=entry_reason,
                market_regime=market_regime,
                rsi=ind.get("rsi"),
                macd=ind.get("macd"),
                macd_signal=ind.get("macd_signal"),
                macd_histogram=ind.get("macd_histogram"),
                ema_fast=ind.get("ema_fast"),
                ema_slow=ind.get("ema_slow"),
                ema_trend=ind.get("ema_trend"),
                atr=ind.get("atr"),
                volume_ratio=ind.get("volume_ratio"),
                bb_position=ind.get("bb_position"),
                ichimoku_cloud=ind.get("ichimoku_cloud"),
                adx=ind.get("adx"),
                candlestick_pattern=", ".join(active_patterns) if active_patterns else None,
                chart_screenshot_url=chart_screenshot_url,
                tags=self._auto_tag(direction, market_regime, confidence, strategy_name),
            )

            self._entries[trade_id] = entry
            await self._save_to_file(entry)
            logger.info(f"Journal: Trade {trade_id} opened — {symbol} {direction}")
            return entry

    async def record_trade_closed(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
        pnl: float,
        pnl_percent: float,
        fees: float = 0.0,
        max_favorable_excursion: Optional[float] = None,
        max_adverse_excursion: Optional[float] = None,
        exit_screenshot_url: Optional[str] = None,
        post_trade_notes: str = "",
    ) -> Optional[JournalEntry]:
        """Update journal entry when trade closes."""
        async with self._lock:
            entry = self._entries.get(trade_id)
            if not entry:
                logger.warning(f"Journal: Trade {trade_id} not found for closing")
                return None

            entry.exit_price = exit_price
            entry.exit_time = datetime.now(timezone.utc).isoformat()
            entry.exit_reason = exit_reason
            entry.pnl = round(pnl, 4)
            entry.pnl_percent = round(pnl_percent, 3)
            entry.fees = round(fees, 4)
            entry.was_profitable = pnl > 0
            entry.hit_stop_loss = exit_reason == "stop_loss"
            entry.hit_take_profit = "take_profit" in exit_reason
            entry.max_favorable_excursion = max_favorable_excursion
            entry.max_adverse_excursion = max_adverse_excursion
            entry.exit_screenshot_url = exit_screenshot_url
            entry.post_trade_notes = post_trade_notes

            # Duration
            if entry.entry_time:
                entry_dt = datetime.fromisoformat(entry.entry_time)
                exit_dt = datetime.now(timezone.utc)
                entry.trade_duration_hours = round((exit_dt - entry_dt).total_seconds() / 3600, 2)

            # Actual R:R
            if entry.take_profit_1 and entry.stop_loss and entry.entry_price:
                risk = abs(entry.entry_price - entry.stop_loss)
                reward = abs(exit_price - entry.entry_price)
                entry.actual_rr = round(reward / risk, 2) if risk > 0 else None

            # Auto lessons
            entry.lessons_learned = self._auto_lessons(entry)

            await self._save_to_file(entry)
            logger.info(f"Journal: Trade {trade_id} closed — PnL: ${pnl:+,.2f}")
            return entry

    # ============================================================
    # Analytics
    # ============================================================

    def get_analytics(self, days: int = 30) -> Dict:
        """Comprehensive journal analytics."""
        entries = [e for e in self._entries.values() if e.exit_time is not None]

        if not entries:
            return {"message": "No completed trades in journal"}

        wins = [e for e in entries if e.was_profitable]
        losses = [e for e in entries if not e.was_profitable]

        # Strategy performance
        strategy_stats = {}
        for e in entries:
            s = e.strategy_name
            if s not in strategy_stats:
                strategy_stats[s] = {"trades": 0, "wins": 0, "pnl": 0}
            strategy_stats[s]["trades"] += 1
            strategy_stats[s]["pnl"] += e.pnl or 0
            if e.was_profitable:
                strategy_stats[s]["wins"] += 1

        for s in strategy_stats:
            t = strategy_stats[s]["trades"]
            strategy_stats[s]["win_rate"] = round(strategy_stats[s]["wins"] / t * 100, 1) if t > 0 else 0

        # Regime performance
        regime_stats = {}
        for e in entries:
            r = e.market_regime
            if r not in regime_stats:
                regime_stats[r] = {"trades": 0, "pnl": 0}
            regime_stats[r]["trades"] += 1
            regime_stats[r]["pnl"] += e.pnl or 0

        # SL analysis
        sl_hits = [e for e in entries if e.hit_stop_loss]
        tp_hits = [e for e in entries if e.hit_take_profit]

        # Best patterns
        pattern_wins = {}
        for e in wins:
            if e.candlestick_pattern:
                for p in e.candlestick_pattern.split(", "):
                    pattern_wins[p] = pattern_wins.get(p, 0) + 1

        return {
            "total_trades": len(entries),
            "win_rate": round(len(wins) / len(entries) * 100, 1) if entries else 0,
            "total_pnl": round(sum(e.pnl or 0 for e in entries), 2),
            "avg_win": round(sum(e.pnl or 0 for e in wins) / len(wins), 2) if wins else 0,
            "avg_loss": round(sum(e.pnl or 0 for e in losses) / len(losses), 2) if losses else 0,
            "avg_duration_hours": round(sum(e.trade_duration_hours or 0 for e in entries) / len(entries), 1),
            "avg_confidence": round(sum(e.confidence for e in entries) / len(entries), 2),
            "stop_loss_rate": round(len(sl_hits) / len(entries) * 100, 1),
            "take_profit_rate": round(len(tp_hits) / len(entries) * 100, 1),
            "strategy_performance": strategy_stats,
            "regime_performance": regime_stats,
            "best_patterns": pattern_wins,
        }

    def get_recent_entries(self, limit: int = 20) -> List[Dict]:
        """Get most recent journal entries."""
        entries = sorted(
            self._entries.values(),
            key=lambda e: e.entry_time,
            reverse=True
        )
        return [asdict(e) for e in entries[:limit]]

    # ============================================================
    # File I/O
    # ============================================================

    async def _save_to_file(self, entry: JournalEntry):
        """Save/update entry in daily JSON file."""
        today = date.today().isoformat()
        filepath = self.journal_dir / f"{today}.json"

        # Load existing
        existing = {}
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}

        existing[entry.trade_id] = asdict(entry)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    async def load_from_files(self):
        """Load all journal entries from disk on startup."""
        count = 0
        for filepath in sorted(self.journal_dir.glob("*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for trade_id, entry_data in data.items():
                    self._entries[trade_id] = JournalEntry(**entry_data)
                    count += 1
            except Exception as e:
                logger.error(f"Error loading journal file {filepath}: {e}")
        logger.info(f"Journal loaded {count} entries from disk")

    # ============================================================
    # Helpers
    # ============================================================

    def _auto_tag(self, direction: str, regime: str, confidence: float, strategy: str) -> List[str]:
        tags = [direction, regime, strategy]
        if confidence >= 0.8:
            tags.append("high_confidence")
        elif confidence < 0.6:
            tags.append("low_confidence")
        return tags

    def _auto_lessons(self, entry: JournalEntry) -> str:
        lessons = []

        if entry.hit_stop_loss:
            if entry.confidence and entry.confidence > 0.8:
                lessons.append("High confidence trade hit SL — review market regime.")
            if entry.market_regime == "high_volatility":
                lessons.append("SL hit during high volatility — avoid trading in this regime.")

        if entry.was_profitable and entry.exit_reason and "take_profit" in entry.exit_reason:
            lessons.append(f"TP hit successfully — {entry.strategy_name} working well in {entry.market_regime}.")

        if entry.trade_duration_hours and entry.trade_duration_hours < 0.5 and entry.hit_stop_loss:
            lessons.append("Very quick SL hit — entry timing may need review.")

        if entry.actual_rr and entry.actual_rr < 1.0 and entry.was_profitable:
            lessons.append("Profit taken below 1:1 RR — consider holding longer.")

        return " | ".join(lessons) if lessons else "No specific lessons noted."


# Singleton
_journal: Optional[TradeJournal] = None

def get_journal() -> TradeJournal:
    global _journal
    if _journal is None:
        _journal = TradeJournal()
    return _journal
