# NWH Crypto Trading Bot

Enterprise-grade automated cryptocurrency trading platform.

## Quick Start

1. Copy `.env.example` to `.env` and fill your values
2. Run: `bash deployment/scripts/deploy.sh`
3. Open: `https://your-server-ip`

## Requirements

- Docker + Docker Compose
- A VPS (minimum 2GB RAM, 20GB SSD)
- Binance/Bybit API keys (READ + TRADE only, NO withdrawals)

## Structure

```
backend/        FastAPI backend
frontend/       React + TypeScript dashboard
deployment/     Docker, Nginx, scripts
risk_engine/    Core risk management
strategies/     Trading strategies
exchanges/      Binance + Bybit connectors
backtesting/    Historical testing
paper_trading/  Simulated trading
notifications/  Telegram + Email alerts
```

## Safety Rules

- TRADING_MODE=paper by default (change to live only when ready)
- Stop loss is MANDATORY on every trade
- Daily drawdown limit auto-halts trading
- API keys are encrypted with AES-256

## Support

Telegram notifications are built-in.
Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.
