"""
NWH Crypto Trading Bot - Core Configuration
Enterprise-grade configuration management with environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
from functools import lru_cache
import secrets


class DatabaseSettings(BaseSettings):
    POSTGRES_HOST: str = Field(default="localhost", env="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    POSTGRES_USER: str = Field(default="nwh_user", env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(..., env="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(default="nwh_trading", env="POSTGRES_DB")
    POSTGRES_POOL_SIZE: int = Field(default=20, env="POSTGRES_POOL_SIZE")
    POSTGRES_MAX_OVERFLOW: int = Field(default=40, env="POSTGRES_MAX_OVERFLOW")

    @property
    def async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    class Config:
        env_file = ".env"


class RedisSettings(BaseSettings):
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_MAX_CONNECTIONS: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")

    @property
    def url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    class Config:
        env_file = ".env"


class SecuritySettings(BaseSettings):
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(64), env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    ENCRYPTION_KEY: str = Field(..., env="ENCRYPTION_KEY")  # For AES-256
    TWO_FA_ISSUER: str = Field(default="NWH Crypto Bot", env="TWO_FA_ISSUER")
    ALLOWED_IPS: List[str] = Field(default=[], env="ALLOWED_IPS")
    SESSION_TIMEOUT_MINUTES: int = Field(default=60, env="SESSION_TIMEOUT_MINUTES")

    class Config:
        env_file = ".env"


class KafkaSettings(BaseSettings):
    KAFKA_BOOTSTRAP_SERVERS: str = Field(default="localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    KAFKA_TOPIC_TRADES: str = Field(default="nwh.trades", env="KAFKA_TOPIC_TRADES")
    KAFKA_TOPIC_ORDERS: str = Field(default="nwh.orders", env="KAFKA_TOPIC_ORDERS")
    KAFKA_TOPIC_MARKET_DATA: str = Field(default="nwh.market_data", env="KAFKA_TOPIC_MARKET_DATA")
    KAFKA_TOPIC_RISK_ALERTS: str = Field(default="nwh.risk_alerts", env="KAFKA_TOPIC_RISK_ALERTS")
    KAFKA_CONSUMER_GROUP: str = Field(default="nwh-trading-group", env="KAFKA_CONSUMER_GROUP")

    class Config:
        env_file = ".env"


class NotificationSettings(BaseSettings):
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")
    SMTP_HOST: str = Field(default="smtp.gmail.com", env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USER: Optional[str] = Field(default=None, env="SMTP_USER")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    NOTIFICATION_EMAIL: Optional[str] = Field(default=None, env="NOTIFICATION_EMAIL")

    class Config:
        env_file = ".env"


class TradingSettings(BaseSettings):
    MAX_SIMULTANEOUS_TRADES: int = Field(default=5, env="MAX_SIMULTANEOUS_TRADES")
    MAX_DAILY_DRAWDOWN_PERCENT: float = Field(default=5.0, env="MAX_DAILY_DRAWDOWN_PERCENT")
    DEFAULT_RISK_PER_TRADE_PERCENT: float = Field(default=1.0, env="DEFAULT_RISK_PER_TRADE_PERCENT")
    MIN_RISK_REWARD_RATIO: float = Field(default=1.5, env="MIN_RISK_REWARD_RATIO")
    MAX_POSITION_SIZE_PERCENT: float = Field(default=10.0, env="MAX_POSITION_SIZE_PERCENT")
    PAPER_TRADING_BALANCE: float = Field(default=10000.0, env="PAPER_TRADING_BALANCE")
    TRADING_MODE: str = Field(default="paper", env="TRADING_MODE")  # paper | live
    SUPPORTED_EXCHANGES: List[str] = Field(default=["binance", "bybit"], env="SUPPORTED_EXCHANGES")

    class Config:
        env_file = ".env"


class AppSettings(BaseSettings):
    APP_NAME: str = "NWH Crypto Trading Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="production", env="ENVIRONMENT")
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"], env="CORS_ORIGINS")
    WORKERS: int = Field(default=4, env="WORKERS")

    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    security: SecuritySettings = SecuritySettings()
    kafka: KafkaSettings = KafkaSettings()
    notifications: NotificationSettings = NotificationSettings()
    trading: TradingSettings = TradingSettings()

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()
