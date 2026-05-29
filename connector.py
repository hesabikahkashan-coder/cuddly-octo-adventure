"""
Bybit Exchange Connector
Supports Spot and Derivatives trading with WebSocket streaming.
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Callable
import ccxt.async_support as ccxt
import websockets
from ...core.logging import get_logger
from ..base_exchange import (
    BaseExchangeConnector, OrderRequest, OrderResult,
    Balance, Ticker, OHLCV, OrderSide, OrderType
)

logger = get_logger(__name__)


class BybitConnector(BaseExchangeConnector):
    """
    Bybit connector supporting Spot and Derivatives (Linear/Inverse).
    Uses CCXT for REST API and native WebSocket for streaming.
    """

    BYBIT_WS_PUBLIC = "wss://stream.bybit.com/v5/public"
    BYBIT_WS_PRIVATE = "wss://stream.bybit.com/v5/private"
    BYBIT_WS_TESTNET = "wss://stream-testnet.bybit.com/v5"

    TIMEFRAME_MAP = {
        "1m": "1", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "4h": "240", "1d": "D", "1w": "W"
    }

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        category: str = "linear"  # spot, linear, inverse
    ):
        super().__init__(api_key, api_secret, testnet)
        self.category = category
        self._exchange: Optional[ccxt.bybit] = None
        self._ws_public: Optional[Any] = None
        self._ws_private: Optional[Any] = None
        self._callbacks: Dict[str, Callable] = {}

    async def connect(self) -> bool:
        """Initialize CCXT Bybit connection."""
        try:
            exchange_config = {
                "apiKey": self.api_key,
                "secret": self.api_secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot" if self.category == "spot" else "future",
                    "adjustForTimeDifference": True,
                },
            }

            if self.testnet:
                exchange_config["options"]["testnet"] = True

            self._exchange = ccxt.bybit(exchange_config)
            await self._exchange.load_markets()
            await self._exchange.fetch_balance()

            self._connected = True
            logger.info(f"Bybit [{self.category}] connector connected")
            return True

        except ccxt.AuthenticationError as e:
            logger.error(f"Bybit authentication failed: {e}")
            self._connected = False
            raise
        except Exception as e:
            logger.error(f"Bybit connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        if self._exchange:
            await self._exchange.close()
        self._connected = False
        logger.info("Bybit connector disconnected")

    async def connect_websocket(self, symbols: List[str], callbacks: Dict[str, Any]):
        """Connect to Bybit V5 WebSocket streams."""
        self._callbacks = callbacks

        base_url = self.BYBIT_WS_TESTNET if self.testnet else f"{self.BYBIT_WS_PUBLIC}/{self.category}"

        subscribe_topics = []
        for symbol in symbols:
            ws_symbol = symbol.replace("/", "")
            subscribe_topics.extend([
                f"tickers.{ws_symbol}",
                f"kline.1.{ws_symbol}",
                f"orderbook.50.{ws_symbol}",
            ])

        asyncio.create_task(self._websocket_public_handler(base_url, subscribe_topics))
        logger.info(f"Bybit WebSocket connecting for {len(symbols)} symbols")

    async def _websocket_public_handler(self, url: str, topics: List[str]):
        """Public WebSocket handler with auto-reconnect."""
        while True:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    self._ws_connected = True

                    # Subscribe to topics
                    subscribe_msg = {
                        "req_id": "nwh_sub",
                        "op": "subscribe",
                        "args": topics
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info("Bybit WebSocket subscribed to topics")

                    # Heartbeat task
                    async def heartbeat():
                        while True:
                            await asyncio.sleep(20)
                            await ws.send(json.dumps({"op": "ping"}))

                    hb_task = asyncio.create_task(heartbeat())

                    async for message in ws:
                        data = json.loads(message)
                        if data.get("op") == "pong":
                            continue
                        await self._process_ws_message(data)

                    hb_task.cancel()

            except websockets.ConnectionClosed as e:
                self._ws_connected = False
                logger.warning(f"Bybit WebSocket closed: {e}. Reconnecting...")
                await asyncio.sleep(self._reconnect_delay)
            except Exception as e:
                self._ws_connected = False
                logger.error(f"Bybit WebSocket error: {e}. Reconnecting...")
                await asyncio.sleep(self._reconnect_delay)

    async def _process_ws_message(self, message: Dict):
        """Process Bybit V5 WebSocket messages."""
        try:
            topic = message.get("topic", "")

            if topic.startswith("tickers."):
                if "on_ticker" in self._callbacks:
                    ticker_data = message.get("data", {})
                    ticker = Ticker(
                        symbol=ticker_data.get("symbol", ""),
                        bid=float(ticker_data.get("bid1Price", 0) or 0),
                        ask=float(ticker_data.get("ask1Price", 0) or 0),
                        last=float(ticker_data.get("lastPrice", 0) or 0),
                        volume=float(ticker_data.get("volume24h", 0) or 0),
                        timestamp=message.get("ts", 0)
                    )
                    await self._callbacks["on_ticker"](ticker)

            elif topic.startswith("kline."):
                if "on_kline" in self._callbacks:
                    kline_list = message.get("data", [])
                    for kline in kline_list:
                        await self._callbacks["on_kline"]({
                            "symbol": message.get("topic", "").split(".")[-1],
                            "open": float(kline.get("open", 0)),
                            "high": float(kline.get("high", 0)),
                            "low": float(kline.get("low", 0)),
                            "close": float(kline.get("close", 0)),
                            "volume": float(kline.get("volume", 0)),
                            "is_closed": kline.get("confirm", False),
                            "timestamp": kline.get("start", 0)
                        })

        except Exception as e:
            logger.error(f"Error processing Bybit WebSocket message: {e}")

    # ============================================================
    # Market Data
    # ============================================================

    async def get_ticker(self, symbol: str) -> Ticker:
        await self._ensure_connected()
        ticker = await self._exchange.fetch_ticker(symbol)
        return Ticker(
            symbol=symbol,
            bid=ticker["bid"],
            ask=ticker["ask"],
            last=ticker["last"],
            volume=ticker["baseVolume"],
            timestamp=ticker["timestamp"]
        )

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict:
        await self._ensure_connected()
        return await self._exchange.fetch_order_book(symbol, depth)

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[OHLCV]:
        await self._ensure_connected()
        tf = self.TIMEFRAME_MAP.get(timeframe, "60")
        raw = await self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return [OHLCV(
            timestamp=candle[0],
            open=candle[1],
            high=candle[2],
            low=candle[3],
            close=candle[4],
            volume=candle[5]
        ) for candle in raw]

    async def get_balance(self) -> Dict[str, Balance]:
        await self._ensure_connected()
        raw = await self._exchange.fetch_balance()
        balances = {}
        for currency, data in raw["total"].items():
            if data > 0:
                balances[currency] = Balance(
                    currency=currency,
                    free=raw["free"].get(currency, 0),
                    used=raw["used"].get(currency, 0),
                    total=data
                )
        return balances

    async def get_positions(self) -> List[Dict]:
        await self._ensure_connected()
        if self.category == "spot":
            return []
        positions = await self._exchange.fetch_positions()
        return [p for p in positions if float(p.get("contracts", 0) or 0) > 0]

    # ============================================================
    # Order Management
    # ============================================================

    async def place_order(self, order: OrderRequest) -> OrderResult:
        is_safe, message = self.validate_order_safety(order)
        if not is_safe:
            raise ValueError(f"Order safety check failed: {message}")

        await self._ensure_connected()

        params = {}
        if order.stop_price:
            params["triggerPrice"] = order.stop_price
        if order.reduce_only and self.category != "spot":
            params["reduceOnly"] = True
        if order.client_order_id:
            params["orderLinkId"] = order.client_order_id

        try:
            result = await self._exchange.create_order(
                symbol=order.symbol,
                type=order.order_type.value,
                side=order.side.value,
                amount=order.quantity,
                price=order.price,
                params=params
            )

            return OrderResult(
                exchange_order_id=str(result["id"]),
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                status=result["status"],
                price=result.get("price"),
                quantity=result["amount"],
                filled_quantity=result.get("filled", 0),
                average_fill_price=result.get("average"),
                fee=result.get("fee", {}).get("cost", 0) if result.get("fee") else 0,
                fee_currency=result.get("fee", {}).get("currency", "USDT") if result.get("fee") else "USDT",
                created_at=str(result.get("datetime", "")),
                raw_response=result
            )

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds on Bybit: {e}")
            raise
        except ccxt.RateLimitExceeded:
            await self.handle_rate_limit()
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        await self._ensure_connected()
        try:
            await self._exchange.cancel_order(order_id, symbol)
            return True
        except ccxt.OrderNotFound:
            return False

    async def get_order(self, order_id: str, symbol: str) -> Dict:
        await self._ensure_connected()
        return await self._exchange.fetch_order(order_id, symbol)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        await self._ensure_connected()
        return await self._exchange.fetch_open_orders(symbol)

    async def handle_rate_limit(self, retry_after: int = None):
        wait_time = retry_after or 30
        logger.warning(f"Bybit rate limit hit. Waiting {wait_time}s...")
        await asyncio.sleep(wait_time)

    async def _ensure_connected(self):
        if not self._connected:
            await self.reconnect_with_backoff()
        if not self._connected:
            raise ConnectionError("Failed to connect to Bybit")
