"""
NWH Crypto Trading Bot - Structured Logging
Enterprise-grade structured logging with JSON output and log levels.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pythonjsonlogger import jsonlogger


class NWHJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""

    def add_fields(self, log_record: Dict, record: logging.LogRecord, message_dict: Dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno
        log_record["app"] = "nwh-crypto-bot"

        # Remove redundant fields
        log_record.pop("levelname", None)
        log_record.pop("name", None)


class TradeLogger:
    """Specialized logger for trade events."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def log_trade_opened(self, trade_data: Dict[str, Any]):
        self._logger.info("Trade opened", extra={"event": "trade_opened", **trade_data})

    def log_trade_closed(self, trade_data: Dict[str, Any]):
        self._logger.info("Trade closed", extra={"event": "trade_closed", **trade_data})

    def log_trade_rejected(self, reason: str, trade_data: Dict[str, Any]):
        self._logger.warning("Trade rejected", extra={"event": "trade_rejected", "reason": reason, **trade_data})

    def log_stop_loss_hit(self, trade_data: Dict[str, Any]):
        self._logger.warning("Stop loss hit", extra={"event": "stop_loss_hit", **trade_data})

    def log_take_profit_hit(self, trade_data: Dict[str, Any]):
        self._logger.info("Take profit hit", extra={"event": "take_profit_hit", **trade_data})

    def log_risk_warning(self, message: str, context: Dict[str, Any]):
        self._logger.error("Risk warning", extra={"event": "risk_warning", "message": message, **context})


class AuditLogger:
    """Audit logger for security and compliance events."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def log_login(self, user_id: str, ip: str, success: bool):
        self._logger.info(
            "Login attempt",
            extra={"event": "login", "user_id": user_id, "ip": ip, "success": success}
        )

    def log_api_key_access(self, user_id: str, exchange: str, action: str):
        self._logger.info(
            "API key accessed",
            extra={"event": "api_key_access", "user_id": user_id, "exchange": exchange, "action": action}
        )

    def log_settings_change(self, user_id: str, setting: str, old_value: Any, new_value: Any):
        self._logger.warning(
            "Settings changed",
            extra={
                "event": "settings_change",
                "user_id": user_id,
                "setting": setting,
                "old_value": str(old_value),
                "new_value": str(new_value)
            }
        )

    def log_2fa_event(self, user_id: str, action: str, success: bool):
        self._logger.info(
            "2FA event",
            extra={"event": "2fa", "user_id": user_id, "action": action, "success": success}
        )


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure application-wide logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    if json_output:
        handler = logging.StreamHandler(sys.stdout)
        formatter = NWHJsonFormatter(
            "%(timestamp)s %(level)s %(module)s %(message)s"
        )
        handler.setFormatter(formatter)
    else:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # Suppress noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)


def get_trade_logger() -> TradeLogger:
    """Get the specialized trade logger."""
    return TradeLogger(get_logger("nwh.trades"))


def get_audit_logger() -> AuditLogger:
    """Get the audit logger."""
    return AuditLogger(get_logger("nwh.audit"))
