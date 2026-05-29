#!/bin/bash
# NWH Crypto Bot - Production Deployment Script
set -e

echo "🚀 NWH Crypto Trading Bot - Deployment"
echo "======================================="

# Check .env
if [ ! -f .env ]; then
    echo "❌ .env file not found. Copy .env.example to .env and fill values."
    exit 1
fi

# Pull latest
echo "📦 Pulling latest images..."
docker-compose pull

# Build
echo "🔨 Building services..."
docker-compose build --no-cache

# Stop old containers
echo "⏹ Stopping old containers..."
docker-compose down

# Start
echo "▶️  Starting services..."
docker-compose up -d

# Wait for DB
echo "⏳ Waiting for database..."
sleep 10

# Run migrations
echo "🗄 Running database migrations..."
docker-compose exec backend alembic upgrade head

echo ""
echo "✅ Deployment complete!"
echo "   Frontend: https://localhost"
echo "   API:      https://localhost/api/v1"
echo "   Grafana:  http://localhost:3001"
