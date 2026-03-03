# ═══════════════════════════════════════════════════════════════════════════
# Makefile for Drift Detection Service
# ═══════════════════════════════════════════════════════════════════════════
# Provides convenient commands for Docker operations and service management

.PHONY: help setup build up down restart logs status clean test shell db-init

# Default target
help:
	@echo "════════════════════════════════════════════════════════════════"
	@echo "  Drift Detection Service - Available Commands"
	@echo "════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "  Setup & Build:"
	@echo "    make setup       - Copy .env.example to .env"
	@echo "    make build       - Build Docker images"
	@echo "    make rebuild     - Rebuild images from scratch (no cache)"
	@echo ""
	@echo "  Service Management:"
	@echo "    make up          - Start all services"
	@echo "    make down        - Stop all services"
	@echo "    make restart     - Restart all services"
	@echo "    make stop        - Stop services without removing"
	@echo ""
	@echo "  Logs & Monitoring:"
	@echo "    make logs        - View logs from all services"
	@echo "    make logs-api    - View API service logs"
	@echo "    make logs-worker - View worker service logs"
	@echo "    make logs-consumer - View consumer service logs"
	@echo "    make status      - Check service status"
	@echo "    make stats       - Show resource usage"
	@echo ""
	@echo "  Development:"
	@echo "    make shell       - Open shell in API container"
	@echo "    make shell-worker - Open shell in worker container"
	@echo "    make test        - Run tests inside container"
	@echo "    make db-init     - Initialize database schema"
	@echo ""
	@echo "  Worker Management:"
	@echo "    make worker-ping - Check worker health"
	@echo "    make worker-stats - Show worker statistics"
	@echo "    make worker-active - Show active tasks"
	@echo "    make scale-workers N=3 - Scale workers to N instances"
	@echo ""
	@echo "  Redis (shared-redis on shared-network):"
	@echo "    make redis-cli   - Open Redis CLI"
	@echo "    make redis-info  - Show Redis info"
	@echo "    make network     - Create shared-network if not exists"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean       - Stop and remove containers"
	@echo "    make clean-all   - Remove containers, volumes, and images"
	@echo ""
	@echo "════════════════════════════════════════════════════════════════"

# ─── Setup & Build ───────────────────────────────────────────────────────────

setup:
	@echo "📋 Setting up environment..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env from .env.example"; \
		echo "⚠️  Please edit .env with your actual configuration"; \
	else \
		echo "⚠️  .env already exists, skipping..."; \
	fi

build:
	@echo "🔨 Building Docker images..."
	docker-compose build
	@echo "✓ Build complete"

rebuild:
	@echo "🔨 Rebuilding Docker images (no cache)..."
	docker-compose build --no-cache
	@echo "✓ Rebuild complete"

# ─── Service Management ──────────────────────────────────────────────────────

up:
	@echo "🚀 Starting all services..."
	docker-compose up -d
	@echo "✓ Services started"
	@echo ""
	@echo "🔍 Checking service health..."
	@sleep 5
	@make status

down:
	@echo "🛑 Stopping all services..."
	docker-compose down
	@echo "✓ Services stopped"

restart:
	@echo "🔄 Restarting all services..."
	@make down
	@make up

stop:
	@echo "⏸️  Stopping services..."
	docker-compose stop
	@echo "✓ Services stopped (not removed)"

# ─── Logs & Monitoring ───────────────────────────────────────────────────────

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker

logs-consumer:
	docker-compose logs -f consumer

status:
	@echo "📊 Service Status:"
	@docker-compose ps
	@echo ""
	@echo "🏥 API Health:"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "⚠️  API not responding"

stats:
	@echo "📈 Resource Usage:"
	@docker stats --no-stream drift-api drift-worker drift-consumer

# ─── Development ─────────────────────────────────────────────────────────────

shell:
	@echo "🐚 Opening shell in API container..."
	docker exec -it drift-api bash

shell-worker:
	@echo "🐚 Opening shell in worker container..."
	docker exec -it drift-worker bash

test:
	@echo "🧪 Running tests..."
	docker exec drift-api pytest -v

db-init:
	@echo "🗄️  Initializing database..."
	docker exec drift-api python -c "from app.db.connection import initialize_db; import asyncio; asyncio.run(initialize_db())"
	@echo "✓ Database initialized"

# ─── Worker Management ───────────────────────────────────────────────────────

worker-ping:
	@echo "🏓 Pinging Celery workers..."
	docker exec drift-worker celery -A app.workers.celery_app inspect ping

worker-stats:
	@echo "📊 Worker Statistics:"
	docker exec drift-worker celery -A app.workers.celery_app inspect stats

worker-active:
	@echo "⚡ Active Tasks:"
	docker exec drift-worker celery -A app.workers.celery_app inspect active

worker-registered:
	@echo "📝 Registered Tasks:"
	docker exec drift-worker celery -A app.workers.celery_app inspect registered

scale-workers:
	@echo "📈 Scaling workers to $(N) instances..."
	docker-compose up -d --scale worker=$(N)
	@echo "✓ Workers scaled to $(N)"

# ─── Redis ───────────────────────────────────────────────────────────────────

redis-cli:
	@echo "🔴 Opening Redis CLI (shared-redis)..."
	docker exec -it shared-redis redis-cli

redis-info:
	@echo "ℹ️  Redis Info (shared-redis):"
	docker exec shared-redis redis-cli info

redis-streams:
	@echo "📡 Redis Streams Info (shared-redis):"
	@echo ""
	@echo "Behavior Events Stream:"
	@docker exec shared-redis redis-cli XINFO STREAM behavior.events || echo "Stream does not exist yet"
	@echo ""
	@echo "Drift Events Stream:"
	@docker exec shared-redis redis-cli XINFO STREAM drift.events || echo "Stream does not exist yet"

network:
	@echo "🌐 Checking shared-network..."
	@docker network inspect shared-network >/dev/null 2>&1 || \
		(docker network create shared-network && echo "✓ Created shared-network") && \
		echo "✓ shared-network exists"

# ─── Cleanup ─────────────────────────────────────────────────────────────────

clean:
	@echo "🧹 Cleaning up containers..."
	docker-compose down
	@echo "✓ Containers removed"

clean-all:
	@echo "🧹 Cleaning up everything (containers, volumes, images)..."
	@read -p "⚠️  This will delete all data. Continue? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker-compose down -v; \
		docker rmi drift_detection_service_api drift_detection_service_worker drift_detection_service_consumer 2>/dev/null || true; \
		echo "✓ Cleanup complete"; \
	else \
		echo "❌ Cancelled"; \
	fi

# ─── Utility ─────────────────────────────────────────────────────────────────

seed-data:
	@echo "🌱 Seeding test data..."
	docker exec drift-api python scripts/seed_test_data.py --user test_user --pattern all
	@echo "✓ Test data seeded"

run-detection:
	@echo "🔍 Running drift detection for test_user..."
	docker exec drift-api python -m scripts.run_detection test_user
	@echo "✓ Detection complete"

# ═══════════════════════════════════════════════════════════════════════════
# End of Makefile
# ═══════════════════════════════════════════════════════════════════════════
