"""
NWH Crypto - Telegram Control Bot
Full control panel via Telegram commands.
Kill switch, strategy control, PnL, positions, risk management.
"""
import asyncio
import functools
from typing import Optional, Dict, Any
import httpx
from ..core.logging import get_logger
from ..core.config import settings

logger = get_logger(__name__)

BASE_URL = "https://api.telegram.org/bot{token}"


def admin_only(func):
    """Decorator: only allow commands from authorized chat ID."""
    @functools.wraps(func)
    async def wrapper(self, update: Dict, *args, **kwargs):
        chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
        if chat_id != settings.notifications.TELEGRAM_CHAT_ID:
            await self.send_message(chat_id, "⛔ Unauthorized access.")
            logger.warning(f"Unauthorized Telegram access from chat_id: {chat_id}")
            return
        return await func(self, update, *args, **kwargs)
    return wrapper


class NWHTelegramBot:
    """
    Full Telegram control panel for NWH Trading Bot.

    Commands:
    /start      - Welcome message
    /status     - Full system status
    /pnl        - Today's P&L
    /positions  - Open positions
    /risk       - Risk metrics
    /balance    - Account balance
    /drawdown   - Daily drawdown status
    /stopbot    - Stop all strategies
    /startbot   - Start all strategies
    /kill       - EMERGENCY: Close all trades + disable trading
    /setrisk X  - Set risk per trade to X%
    /closeall   - Close all open positions
    /close SYM  - Close position on symbol
    /mode paper - Switch to paper trading
    /mode live  - Switch to live trading
    /report     - Daily performance report
    /help       - Show all commands
    """

    COMMANDS = {
        "/start": "start",
        "/status": "status",
        "/pnl": "pnl",
        "/positions": "positions",
        "/risk": "risk",
        "/balance": "balance",
        "/drawdown": "drawdown",
        "/stopbot": "stopbot",
        "/startbot": "startbot",
        "/kill": "kill",
        "/setrisk": "setrisk",
        "/closeall": "closeall",
        "/close": "close",
        "/mode": "mode",
        "/report": "report",
        "/help": "help",
    }

    def __init__(self, token: str, chat_id: str, api_base: str = "http://localhost:8000"):
        self.token = token
        self.chat_id = chat_id
        self.api_base = api_base
        self._client = httpx.AsyncClient(timeout=15.0)
        self._polling = False
        self._last_update_id = 0

    # ============================================================
    # Core Messaging
    # ============================================================

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        try:
            url = f"{BASE_URL.format(token=self.token)}/sendMessage"
            resp = await self._client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            })
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def send_photo(self, chat_id: str, photo_url: str, caption: str = "") -> bool:
        try:
            url = f"{BASE_URL.format(token=self.token)}/sendPhoto"
            resp = await self._client.post(url, json={
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": "HTML",
            })
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram photo send error: {e}")
            return False

    # ============================================================
    # Polling
    # ============================================================

    async def start_polling(self):
        """Start long-polling for incoming messages."""
        self._polling = True
        logger.info("Telegram bot polling started")
        await self.send_message(self.chat_id, "🤖 <b>NWH Bot is online</b>\nType /help for commands.")

        while self._polling:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._process_update(update)
            except Exception as e:
                logger.error(f"Polling error: {e}")
            await asyncio.sleep(1)

    async def stop_polling(self):
        self._polling = False

    async def _get_updates(self) -> list:
        url = f"{BASE_URL.format(token=self.token)}/getUpdates"
        params = {"offset": self._last_update_id + 1, "timeout": 30, "limit": 10}
        try:
            resp = await self._client.get(url, params=params, timeout=35.0)
            data = resp.json()
            if data.get("ok") and data.get("result"):
                updates = data["result"]
                self._last_update_id = updates[-1]["update_id"]
                return updates
        except Exception:
            pass
        return []

    async def _process_update(self, update: Dict):
        """Route incoming update to correct handler."""
        message = update.get("message", {})
        text = message.get("text", "").strip()
        if not text:
            return

        parts = text.split()
        command = parts[0].lower().split("@")[0]  # Remove bot username if present
        args = parts[1:] if len(parts) > 1 else []

        handler_name = self.COMMANDS.get(command)
        if handler_name:
            handler = getattr(self, f"cmd_{handler_name}", None)
            if handler:
                await handler(update, args)
        else:
            chat_id = str(message.get("chat", {}).get("id", ""))
            await self.send_message(chat_id, "❓ Unknown command. Type /help")

    # ============================================================
    # API Helper
    # ============================================================

    async def _api_get(self, endpoint: str) -> Optional[Dict]:
        try:
            resp = await self._client.get(f"{self.api_base}/api/v1{endpoint}")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"API call failed: {e}")
        return None

    async def _api_post(self, endpoint: str, data: Dict = None) -> Optional[Dict]:
        try:
            resp = await self._client.post(f"{self.api_base}/api/v1{endpoint}", json=data or {})
            if resp.status_code in [200, 201]:
                return resp.json()
        except Exception as e:
            logger.error(f"API call failed: {e}")
        return None

    # ============================================================
    # Command Handlers
    # ============================================================

    @admin_only
    async def cmd_start(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        msg = (
            "🤖 <b>NWH Crypto Trading Bot</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Your personal trading control panel.\n\n"
            "Type /help to see all commands."
        )
        await self.send_message(chat_id, msg)

    @admin_only
    async def cmd_help(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        msg = (
            "📋 <b>Available Commands</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>Monitoring</b>\n"
            "/status — Full system status\n"
            "/pnl — Today's P&amp;L\n"
            "/positions — Open positions\n"
            "/balance — Account balance\n"
            "/drawdown — Drawdown status\n"
            "/risk — Risk metrics\n"
            "/report — Daily report\n\n"
            "⚙️ <b>Control</b>\n"
            "/startbot — Start all strategies\n"
            "/stopbot — Stop all strategies\n"
            "/closeall — Close all positions\n"
            "/close BTC/USDT — Close specific symbol\n"
            "/setrisk 1.5 — Set risk % per trade\n"
            "/mode paper — Switch to paper mode\n"
            "/mode live — Switch to live mode\n\n"
            "🚨 <b>Emergency</b>\n"
            "/kill — EMERGENCY STOP EVERYTHING"
        )
        await self.send_message(chat_id, msg)

    @admin_only
    async def cmd_status(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        data = await self._api_get("/dashboard/status")
        if not data:
            await self.send_message(chat_id, "❌ Could not reach API.")
            return

        risk = data.get("risk", {})
        trading = data.get("trading", {})
        system = data.get("system", {})

        halted = risk.get("trading_halted", False)
        status_icon = "🔴 HALTED" if halted else "🟢 Active"

        msg = (
            f"📡 <b>System Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Status: {status_icon}\n"
            f"Mode: {trading.get('mode', 'paper').upper()}\n"
            f"Exchange: {trading.get('exchange', 'binance').upper()}\n\n"
            f"💰 <b>Account</b>\n"
            f"Balance: <code>${data.get('balance', 0):,.2f}</code>\n"
            f"Daily PnL: <code>${data.get('daily_pnl', 0):+,.2f}</code> "
            f"({data.get('daily_pnl_percent', 0):+.2f}%)\n\n"
            f"⚠️ <b>Risk</b>\n"
            f"Drawdown: {risk.get('daily_drawdown_percent', 0):.2f}%\n"
            f"Open Trades: {risk.get('open_trades', 0)}/{risk.get('max_trades', 5)}\n"
            f"Active Strategies: {trading.get('active_strategies', 0)}\n\n"
            f"🖥 <b>Server</b>\n"
            f"CPU: {system.get('cpu_percent', 0):.1f}%\n"
            f"RAM: {system.get('ram_percent', 0):.1f}%\n"
            f"Uptime: {system.get('uptime', 'N/A')}"
        )
        await self.send_message(chat_id, msg)

    @admin_only
    async def cmd_pnl(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        data = await self._api_get("/dashboard/pnl")
        if not data:
            await self.send_message(chat_id, "❌ Could not fetch PnL.")
            return

        pnl = data.get("daily_pnl", 0)
        emoji = "📈" if pnl >= 0 else "📉"
        msg = (
            f"{emoji} <b>Today's P&amp;L</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"PnL: <code>${pnl:+,.2f}</code> ({data.get('daily_pnl_percent', 0):+.2f}%)\n"
            f"Trades: {data.get('total_trades', 0)} "
            f"(✅{data.get('wins', 0)} / ❌{data.get('losses', 0)})\n"
            f"Win Rate: {data.get('win_rate', 0):.1f}%\n"
            f"Best Trade: <code>${data.get('best_trade', 0):+,.2f}</code>\n"
            f"Worst Trade: <code>${data.get('worst_trade', 0):+,.2f}</code>\n"
            f"Fees Paid: <code>${data.get('total_fees', 0):.2f}</code>"
        )
        await self.send_message(chat_id, msg)

    @admin_only
    async def cmd_positions(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        data = await self._api_get("/trades/positions")
        if not data:
            await self.send_message(chat_id, "❌ Could not fetch positions.")
            return

        positions = data.get("positions", [])
        if not positions:
            await self.send_message(chat_id, "📭 No open positions.")
            return

        msg = f"📊 <b>Open Positions ({len(positions)})</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for p in positions:
            pnl = p.get("unrealized_pnl", 0)
            pnl_icon = "🟢" if pnl >= 0 else "🔴"
            direction = "⬆️ LONG" if p.get("direction") == "long" else "⬇️ SHORT"
            msg += (
                f"\n{pnl_icon} <b>{p.get('symbol')}</b> {direction}\n"
                f"Entry: <code>${p.get('entry_price', 0):,.4f}</code>\n"
                f"Current: <code>${p.get('current_price', 0):,.4f}</code>\n"
                f"PnL: <code>${pnl:+,.2f}</code> ({p.get('unrealized_pnl_percent', 0):+.2f}%)\n"
                f"SL: <code>${p.get('stop_loss', 0):,.4f}</code>\n"
                f"────────────\n"
            )
        await self.send_message(chat_id, msg)

    @admin_only
    async def cmd_risk(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        data = await self._api_get("/risk/status")
        if not data:
            await self.send_message(chat_id, "❌ Could not fetch risk status.")
            return

        msg = (
            f"🛡 <b>Risk Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Trading: {'🔴 HALTED' if data.get('trading_halted') else '🟢 Active'}\n"
            f"Daily Drawdown: {data.get('daily_drawdown_percent', 0):.2f}% / {data.get('max_daily_drawdown', 5)}%\n"
            f"Open Trades: {data.get('open_trades', 0)} / {data.get('max_simultaneous_trades', 5)}\n"
            f"Risk Per Trade: {data.get('risk_per_trade_percent', 1):.1f}%\n"
            f"Consecutive Losses: {data.get('consecutive_losses', 0)}\n"
            f"Daily Start Balance: <code>${data.get('daily_start_balance', 0):,.2f}</code>\n"
            f"Current Balance: <code>${data.get('current_balance', 0):,.2f}</code>"
        )
        if data.get("halt_reason"):
            msg += f"\n\n⚠️ Halt Reason: {data.get('halt_reason')}"
        await self.send_message(chat_id, msg)

    @admin_only
    async def cmd_balance(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        data = await self._api_get("/exchanges/balance")
        if not data:
            await self.send_message(chat_id, "❌ Could not fetch balance.")
            return

        msg = "💰 <b>Account Balance</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for currency, info in data.get("balances", {}).items():
            if info.get("total", 0) > 0:
                msg += f"{currency}: <code>{info.get('total', 0):.4f}</code> (Free: {info.get('free', 0):.4f})\n"
        await self.send_message(chat_id, msg)

    @admin_only
    async def cmd_drawdown(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        data = await self._api_get("/risk/drawdown")
        if not data:
            await self.send_message(chat_id, "❌ Could not fetch drawdown data.")
            return

        dd = data.get("daily_drawdown_percent", 0)
        max_dd = data.get("max_daily_drawdown", 5.0)
        used_pct = (dd / max_dd * 100) if max_dd > 0 else 0
        bar = "█" * int(used_pct / 10) + "░" * (10 - int(used_pct / 10))

        msg = (
            f"📉 <b>Drawdown Monitor</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"[{bar}] {used_pct:.0f}%\n"
            f"Current: {dd:.2f}% / {max_dd:.1f}%\n"
            f"Status: {'🔴 LIMIT REACHED' if dd >= max_dd else '🟢 Safe'}\n"
            f"Start Balance: <code>${data.get('start_balance', 0):,.2f}</code>\n"
            f"Current Balance: <code>${data.get('current_balance', 0):,.2f}</code>\n"
            f"Loss Today: <code>${data.get('loss_today', 0):,.2f}</code>"
        )
        await self.send_message(chat_id, msg)

    @admin_only
    async def cmd_stopbot(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        result = await self._api_post("/strategies/stop-all")
        if result:
            await self.send_message(chat_id, "⏸ <b>All strategies stopped.</b>\nOpen positions remain open until manual close.")
        else:
            await self.send_message(chat_id, "❌ Failed to stop strategies.")

    @admin_only
    async def cmd_startbot(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        result = await self._api_post("/strategies/start-all")
        if result:
            await self.send_message(chat_id, "▶️ <b>All strategies started.</b>")
        else:
            await self.send_message(chat_id, "❌ Failed to start strategies.")

    @admin_only
    async def cmd_kill(self, update: Dict, args: list):
        """EMERGENCY KILL SWITCH — closes everything immediately."""
        chat_id = str(update["message"]["chat"]["id"])
        await self.send_message(chat_id, "🚨 <b>KILL SWITCH ACTIVATED</b>\nClosing all positions and halting trading...")

        result = await self._api_post("/risk/kill-switch")
        if result:
            closed = result.get("positions_closed", 0)
            await self.send_message(
                chat_id,
                f"✅ <b>Kill Switch Complete</b>\n"
                f"Positions Closed: {closed}\n"
                f"Strategies Stopped: ✅\n"
                f"Trading Halted: ✅\n\n"
                f"Use /startbot to resume after reviewing."
            )
        else:
            await self.send_message(chat_id, "❌ Kill switch API failed. Check server manually!")

    @admin_only
    async def cmd_setrisk(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        if not args:
            await self.send_message(chat_id, "Usage: /setrisk 1.5")
            return
        try:
            risk_pct = float(args[0])
            if risk_pct <= 0 or risk_pct > 5:
                await self.send_message(chat_id, "⚠️ Risk must be between 0.1% and 5%")
                return
            result = await self._api_post("/risk/set-risk-percent", {"risk_percent": risk_pct})
            if result:
                await self.send_message(chat_id, f"✅ Risk per trade set to <b>{risk_pct}%</b>")
            else:
                await self.send_message(chat_id, "❌ Failed to update risk.")
        except ValueError:
            await self.send_message(chat_id, "❌ Invalid value. Example: /setrisk 1.5")

    @admin_only
    async def cmd_closeall(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        result = await self._api_post("/trades/close-all")
        if result:
            closed = result.get("closed_count", 0)
            pnl = result.get("total_pnl", 0)
            await self.send_message(
                chat_id,
                f"✅ <b>All positions closed</b>\n"
                f"Closed: {closed} positions\n"
                f"Total PnL: <code>${pnl:+,.2f}</code>"
            )
        else:
            await self.send_message(chat_id, "❌ Failed to close positions.")

    @admin_only
    async def cmd_close(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        if not args:
            await self.send_message(chat_id, "Usage: /close BTC/USDT")
            return
        symbol = args[0].upper()
        result = await self._api_post(f"/trades/close-symbol", {"symbol": symbol})
        if result:
            pnl = result.get("pnl", 0)
            await self.send_message(
                chat_id,
                f"✅ <b>{symbol} closed</b>\nPnL: <code>${pnl:+,.2f}</code>"
            )
        else:
            await self.send_message(chat_id, f"❌ No open position for {symbol}")

    @admin_only
    async def cmd_mode(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        if not args or args[0].lower() not in ["paper", "live"]:
            await self.send_message(chat_id, "Usage: /mode paper OR /mode live")
            return
        mode = args[0].lower()
        if mode == "live":
            await self.send_message(
                chat_id,
                "⚠️ <b>WARNING: Switching to LIVE mode</b>\n"
                "Real money will be used.\n"
                "Reply /confirmLIVE to proceed."
            )
            return
        result = await self._api_post("/trading/set-mode", {"mode": mode})
        if result:
            await self.send_message(chat_id, f"✅ Switched to <b>{mode.upper()}</b> mode")
        else:
            await self.send_message(chat_id, "❌ Failed to switch mode.")

    @admin_only
    async def cmd_report(self, update: Dict, args: list):
        chat_id = str(update["message"]["chat"]["id"])
        data = await self._api_get("/dashboard/daily-report")
        if not data:
            await self.send_message(chat_id, "❌ Could not generate report.")
            return

        pnl = data.get("daily_pnl", 0)
        emoji = "📈" if pnl >= 0 else "📉"
        msg = (
            f"{emoji} <b>Daily Report — {data.get('date', 'Today')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"PnL: <code>${pnl:+,.2f}</code> ({data.get('daily_pnl_percent', 0):+.2f}%)\n"
            f"Balance: <code>${data.get('balance', 0):,.2f}</code>\n"
            f"Total Trades: {data.get('total_trades', 0)}\n"
            f"Win Rate: {data.get('win_rate', 0):.1f}%\n"
            f"Profit Factor: {data.get('profit_factor', 0):.2f}\n"
            f"Max Drawdown: {data.get('max_drawdown', 0):.2f}%\n"
            f"Fees: <code>${data.get('total_fees', 0):.2f}</code>\n"
            f"Best: <code>${data.get('best_trade', 0):+,.2f}</code> | "
            f"Worst: <code>${data.get('worst_trade', 0):+,.2f}</code>\n\n"
            f"🏆 Best Strategy: {data.get('best_strategy', 'N/A')}"
        )
        await self.send_message(chat_id, msg)

    async def close(self):
        await self._client.aclose()
