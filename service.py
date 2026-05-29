"""
Notification Service
Supports Telegram, Email, and in-app notifications.
"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
import httpx
from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram Bot."""

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=10.0)

    async def send(self, message: str, parse_mode: str = "HTML") -> bool:
        try:
            url = self.BASE_URL.format(token=self.token)
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }
            response = await self._client.post(url, json=payload)
            if response.status_code == 200:
                logger.info("Telegram notification sent")
                return True
            else:
                logger.error(f"Telegram error: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def send_trade_opened(self, trade: Dict) -> bool:
        emoji = "🟢" if trade.get("direction") == "long" else "🔴"
        msg = (
            f"{emoji} <b>Trade Opened</b>\n"
            f"Symbol: <code>{trade.get('symbol')}</code>\n"
            f"Direction: {trade.get('direction', '').upper()}\n"
            f"Entry: <code>${trade.get('entry_price', 0):,.4f}</code>\n"
            f"Stop Loss: <code>${trade.get('stop_loss', 0):,.4f}</code>\n"
            f"TP1: <code>${trade.get('take_profit_1', 'N/A')}</code>\n"
            f"Risk: {trade.get('risk_percent', 0):.1f}%\n"
            f"Mode: {trade.get('mode', 'paper').upper()}"
        )
        return await self.send(msg)

    async def send_trade_closed(self, trade: Dict) -> bool:
        pnl = trade.get("pnl", 0)
        emoji = "✅" if pnl > 0 else "❌"
        msg = (
            f"{emoji} <b>Trade Closed</b>\n"
            f"Symbol: <code>{trade.get('symbol')}</code>\n"
            f"PnL: <code>${pnl:+,.2f}</code> ({trade.get('pnl_percent', 0):+.2f}%)\n"
            f"Exit Reason: {trade.get('exit_reason', '')}\n"
            f"Balance: <code>${trade.get('balance', 0):,.2f}</code>"
        )
        return await self.send(msg)

    async def send_risk_warning(self, message: str, context: Dict) -> bool:
        msg = (
            f"⚠️ <b>RISK WARNING</b>\n"
            f"{message}\n"
            f"Daily Drawdown: {context.get('daily_drawdown', 0):.2f}%"
        )
        return await self.send(msg)

    async def send_daily_report(self, report: Dict) -> bool:
        pnl = report.get("daily_pnl", 0)
        emoji = "📈" if pnl >= 0 else "📉"
        msg = (
            f"{emoji} <b>Daily Report</b>\n"
            f"Date: {report.get('date')}\n"
            f"────────────────\n"
            f"PnL: <code>${pnl:+,.2f}</code> ({report.get('daily_pnl_percent', 0):+.2f}%)\n"
            f"Trades: {report.get('total_trades', 0)} "
            f"(W: {report.get('wins', 0)} / L: {report.get('losses', 0)})\n"
            f"Win Rate: {report.get('win_rate', 0):.1f}%\n"
            f"Balance: <code>${report.get('balance', 0):,.2f}</code>"
        )
        return await self.send(msg)

    async def close(self):
        await self._client.aclose()


class EmailNotifier:
    """Send notifications via SMTP email."""

    def __init__(self):
        self.host = settings.notifications.SMTP_HOST
        self.port = settings.notifications.SMTP_PORT
        self.user = settings.notifications.SMTP_USER
        self.password = settings.notifications.SMTP_PASSWORD
        self.to_email = settings.notifications.NOTIFICATION_EMAIL

    async def send(self, subject: str, body_html: str) -> bool:
        if not self.user or not self.to_email:
            return False
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._send_sync, subject, body_html)
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    def _send_sync(self, subject: str, body_html: str) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.user
        msg["To"] = self.to_email
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            server.login(self.user, self.password)
            server.sendmail(self.user, self.to_email, msg.as_string())
        return True


class NotificationService:
    """
    Unified notification service.
    Dispatches to all configured channels.
    """

    def __init__(self):
        self._telegram: Optional[TelegramNotifier] = None
        self._email = EmailNotifier()

        if settings.notifications.TELEGRAM_BOT_TOKEN and settings.notifications.TELEGRAM_CHAT_ID:
            self._telegram = TelegramNotifier(
                settings.notifications.TELEGRAM_BOT_TOKEN,
                settings.notifications.TELEGRAM_CHAT_ID
            )

    async def notify_trade_opened(self, trade: Dict):
        tasks = []
        if self._telegram:
            tasks.append(self._telegram.send_trade_opened(trade))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def notify_trade_closed(self, trade: Dict):
        tasks = []
        if self._telegram:
            tasks.append(self._telegram.send_trade_closed(trade))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def notify_risk_warning(self, message: str, context: Dict):
        tasks = []
        if self._telegram:
            tasks.append(self._telegram.send_risk_warning(message, context))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def notify_daily_report(self, report: Dict):
        tasks = []
        if self._telegram:
            tasks.append(self._telegram.send_daily_report(report))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send_raw(self, message: str):
        if self._telegram:
            await self._telegram.send(message)


notification_service = NotificationService()
