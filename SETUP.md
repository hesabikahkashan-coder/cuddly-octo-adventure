# NWH Crypto Trading Bot - Complete Setup Guide

## 📋 Prerequisites

- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **System Requirements**: Minimum 2GB RAM, 20GB SSD
- **Binance/Bybit API Keys** - Create at exchange accounts
- **Telegram Bot** (optional) - For notifications
- **Domain & SSL** (optional) - For production deployment

## 🚀 Quick Installation (5 Minutes)

### Step 1: Clone Repository
```bash
git clone https://github.com/hesabikahkashan-coder/cuddly-octo-adventure.git
cd cuddly-octo-adventure
```

### Step 2: Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```bash
nano .env
```

Key variables to update:
- `BINANCE_API_KEY` and `BINANCE_API_SECRET`
- `POSTGRES_PASSWORD` (change from default)
- `REDIS_PASSWORD` (change from default)
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (optional)

### Step 3: Start Services
```bash
docker-compose up -d
```

### Step 4: Verify Installation
```bash
# Check if all services are running
docker-compose ps

# Check backend health
curl http://localhost:8000/health
```

### Step 5: Access Dashboard
Open your browser:
- **Dashboard UI**: http://localhost
- **API Documentation**: http://localhost:8000/api/docs
- **Grafana Monitoring**: http://localhost:3001 (admin/admin)

---

## ⚙️ Configuration Guide

### Trading Mode Setup

#### Paper Trading (Recommended for Testing)
```env
TRADING_MODE=paper
INITIAL_BALANCE=10000
```

#### Live Trading (Production)
⚠️ **WARNING**: Only enable after thorough testing!

1. Update `.env`:
```env
TRADING_MODE=live
```

2. Set conservative risk parameters:
```env
MAX_DRAWDOWN_PERCENT=15
DAILY_LOSS_LIMIT=-1000
STOP_LOSS_PERCENT=3
```

### Exchange API Keys

#### Binance Setup
1. Visit https://www.binance.com/account/api-management
2. Click "Create API"
3. Configure permissions:
   - ✅ **Enable Reading** (for positions)
   - ✅ **Enable Margin Account Transfer** (for trades)
   - ✅ **Enable Spot & Margin Trading**
   - ❌ **Disable Withdrawals** (for security)
4. Add to `.env`:
```env
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=False
```

#### Bybit Setup
1. Visit https://www.bybit.com/app/user/api-management
2. Create API Key with same permissions
3. Add to `.env`:
```env
BYBIT_API_KEY=your_key_here
BYBIT_API_SECRET=your_secret_here
BYBIT_TESTNET=False
```

### Risk Management Configuration

```env
# Stop trading if drawdown exceeds this percentage
MAX_DRAWDOWN_PERCENT=20

# Stop trading if daily loss exceeds this amount (USD)
DAILY_LOSS_LIMIT=-500

# Mandatory stop loss for every trade
STOP_LOSS_PERCENT=2

# Default take profit target
TAKE_PROFIT_PERCENT=5

# Maximum position size as % of account
MAX_POSITION_SIZE_PERCENT=10
```

### Telegram Notifications

#### Setup Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Follow prompts to name your bot
4. Copy the provided **Bot Token**
5. Send a message to your bot (just say "hi")
6. Search for **@userinfobot** to get your **Chat ID**

#### Configure in .env
```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=1234567890
```

#### Verify Setup
```bash
docker-compose logs -f backend | grep "Telegram"
```

### SSL/HTTPS Setup

#### Generate Self-Signed Certificate
```bash
mkdir -p deployment/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout deployment/nginx/ssl/private.key \
  -out deployment/nginx/ssl/certificate.crt
```

#### Using Let's Encrypt (Recommended for Production)
```bash
apt-get install certbot python3-certbot-nginx
certbot certonly --nginx -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem deployment/nginx/ssl/private.key
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem deployment/nginx/ssl/certificate.crt
```

---

## 📊 Dashboard Access

### Local Network Access
- URL: `http://localhost`
- URL: `http://your-machine-ip`

### Remote Access (VPS)

#### Step 1: Update DNS
Point your domain to your VPS IP address

#### Step 2: Update Configuration
Edit `.env`:
```env
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

Update `nginx.conf`:
```nginx
server_name yourdomain.com www.yourdomain.com;
```

#### Step 3: Access Dashboard
- URL: `https://yourdomain.com`

### Dashboard Features

1. **Trading Dashboard**
   - Active trades overview
   - P&L summary
   - Risk metrics
   - Account balance

