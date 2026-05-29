"""
Economic News Filter
Automatically pauses trading before high-impact news events:
FOMC, CPI, NFP, GDP, PPI, and other market-moving events.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import httpx
from ..core.logging import get_logger

logger = get_logger(__name__)


HIGH_IMPACT_EVENTS = [
    "FOMC", "Federal Reserve", "Fed Rate", "Interest Rate Decision",
    "CPI", "Consumer Price Index", "Inflation",
    "NFP", "Non-Farm Payroll", "Employment",
    "GDP", "Gross Domestic Product",
    "PPI", "Producer Price Index",
    "ECB", "Bank of England", "Bank of Japan",
    "Unemployment", "Retail Sales",
]

CRYPTO_SPECIFIC_EVENTS = [
    "SEC", "Bitcoin ETF", "Crypto Regulation",
    "Halving", "Exchange Hack", "Stablecoin",
]


class NewsEvent:
    def __init__(self, title: str, time: datetime, impact: str, currency: str):
        self.title = title
        self.time = time
        self.impact = impact  # high / medium / low
        self.currency = currency
        self.is_high_impact = any(kw.lower() in title.lower() for kw in HIGH_IMPACT_EVENTS)

    def __repr__(self):
        return f"<NewsEvent {self.title} @ {self.time} impact={self.impact}>"


class EconomicNewsFilter:
    """
    Monitors economic calendar and blocks trading around
    high-impact news events.

    Pause window: configurable minutes before and after event.
    """

    def __init__(
        self,
        pause_before_minutes: int = 30,
        pause_after_minutes: int = 30,
        impact_level: str = "high",  # high / medium
        calendar_api_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    ):
        self.pause_before = pause_before_minutes
        self.pause_after = pause_after_minutes
        self.impact_level = impact_level
        self.calendar_api_url = calendar_api_url

        self._upcoming_events: List[NewsEvent] = []
        self._last_fetch: Optional[datetime] = None
        self._fetch_interval_hours = 6
        self._client = httpx.AsyncClient(timeout=10.0)
        self._lock = asyncio.Lock()

    async def is_safe_to_trade(self, symbol: str = None) -> tuple[bool, str]:
        """
        Check if it's safe to trade right now.

        Returns:
            (is_safe, reason_if_not_safe)
        """
        await self._refresh_events_if_needed()

        now = datetime.now(timezone.utc)

        for event in self._upcoming_events:
            if not event.is_high_impact:
                continue

            pause_start = event.time - timedelta(minutes=self.pause_before)
            pause_end = event.time + timedelta(minutes=self.pause_after)

            if pause_start <= now <= pause_end:
                return False, (
                    f"High-impact news: '{event.title}' "
                    f"at {event.time.strftime('%H:%M UTC')} — "
                    f"Trading paused {self.pause_before}min before and {self.pause_after}min after."
                )

        # Check upcoming in next 30 minutes — warn but don't block
        for event in self._upcoming_events:
            if event.is_high_impact:
                time_until = (event.time - now).total_seconds() / 60
                if 0 < time_until <= self.pause_before:
                    return False, f"News approaching: '{event.title}' in {time_until:.0f} minutes"

        return True, "Clear to trade"

    async def get_upcoming_events(self, hours: int = 24) -> List[Dict]:
        """Get list of upcoming high-impact events."""
        await self._refresh_events_if_needed()
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)

        return [
            {
                "title": e.title,
                "time": e.time.isoformat(),
                "impact": e.impact,
                "currency": e.currency,
                "is_high_impact": e.is_high_impact,
                "minutes_until": round((e.time - now).total_seconds() / 60, 0),
            }
            for e in self._upcoming_events
            if now <= e.time <= cutoff
        ]

    async def _refresh_events_if_needed(self):
        """Fetch calendar data if cache is stale."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            if (
                self._last_fetch is None or
                (now - self._last_fetch).total_seconds() > self._fetch_interval_hours * 3600
            ):
                await self._fetch_calendar()
                self._last_fetch = now

    async def _fetch_calendar(self):
        """Fetch economic calendar from ForexFactory API."""
        try:
            resp = await self._client.get(self.calendar_api_url)
            if resp.status_code == 200:
                data = resp.json()
                events = []
                for item in data:
                    try:
                        impact = item.get("impact", "").lower()
                        if impact not in ["high", "medium"]:
                            continue

                        date_str = item.get("date", "")
                        time_str = item.get("time", "00:00am")

                        # Parse date + time
                        event_time = self._parse_ff_datetime(date_str, time_str)
                        if not event_time:
                            continue

                        # Only future events
                        if event_time < datetime.now(timezone.utc):
                            continue

                        events.append(NewsEvent(
                            title=item.get("title", "Unknown"),
                            time=event_time,
                            impact=impact,
                            currency=item.get("country", "USD"),
                        ))
                    except Exception:
                        continue

                self._upcoming_events = sorted(events, key=lambda e: e.time)
                logger.info(f"News filter: loaded {len(self._upcoming_events)} upcoming events")

        except Exception as e:
            logger.warning(f"Could not fetch economic calendar: {e}. Trading will continue.")

    def _parse_ff_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Parse ForexFactory date + time strings."""
        try:
            # Format: "01-06-2025" and "8:30am"
            from datetime import datetime as dt
            date_part = dt.strptime(date_str, "%m-%d-%Y").date()

            time_str = time_str.strip().lower().replace(" ", "")
            if time_str in ["", "all day", "tentative"]:
                return dt.combine(date_part, dt.min.time()).replace(tzinfo=timezone.utc)

            fmt = "%I:%M%p"
            time_part = dt.strptime(time_str, fmt).time()
            return dt.combine(date_part, time_part).replace(tzinfo=timezone.utc)
        except Exception:
            return None

    async def close(self):
        await self._client.aclose()


# Singleton
_news_filter: Optional[EconomicNewsFilter] = None

def get_news_filter() -> EconomicNewsFilter:
    global _news_filter
    if _news_filter is None:
        _news_filter = EconomicNewsFilter()
    return _news_filter
