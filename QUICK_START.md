# 🚀 Quick Start Guide - NWH Crypto Trading Bot

Get your automated crypto trading bot running in **5 minutes**!

## ⚡ 5-Minute Setup

### 1️⃣ Clone & Setup
```bash
git clone https://github.com/hesabikahkashan-coder/cuddly-octo-adventure.git
cd cuddly-octo-adventure
cp .env.example .env
```

### 2️⃣ Configure (Edit `.env`)
```bash
# Update these values:
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
POSTGRES_PASSWORD=strong_password
REDIS_PASSWORD=strong_password
TELEGRAM_BOT_TOKEN=your_token (optional)
TELEGRAM_CHAT_ID=your_id (optional)
```

### 3️⃣ Start Services
```bash
docker-compose up -d
```

### 4️⃣ Access Dashboard
Open browser: **http://localhost**

### 5️⃣ Login
- Username: `admin`
- Password: `admin`

---

## 🌐 Access Dashboard

### Local Access
```
http://localhost
http://your-machine-ip
```

### API Documentation
```
http://localhost:8000/api/docs
```

### Monitoring Dashboards
```
Grafana: http://localhost:3001 (admin/admin)
Prometheus: http://localhost:9090
Database: http://localhost:8080 (Adminer)
Redis: http://localhost:8081 (Commander)
```

---

## 📊 Dashboard Features

✅ **Trading Dashboard** - Real-time trade status
✅ **Risk Monitor** - Drawdown & daily loss tracking  
✅ **Performance Charts** - Win rate, profit factor, equity curve
✅ **Exchange Status** - Connected exchanges & API health
✅ **Notifications** - Trade alerts & system events

---

## 🎯 Start Trading

### Paper Trading (Recommended for Testing)
No real money is used. Perfect for testing strategies.

```env
TRADING_MODE=paper
INITIAL_BALANCE=10000
```

### Live Trading (Production)
⚠️ **Only after testing thoroughly!**

1. Update `.env`:
```env
TRADING_MODE=live
MAX_DRAWDOWN_PERCENT=15
DAILY_LOSS_LIMIT=-1000
STOP_LOSS_PERCENT=3
```

2. Set conservative risk limits first

3. Start with small position sizes

---

## 🔌 Connect Exchanges

### Binance
1. Visit https://www.binance.com/account/api-management
2. Create API Key with:
   - ✅ Read
   - ✅ Trade
   - ❌ NO Withdrawals
3. Add to `.env`:
```env
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=yyy
```

### Bybit
1. Visit https://www.bybit.com/app/user/api-management
2. Create API Key (same permissions)
3. Add to `.env`:
```env
BYBIT_API_KEY=xxx
BYBIT_API_SECRET=yyy
```

---

## 📱 Telegram Notifications

### Setup
1. Message **@BotFather** on Telegram
2. Send `/newbot` and follow prompts
3. Get bot token
4. Message your bot
5. Message **@userinfobot** to get chat ID

### Configure
```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_id
```

---

## 🛡️ Risk Management

Configure in `.env`:

```env
# Stop if drawdown > 20%
MAX_DRAWDOWN_PERCENT=20

# Stop if daily loss > -$500
DAILY_LOSS_LIMIT=-500

# Stop loss on every trade
STOP_LOSS_PERCENT=2

# Take profit target
TAKE_PROFIT_PERCENT=5

# Max position size
MAX_POSITION_SIZE_PERCENT=10
```

---

## 🔧 Useful Commands

```bash
# View logs
docker-compose logs -f backend

# Check health
curl http://localhost:8000/health

# Enter shell
docker-compose exec backend bash

# Run migrations
docker-compose exec backend alembic upgrade head

# Restart services
docker-compose restart

# Stop all
docker-compose down
```

---

## 📈 API Examples

### Get Account Summary
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/dashboard/summary
```

### View Active Trades
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/trades?status=open
```

### Place a Trade
```bash
curl -X POST http://localhost:8000/api/v1/trades \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "side": "buy",
    "quantity": 0.01,
    "stop_loss_percent": 2
  }'
```

---

## 🚨 Safety Checklist

- [ ] Start in **PAPER TRADING** mode
- [ ] Set **STOP LOSS** on every trade
- [ ] Configure **DRAWDOWN LIMITS**
- [ ] Use **READ + TRADE** API permissions (NO withdrawals)
- [ ] Enable **2FA** on exchange accounts
- [ ] Change default **passwords**
- [ ] **Test thoroughly** before going live
- [ ] Monitor **first trades** closely

---

## ❓ Common Issues

| Issue | Solution |
|-------|----------|
| Port 80 in use | `docker-compose up -d -p 8080:80` |
| Services won't start | `docker-compose logs backend` |
| Can't connect to exchange | Verify API keys & IP whitelist |
| Dashboard won't load | Clear cache & restart frontend |

---

## 📞 Resources

- 📖 [Full Setup Guide](./SETUP.md)
- 🔗 [API Docs](http://localhost:8000/api/docs)
- 🐛 [Report Issues](https://github.com/hesabikahkashan-coder/cuddly-octo-adventure/issues)

---

## 🎓 Next Steps

1. **Test Strategy** - Paper trade for 1-2 weeks
2. **Analyze Results** - Check win rate & drawdown
3. **Optimize** - Adjust parameters based on results
4. **Go Live** - Start with small position sizes
5. **Monitor** - Watch first trades closely

---

**Ready to automate your trading? Start now! 🚀**

*Remember: Past performance ≠ future results. Always use risk management!*