2. **Risk Management**
   - Drawdown monitor
   - Daily loss tracking
   - Position sizing
   - Stop loss enforcement

3. **Performance Analytics**
   - Win rate statistics
   - Profit factor
   - Sharpe ratio
   - Equity curve

4. **Exchange Status**
   - Connected exchanges
   - API health
   - Order status

5. **Notifications Log**
   - Trade alerts
   - Risk warnings
   - System events

---

## 🔌 API Integration

### Authentication
```bash
# Get access token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | jq -r '.access_token')

# Use token in requests
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/dashboard/summary
```

### Example API Calls

#### Get Account Summary
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/dashboard/summary | jq
```

#### Get Active Trades
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/trades?status=open | jq
```

#### Place a Trade (Paper Mode)
```bash
curl -X POST http://localhost:8000/api/v1/trades \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "exchange": "binance",
    "symbol": "BTCUSDT",
    "side": "buy",
    "quantity": 0.01,
    "stop_loss_percent": 2,
    "take_profit_percent": 5
  }' | jq
```

#### Get Performance Metrics
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/risk/metrics | jq
```

---

## 🧪 Backtesting

### Run Backtest via API
```bash
curl -X POST http://localhost:8000/api/v1/backtests \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "strategy_id": 1,
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_balance": 10000,
    "symbols": ["BTCUSDT", "ETHUSDT"]
  }' | jq
```

### Get Backtest Results
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/backtests/1/results | jq
```

---

## 📈 Monitoring & Logs

### View Service Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

### Access Monitoring Dashboard

#### Prometheus (Metrics)
- URL: http://localhost:9090
- Query: `http_requests_total`, `trade_count`, `balance_total`

#### Grafana (Dashboards)
- URL: http://localhost:3001
- Username: admin
- Password: admin

#### Database Explorer
- URL: http://localhost:8080 (Adminer)
- Database: nwh_trading

#### Redis Commander
- URL: http://localhost:8081

---

## 🛠️ Useful Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart all services
docker-compose restart

# View logs
docker-compose logs -f

# Access backend shell
docker-compose exec backend bash

# Run database migrations
docker-compose exec backend alembic upgrade head

# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Run tests
docker-compose exec backend pytest tests/ -v

# Run linting
docker-compose exec backend flake8 . --max-line-length=120

# Clean up (⚠️ removes all data)
docker-compose down -v
```

---

## 🔒 Security Best Practices

### ✅ Required Actions

- [ ] Change `SECRET_KEY` in `.env`
- [ ] Change `POSTGRES_PASSWORD` (not the default)
- [ ] Change `REDIS_PASSWORD` (not the default)
- [ ] Change `GRAFANA_PASSWORD` from "admin"
- [ ] Use strong Telegram bot token
- [ ] Enable SSL/HTTPS certificates
- [ ] Whitelist API IP addresses on exchanges
- [ ] Set API permissions to READ + TRADE (NO WITHDRAWALS)
- [ ] Enable 2FA on exchange accounts

### 🔐 API Key Management

```bash
# Store API keys securely
export BINANCE_API_KEY="your-key"
export BINANCE_API_SECRET="your-secret"

# Never commit secrets to git
echo ".env" >> .gitignore
```

### Firewall Rules

```bash
# Allow only necessary ports
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw deny 5432      # Block PostgreSQL from outside
ufw deny 6379      # Block Redis from outside
```

---

## ❓ Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker --version

# View detailed logs
docker-compose logs --tail=50

# Rebuild images
docker-compose down
docker-compose up -d --build
```

### Database connection error
```bash
# Check PostgreSQL is healthy
docker-compose ps postgres

# View database logs
docker-compose logs postgres

# Reset database
docker-compose exec postgres psql -U trading_bot -d nwh_trading
```

### API returns 401 (Unauthorized)
- Check JWT token is valid
- Check token hasn't expired
- Verify `SECRET_KEY` matches

### Exchange connection fails
- Verify API keys are correct
- Check IP is whitelisted on exchange
- Ensure testnet/mainnet matches config
- Check API permissions are set correctly

### Frontend won't load
- Clear browser cache
- Check frontend service logs: `docker-compose logs frontend`
- Verify CORS settings in `.env`

---

## 📞 Support & Resources

- **API Docs**: http://localhost:8000/api/docs
- **GitHub**: https://github.com/hesabikahkashan-coder/cuddly-octo-adventure
- **Issues**: https://github.com/hesabikahkashan-coder/cuddly-octo-adventure/issues

---

## 📝 License

MIT License - See LICENSE file for details

---

**Happy Trading! 🚀** 

*Remember: Start with paper trading and always use risk management!*
