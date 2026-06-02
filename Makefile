.PHONY: help build up down logs restart clean test lint format

# Default target
help:
	@echo "NWH Crypto Trading Bot - Available Commands"
	@echo "============================================"
	@echo "make build         - Build Docker images"
	@echo "make up            - Start all services"
	@echo "make down          - Stop all services"
	@echo "make restart       - Restart all services"
	@echo "make logs          - View service logs"
	@echo "make logs-backend  - View backend logs"
	@echo "make test          - Run tests"
	@echo "make lint          - Run linting"
	@echo "make format        - Format code"
	@echo "make clean         - Remove containers and volumes"
	@echo "make shell         - Access backend shell"
	@echo "make migrate       - Run database migrations"

# Build images
build:
	docker-compose build

# Start services
up:
	docker-compose up -d
	@echo "Services started. Access dashboard at http://localhost"

# Stop services
down:
	docker-compose down

# Restart services
restart: down up

# View logs
logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

logs-postgres:
	docker-compose logs -f postgres

# Run tests
test:
	docker-compose exec backend pytest tests/ -v

test-cov:
	docker-compose exec backend pytest tests/ --cov=. --cov-report=html

# Lint code
lint:
	docker-compose exec backend flake8 . --max-line-length=120

# Format code
format:
	docker-compose exec backend black .

# Clean up
clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Access shell
shell:
	docker-compose exec backend /bin/bash

shell-frontend:
	docker-compose exec frontend /bin/sh

# Database operations
migrate:
	docker-compose exec backend alembic upgrade head

migrate-revision:
	docker-compose exec backend alembic revision --autogenerate

# Check health
health:
	@echo "Checking service health..."
	@curl -s http://localhost:8000/health | jq .
	@echo ""

# Development setup
dev-setup:
	cp .env.example .env
	make build
	make up
	@echo "Development environment ready!"

# Production setup
prod-setup:
	cp .env.example .env
	@echo "Update .env with production values"
	make build
	make up
