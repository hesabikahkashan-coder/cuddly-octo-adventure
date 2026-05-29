"""
Base Exchange Connector - Abstract interface for all exchanges.
All exchange connectors MUST implement this interface.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from ..core.logging import get_logger

logger = get_logger(__name__)


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS_LIMIT = "stop_loss_limit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"
    reduce_only: bool = False
    client_order_id: Optional[str] = None


@dataclass
class OrderResult:
    exchange_order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    price: Optional[float]
    quantity: float
    filled_quantity: float
    average_fill_price: Optional[float]
    fee: float
    fee_currency: str
    created_at: str
    raw_response: Dict


@dataclass
class Balance:
    currency: str
    free: float
    used: float
    total: float


@dataclass
class Ticker:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: int


@dataclass
class OHLCV:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class BaseExchangeConnector(ABC):
    """
    Abstract base class for all exchange connectors.
    Enforces consistent interface and safety checks.
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self._connected = False
        self._ws_connected = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # seconds

    # ============================================================
    # Connection Management
    # ============================================================

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to exchange REST API."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from exchange."""
        pass

    @abstractmethod
    async def connect_websocket(self, symbols: List[str], callbacks: Dict[str, Any]):
        """Connect to WebSocket streams."""
        pass

    async def reconnect_with_backoff(self):
        """Reconnect with exponential backoff."""
        for attempt in range(self._max_reconnect_attempts):
            delay = self._reconnect_delay * (2 ** attempt)
            logger.warning(f"Reconnecting in {delay}s (attempt {attempt+1}/{self._max_reconnect_attempts})")
            await asyncio.sleep(delay)
            try:
                success = await self.connect()
                if success:
                    self._reconnect_attempts = 0
                    logger.info("Reconnected successfully")
                    return True
            except Exception as e:
                logger.error(f"Reconnect attempt {attempt+1} failed: {e}")
        
        logger.error("Max reconnection attempts exceeded")
        return False

    # ============================================================
    # Market Data
    # ============================================================

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict:
        pass

    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[OHLCV]:
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, Balance]:
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict]:
        """Get open positions (futures only)."""
        pass

    # ============================================================
    # Order Management
    # ============================================================

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResult:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Dict:
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        pass

    # ============================================================
    # Safety Checks (MANDATORY)
    # ============================================================

    def validate_order_safety(self, order: OrderRequest) -> tuple[bool, str]:
        """
        Safety validation before any order is placed.
        This cannot be bypassed.
        """
        # Withdrawals are NEVER allowed through this bot
        if hasattr(order, 'is_withdrawal') and order.is_withdrawal:
            return False, "WITHDRAWALS ARE NOT PERMITTED THROUGH THIS BOT"

        if order.quantity <= 0:
            return False, f"Invalid quantity: {order.quantity}"

        if order.order_type in [OrderType.LIMIT, OrderType.STOP_LOSS_LIMIT, OrderType.TAKE_PROFIT_LIMIT]:
            if not order.price or order.price <= 0:
                return False, "Limit orders require a valid price"

        return True, "Order is valid"

    # ============================================================
    # Rate Limiting
    # ============================================================

    @abstractmethod
    async def handle_rate_limit(self, retry_after: int = None):
        """Handle rate limit responses from exchange."""
        pass

    # ============================================================
    # Properties
    # ============================================================

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def exchange_name(self) -> str:
        return self.__class__.__name__.replace("Connector", "").lower()
