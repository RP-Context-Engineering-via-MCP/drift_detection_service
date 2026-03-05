# Complete Build System Guide - Drift Detection Service

> **Purpose**: This document provides a comprehensive, LLM-optimized explanation of the entire build system, deployment architecture, and operational workflow of the Drift Detection Service. Any AI model should be able to understand 100% of how this system is built, deployed, configured, and operated after reading this document.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Build System Architecture](#2-build-system-architecture)
3. [Docker Multi-Stage Build](#3-docker-multi-stage-build)
4. [Docker Compose Orchestration](#4-docker-compose-orchestration)
5. [Makefile Automation](#5-makefile-automation)
6. [Dependency Management](#6-dependency-management)
7. [Database Migrations](#7-database-migrations)
8. [Configuration System](#8-configuration-system)
9. [Service Entry Points](#9-service-entry-points)
10. [Testing Infrastructure](#10-testing-infrastructure)
11. [Deployment Workflow](#11-deployment-workflow)
12. [Build Optimization Techniques](#12-build-optimization-techniques)
13. [Network Architecture](#13-network-architecture)
14. [Environment Variables Reference](#14-environment-variables-reference)
15. [Build Troubleshooting](#15-build-troubleshooting)

---

## 1. System Overview

### 1.1 What This System Does

The **Drift Detection Service** is a microservice that:
- Detects behavioral drift in user preference patterns
- Processes behavior events from Redis Streams
- Runs machine learning-based anomaly detection
- Publishes drift events for downstream services
- Provides REST API for drift detection queries

### 1.2 Three-Service Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   DRIFT DETECTION SERVICE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│  │  drift-api       │  │  drift-worker    │  │ drift-consumer  │  │
│  │  (FastAPI)       │  │  (Celery)        │  │ (Redis Streams) │  │
│  ├──────────────────┤  ├──────────────────┤  ├─────────────────┤  │
│  │ • REST API       │  │ • Background     │  │ • Event stream  │  │
│  │ • Health checks  │  │   jobs           │  │   processing    │  │
│  │ • APScheduler    │  │ • Drift scans    │  │ • Snapshot      │  │
│  │ • Manual trigger │  │ • Task queue     │  │   updates       │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬────────┘  │
│           │                     │                      │           │
│           └─────────────────────┴──────────────────────┘           │
│                                 │                                  │
│                                 ▼                                  │
│              ┌──────────────────────────────────┐                  │
│              │   Shared Infrastructure          │                  │
│              ├──────────────────────────────────┤                  │
│              │ • PostgreSQL (Supabase)          │                  │
│              │ • Redis (shared-redis)           │                  │
│              │ • Docker Network (shared-network)│                  │
│              └──────────────────────────────────┘                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Point**: All three services are built from the **same Docker image** but with different startup commands.

---

## 2. Build System Architecture

### 2.1 Build Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    BUILD SYSTEM STACK                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: Makefile (User Interface)                            │
│  │                                                              │
│  │  make build → make up → make logs                           │
│  │                                                              │
│  ▼                                                              │
│  Layer 2: Docker Compose (Orchestration)                       │
│  │                                                              │
│  │  Defines 3 services (api, worker, consumer)                 │
│  │  Configures environment, ports, networks                    │
│  │                                                              │
│  ▼                                                              │
│  Layer 3: Dockerfile (Image Build)                             │
│  │                                                              │
│  │  Multi-stage build: builder → runtime                       │
│  │  Base image: python:3.11-slim                               │
│  │                                                              │
│  ▼                                                              │
│  Layer 4: Python Dependencies (requirements.txt)               │
│  │                                                              │
│  │  FastAPI, Celery, Redis, PostgreSQL drivers, ML libs        │
│  │                                                              │
│  ▼                                                              │
│  Layer 5: Application Code                                     │
│  │                                                              │
│  │  Python modules: api/, app/, migrations/                    │
│  │                                                              │
│  └─────────────────────────────────────────────────────────────┘
```

### 2.2 Build Process Flow

```
┌──────────┐
│  make    │
│  build   │
└────┬─────┘
     │
     ▼
┌──────────────────┐
│ docker-compose   │
│ build            │
└────┬─────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│ Dockerfile Multi-Stage Build                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Stage 1: builder (python:3.11-slim)                        │
│  ┌────────────────────────────────────────────┐             │
│  │ 1. Install build tools (gcc, g++, libpq)  │             │
│  │ 2. Copy requirements.txt                   │             │
│  │ 3. pip install all dependencies            │             │
│  │ 4. Download ML model (all-MiniLM-L6-v2)    │             │
│  └────────────────────────────────────────────┘             │
│                       │                                      │
│                       ▼                                      │
│  Stage 2: runtime (python:3.11-slim)                        │
│  ┌────────────────────────────────────────────┐             │
│  │ 1. Create non-root user (appuser)          │             │
│  │ 2. Copy Python packages from builder       │             │
│  │ 3. Copy ML model cache from builder        │             │
│  │ 4. Copy application code                   │             │
│  │ 5. Set working directory to /app           │             │
│  │ 6. Expose port 8000                        │             │
│  └────────────────────────────────────────────┘             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────┐
│ Image Created:   │
│ drift-detection  │
│ (~500MB)         │
└──────────────────┘
```

---

## 3. Docker Multi-Stage Build

### 3.1 Dockerfile Architecture

**File**: `Dockerfile`

```dockerfile
# ═══════════════════════════════════════════════════════════════
# Stage 1: Builder - Heavy dependencies
# ═══════════════════════════════════════════════════════════════
FROM python:3.11-slim as builder

WORKDIR /build

# Install build tools (needed for compiling Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \          # C compiler for Python extensions
    g++ \          # C++ compiler for Python extensions
    libpq-dev \    # PostgreSQL development headers
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Pre-download ML model (sentence-transformers)
# This prevents downloading at runtime
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('all-MiniLM-L6-v2')"

# ═══════════════════════════════════════════════════════════════
# Stage 2: Runtime - Minimal production image
# ═══════════════════════════════════════════════════════════════
FROM python:3.11-slim

# Environment variables for Python
ENV PYTHONUNBUFFERED=1 \         # Disable output buffering
    PYTHONDONTWRITEBYTECODE=1 \   # Don't create .pyc files
    PIP_NO_CACHE_DIR=1 \          # Don't cache pip downloads
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \       # PostgreSQL runtime library
    && rm -rf /var/lib/apt/lists/*

# Fix IPv6 connection issues (force IPv4)
RUN echo "net.ipv6.conf.all.disable_ipv6 = 1" >> /etc/sysctl.conf || true && \
    echo "net.ipv6.conf.default.disable_ipv6 = 1" >> /etc/sysctl.conf || true && \
    echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy ML model cache from builder stage
COPY --from=builder /root/.cache /home/appuser/.cache

# Copy application code
COPY --chown=appuser:appuser . .

# Make scripts executable
RUN chmod +x run_api.py || true

# Switch to non-root user
USER appuser

# Add Python packages to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose FastAPI port
EXPOSE 8000

# Health check (checks if API is responding)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

# Default command (overridden in docker-compose.yml)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 Why Multi-Stage Build?

**Problem**: Single-stage builds include build tools in the final image, increasing size.

**Solution**: Multi-stage build separates build-time dependencies from runtime dependencies.

| Aspect | Without Multi-Stage | With Multi-Stage | Benefit |
|--------|-------------------|------------------|---------|
| **Image Size** | ~1.2 GB | ~500 MB | 58% smaller |
| **Build Tools** | Included (gcc, g++) | Not included | Better security |
| **Build Time** | Slower (repeats work) | Faster (caches builder) | Efficiency |
| **Attack Surface** | Large | Minimal | Security |

### 3.3 Build Caching Strategy

Docker caches each layer. The Dockerfile is ordered to maximize cache hits:

```
1. System packages (rarely change)     ← Cache layer
2. requirements.txt (changes rarely)   ← Cache layer
3. Python dependencies                 ← Cache layer
4. ML model download                   ← Cache layer
5. Application code (changes often)    ← Rebuild layer
```

**Result**: Changing application code doesn't trigger rebuilding dependencies.

---

## 4. Docker Compose Orchestration

### 4.1 Docker Compose Architecture

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  # ──────────────────────────────────────────────────────
  # Service 1: API (FastAPI + APScheduler)
  # ──────────────────────────────────────────────────────
  api:
    build:
      context: .           # Build from current directory
      dockerfile: Dockerfile
    container_name: drift-api
    ports:
      - "8000:8000"        # Expose API to host
    environment:
      # ... (see section 8 for full list)
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/api/v1/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
    networks:
      - shared-network
    # DEFAULT CMD: uvicorn api.main:app --host 0.0.0.0 --port 8000

  # ──────────────────────────────────────────────────────
  # Service 2: Worker (Celery for background jobs)
  # ──────────────────────────────────────────────────────
  worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: drift-worker
    command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
    environment:
      # ... (same as API, except consumer-specific vars)
    healthcheck:
      test: ["CMD", "celery", "-A", "app.workers.celery_app", "inspect", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    restart: unless-stopped
    networks:
      - shared-network
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M

  # ──────────────────────────────────────────────────────
  # Service 3: Consumer (Redis Streams consumer)
  # ──────────────────────────────────────────────────────
  consumer:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: drift-consumer
    command: python -m app.consumer
    environment:
      # ... (same as API)
    restart: unless-stopped
    networks:
      - shared-network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.25'
          memory: 256M

# ──────────────────────────────────────────────────────
# Network Configuration
# ──────────────────────────────────────────────────────
networks:
  shared-network:
    external: true      # Must exist before `docker-compose up`
    name: shared-network
```

### 4.2 Service Roles Explained

| Service | Port | Command | Purpose | Resource Needs |
|---------|------|---------|---------|----------------|
| **api** | 8000 | `uvicorn api.main:app` | REST API, APScheduler cron jobs | Low CPU, low memory |
| **worker** | - | `celery worker` | Executes drift scan jobs | High CPU, high memory (ML) |
| **consumer** | - | `python -m app.consumer` | Processes Redis Streams | Low CPU, low memory |

### 4.3 Key Docker Compose Concepts

#### 4.3.1 Single Image, Multiple Commands

All three services use the **same Docker image** but different startup commands:

```yaml
# Same build context for all
build:
  context: .
  dockerfile: Dockerfile

# Different commands per service
api:     command: uvicorn api.main:app ...
worker:  command: celery -A app.workers.celery_app worker ...
consumer: command: python -m app.consumer
```

**Why?** This avoids maintaining multiple Dockerfiles and ensures all services use identical dependencies.

#### 4.3.2 Environment Variable Injection

Each service receives configuration via environment variables:

```yaml
environment:
  - DATABASE_URL=${DATABASE_URL}    # From .env file
  - REDIS_URL=redis://shared-redis:6379/0
  - MIN_BEHAVIORS_FOR_DRIFT=${MIN_BEHAVIORS_FOR_DRIFT:-5}
```

**Syntax**: `${VAR:-default}` means "use `VAR` from `.env`, or use `default` if not set".

#### 4.3.3 Health Checks

Each service defines a health check command:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/api/v1/health', timeout=5)"]
  interval: 30s      # Check every 30 seconds
  timeout: 10s       # Fail if check takes >10s
  retries: 3         # Try 3 times before marking unhealthy
  start_period: 40s  # Wait 40s after start before first check
```

**Purpose**: Docker can automatically restart unhealthy containers.

#### 4.3.4 Resource Limits

```yaml
deploy:
  resources:
    limits:
      cpus: '2'        # Maximum 2 CPU cores
      memory: 2G       # Maximum 2GB RAM
    reservations:
      cpus: '0.5'      # Guaranteed 0.5 CPU cores
      memory: 512M     # Guaranteed 512MB RAM
```

**Purpose**: Prevents a single service from consuming all host resources.

#### 4.3.5 Restart Policies

```yaml
restart: unless-stopped
```

| Policy | Behavior |
|--------|----------|
| `no` | Never restart |
| `always` | Always restart (even after manual stop) |
| `on-failure` | Restart only if container exits with error |
| `unless-stopped` | Always restart unless manually stopped |

---

## 5. Makefile Automation

### 5.1 Makefile Purpose

The `Makefile` provides a **user-friendly interface** to Docker and Docker Compose commands.

**File**: `Makefile`

### 5.2 Key Make Targets

| Command | What It Does | Docker Compose Equivalent |
|---------|--------------|---------------------------|
| `make help` | Show all commands | - |
| `make setup` | Create `.env` from `.env.example` | - |
| `make build` | Build Docker images | `docker-compose build` |
| `make rebuild` | Rebuild without cache | `docker-compose build --no-cache` |
| `make up` | Start all services | `docker-compose up -d` |
| `make down` | Stop and remove containers | `docker-compose down` |
| `make restart` | Restart all services | `make down && make up` |
| `make logs` | View all logs | `docker-compose logs -f` |
| `make logs-api` | View API logs only | `docker-compose logs -f api` |
| `make logs-worker` | View worker logs only | `docker-compose logs -f worker` |
| `make logs-consumer` | View consumer logs only | `docker-compose logs -f consumer` |
| `make status` | Check service health | `docker-compose ps` + API health check |
| `make shell` | Open bash in API container | `docker exec -it drift-api bash` |
| `make test` | Run tests in container | `docker exec drift-api pytest -v` |
| `make clean` | Stop and remove containers | `docker-compose down` |
| `make clean-all` | Remove everything (containers, volumes, images) | `docker-compose down -v --rmi all` |

### 5.3 Advanced Make Targets

#### Worker Management

```makefile
make worker-ping          # Check if worker is alive
make worker-stats         # Show task statistics
make worker-active        # Show currently running tasks
make scale-workers N=3    # Scale to 3 worker instances
```

#### Redis Management

```makefile
make redis-cli            # Open Redis CLI
make redis-info           # Show Redis server info
make redis-streams        # Show stream statistics
```

#### Network Management

```makefile
make network              # Create shared-network if not exists
```

### 5.4 Makefile Internals

Example target breakdown:

```makefile
up:
	@echo "🚀 Starting all services..."
	docker-compose up -d
	@echo "✓ Services started"
	@echo ""
	@echo "🔍 Checking service health..."
	@sleep 5
	@make status
```

**Explanation**:
- `@echo`: Print message (@ suppresses command echo)
- `docker-compose up -d`: Start services in detached mode
- `@sleep 5`: Wait 5 seconds for services to initialize
- `@make status`: Call another make target

---

## 6. Dependency Management

### 6.1 Requirements File Structure

**File**: `requirements.txt`

The dependencies are organized into categories:

```plaintext
# ═══════════════════════════════════════════════════════
# Core Dependencies
# ═══════════════════════════════════════════════════════
pydantic==2.7.1                    # Data validation
pydantic-settings==2.2.1           # Settings management
python-dotenv==1.0.0               # .env file loading

# ═══════════════════════════════════════════════════════
# Database
# ═══════════════════════════════════════════════════════
asyncpg==0.29.0                    # Async PostgreSQL driver
psycopg2-binary==2.9.9             # Sync PostgreSQL driver
alembic==1.13.1                    # Database migrations

# ═══════════════════════════════════════════════════════
# Message Broker / Cache
# ═══════════════════════════════════════════════════════
redis==5.0.1                       # Redis client

# ═══════════════════════════════════════════════════════
# Background Tasks & Scheduling
# ═══════════════════════════════════════════════════════
celery[redis]==5.4.0               # Distributed task queue
APScheduler==3.10.4                # Cron-style scheduling

# ═══════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════
python-dateutil==2.8.2             # Date/time utilities
numpy==1.26.4                      # Numerical operations

# ═══════════════════════════════════════════════════════
# ML / Embeddings
# ═══════════════════════════════════════════════════════
sentence-transformers==2.7.0       # Text embeddings (includes PyTorch)
scikit-learn==1.5.0                # DBSCAN clustering

# ═══════════════════════════════════════════════════════
# API / Web Framework
# ═══════════════════════════════════════════════════════
fastapi==0.110.0                   # Web framework
uvicorn[standard]==0.27.0          # ASGI server
python-multipart==0.0.9            # Form data parsing

# ═══════════════════════════════════════════════════════
# Testing
# ═══════════════════════════════════════════════════════
pytest==8.2.0                      # Test framework
pytest-asyncio==0.23.6             # Async test support
httpx==0.26.0                      # HTTP client for testing

# ═══════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════
python-json-logger==2.0.7          # JSON-formatted logs

# ═══════════════════════════════════════════════════════
# Type Checking
# ═══════════════════════════════════════════════════════
typing-extensions==4.9.0           # Extended type hints
```

### 6.2 Dependency Categories Explained

| Category | Purpose | Key Libraries |
|----------|---------|---------------|
| **Core** | Configuration, validation | pydantic, python-dotenv |
| **Database** | PostgreSQL access | asyncpg (async), psycopg2 (sync) |
| **Messaging** | Redis Streams, task queue | redis |
| **Background** | Async jobs, scheduling | Celery, APScheduler |
| **ML** | Text embeddings, clustering | sentence-transformers, scikit-learn |
| **API** | REST endpoints | FastAPI, uvicorn |
| **Testing** | Unit/integration tests | pytest, httpx |

### 6.3 Why Two PostgreSQL Drivers?

```
asyncpg  → Used by FastAPI endpoints (async operations)
psycopg2 → Used by Celery workers, scheduler (sync operations)
```

**Reason**: Celery doesn't support async database operations, so sync driver is required.

### 6.4 ML Model: sentence-transformers

The system uses **all-MiniLM-L6-v2** for generating text embeddings:

- **Purpose**: Convert behavior targets (e.g., "Python", "Docker") into 384-dimensional vectors
- **Use Case**: Clustering similar topics using DBSCAN
- **Size**: ~80MB
- **Downloaded**: During Docker build (cached in `/home/appuser/.cache`)

---

## 7. Database Migrations

### 7.1 Alembic Overview

**Alembic** is a database migration tool for PostgreSQL.

**Purpose**: Version control for database schema changes.

### 7.2 Alembic Configuration

**File**: `alembic.ini`

```ini
[alembic]
# Location of migration scripts
script_location = migrations

# File naming template (includes timestamp)
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

# Timezone for timestamps
timezone = UTC

# Database URL (loaded from environment)
sqlalchemy.url = 
```

**Key Point**: Database URL is loaded from `DATABASE_URL` environment variable (not hardcoded).

### 7.3 Migration Structure

```
migrations/
├── env.py                     # Alembic environment configuration
├── script.py.mako             # Template for new migrations
└── versions/
    └── 20260220_0001_001_initial_schema_initial_schema.py
```

### 7.4 Initial Schema Migration

**File**: `migrations/versions/20260220_0001_001_initial_schema_initial_schema.py`

Creates 4 tables:

#### Table 1: `behavior_snapshots`

Stores local copy of user behaviors from Behavior Service.

| Column | Type | Purpose |
|--------|------|---------|
| `user_id` | TEXT | User identifier |
| `behavior_id` | TEXT | Behavior identifier |
| `target` | TEXT | What the behavior is about (e.g., "Python") |
| `intent` | TEXT | Why (PREFERENCE, CONSTRAINT, SKILL, etc.) |
| `context` | TEXT | Where (e.g., "backend", "data_science") |
| `polarity` | TEXT | POSITIVE or NEGATIVE |
| `credibility` | REAL | Conviction strength (0.0 - 1.0) |
| `reinforcement_count` | INTEGER | How many times reinforced |
| `state` | TEXT | ACTIVE or SUPERSEDED |
| `created_at` | BIGINT | Unix timestamp (milliseconds) |
| `last_seen_at` | BIGINT | Unix timestamp (milliseconds) |
| `snapshot_updated_at` | BIGINT | When snapshot was updated |

**Indexes**:
- `(user_id, behavior_id)` - Primary key
- `(user_id, target)` - Fast lookup by target
- `(user_id, state)` - Fast active/superseded filtering
- `(user_id, last_seen_at)` - Time-based queries
- `(user_id, created_at)` - Historical queries

#### Table 2: `conflict_snapshots`

Stores local copy of resolved conflicts from Conflict Service.

| Column | Type | Purpose |
|--------|------|---------|
| `user_id` | TEXT | User identifier |
| `conflict_id` | TEXT | Conflict identifier |
| `behavior_id_1` | TEXT | First behavior in conflict |
| `behavior_id_2` | TEXT | Second behavior in conflict |
| `conflict_type` | TEXT | Type of conflict |
| `resolution_status` | TEXT | RESOLVED, PENDING, etc. |
| `old_polarity` | TEXT | Polarity before resolution |
| `new_polarity` | TEXT | Polarity after resolution |
| `old_target` | TEXT | Target before resolution |
| `new_target` | TEXT | Target after resolution |
| `created_at` | BIGINT | Unix timestamp |

#### Table 3: `drift_events`

Stores detected drift events.

| Column | Type | Purpose |
|--------|------|---------|
| `drift_event_id` | TEXT | Unique event ID |
| `user_id` | TEXT | User with drift |
| `drift_type` | TEXT | TOPIC_EMERGENCE, TOPIC_ABANDONMENT, etc. |
| `drift_score` | REAL | Strength of drift (0.0 - 1.0) |
| `confidence` | REAL | Detection confidence |
| `severity` | TEXT | WEAK_SIGNAL, MODERATE_DRIFT, STRONG_DRIFT |
| `affected_targets` | TEXT[] | List of affected topics |
| `evidence` | JSONB | Supporting data |
| `reference_window_start` | BIGINT | Historical window start |
| `reference_window_end` | BIGINT | Historical window end |
| `current_window_start` | BIGINT | Current window start |
| `current_window_end` | BIGINT | Current window end |
| `detected_at` | BIGINT | Detection timestamp |
| `acknowledged_at` | BIGINT | When acknowledged (nullable) |

**Indexes**:
- `drift_event_id` - Primary key
- `(user_id, detected_at)` - User's drift timeline
- `drift_type` - Filter by type
- `severity` - Filter by severity
- `(user_id, drift_type)` - User + type combination

#### Table 4: `drift_scan_jobs`

Queue for scheduled drift detection jobs.

| Column | Type | Purpose |
|--------|------|---------|
| `job_id` | UUID | Unique job ID (auto-generated) |
| `user_id` | TEXT | User to scan |
| `trigger_event` | TEXT | What triggered the scan |
| `status` | TEXT | PENDING, RUNNING, DONE, FAILED, SKIPPED |
| `priority` | TEXT | HIGH, NORMAL, LOW |
| `scheduled_at` | BIGINT | When job was scheduled |
| `started_at` | BIGINT | When job started (nullable) |
| `completed_at` | BIGINT | When job finished (nullable) |
| `error_message` | TEXT | Error details (nullable) |

**Constraint**: `status` must be one of the 5 valid values.

### 7.5 Running Migrations

```bash
# Upgrade to latest schema
docker exec drift-api alembic upgrade head

# Downgrade to previous version
docker exec drift-api alembic downgrade -1

# Show current version
docker exec drift-api alembic current

# Show migration history
docker exec drift-api alembic history
```

---

## 8. Configuration System

### 8.1 Configuration Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Configuration Flow                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. .env.example (Template)                            │
│     ↓                                                   │
│  2. .env (User copies and customizes)                  │
│     ↓                                                   │
│  3. Docker Compose (Reads .env, injects to containers) │
│     ↓                                                   │
│  4. app/config.py (Pydantic Settings reads env vars)   │
│     ↓                                                   │
│  5. Application Code (Uses Settings object)            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 8.2 Configuration File: app/config.py

**File**: `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",              # Read from .env file
        env_file_encoding="utf-8",
        case_sensitive=False          # DB_URL same as db_url
    )
    
    # ─── Application Settings ────────────────────────────
    app_name: str = "Drift Detection Service"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # ─── Database Settings ───────────────────────────────
    database_url: str                    # REQUIRED (no default)
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # ─── Redis Settings ──────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_behavior_events: str = "behavior.events"
    redis_stream_drift_events: str = "drift.events"
    redis_consumer_group: str = "drift_detection_service"
    
    # ─── Celery Settings ─────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # ─── Drift Detection Settings ────────────────────────
    drift_score_threshold: float = 0.6
    min_behaviors_for_drift: int = 5
    min_days_of_history: int = 14
    scan_cooldown_seconds: int = 3600
    
    # ... many more settings ...

@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
```

### 8.3 Configuration Categories

| Category | Settings | Purpose |
|----------|----------|---------|
| **Application** | `environment`, `debug`, `log_level` | Runtime behavior |
| **Database** | `database_url`, `db_pool_size` | PostgreSQL connection |
| **Redis Streams** | `redis_url`, stream names, consumer config | Event processing |
| **Celery** | `celery_broker_url`, task limits | Background jobs |
| **Drift Detection** | Thresholds, window sizes | Algorithm tuning |
| **Scheduling** | Scan intervals, cooldowns | Periodic jobs |

### 8.4 Environment Variables (Docker Compose)

In `docker-compose.yml`, environment variables are injected:

```yaml
environment:
  # Application
  - ENVIRONMENT=production
  - DEBUG=false
  - LOG_LEVEL=INFO
  
  # Database (from .env file)
  - DATABASE_URL=${DATABASE_URL}
  
  # Redis (hardcoded for Docker network)
  - REDIS_URL=redis://shared-redis:6379/0
  - REDIS_STREAM_BEHAVIOR_EVENTS=behavior.events
  - REDIS_STREAM_DRIFT_EVENTS=drift.events
  
  # Celery (hardcoded for Docker network)
  - CELERY_BROKER_URL=redis://shared-redis:6379/1
  - CELERY_RESULT_BACKEND=redis://shared-redis:6379/2
  
  # Thresholds (from .env with defaults)
  - MIN_BEHAVIORS_FOR_DRIFT=${MIN_BEHAVIORS_FOR_DRIFT:-5}
  - SCAN_COOLDOWN_SECONDS=${SCAN_COOLDOWN_SECONDS:-3600}
```

**Syntax Explained**:
- `${VAR}` - Use exact value from `.env` (fail if not set)
- `${VAR:-default}` - Use value from `.env`, or `default` if not set
- `hardcoded_value` - Literal value (not from `.env`)

---

## 9. Service Entry Points

### 9.1 Entry Point Overview

Each service has a different entry point (startup command):

| Service | Entry Point | File | Description |
|---------|-------------|------|-------------|
| **API** | `uvicorn api.main:app` | `api/main.py` | FastAPI application |
| **Worker** | `celery -A app.workers.celery_app worker` | `app/workers/celery_app.py` | Celery worker |
| **Consumer** | `python -m app.consumer` | `app/consumer/__main__.py` | Redis Streams consumer |

### 9.2 API Entry Point

**Command**: `uvicorn api.main:app --host 0.0.0.0 --port 8000`

**File**: `api/main.py`

```python
from fastapi import FastAPI
from app.scheduler import build_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup/shutdown."""
    # ─── STARTUP ───
    logger.info("Starting Drift Detection API...")
    scheduler = build_scheduler()
    scheduler.start()  # Start APScheduler
    logger.info("APScheduler started")
    
    yield
    
    # ─── SHUTDOWN ───
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)
    close_db_pool()

app = FastAPI(
    title="Drift Detection API",
    lifespan=lifespan
)

# Register routes
app.include_router(router, prefix="/api/v1")
```

**Key Features**:
1. **APScheduler**: Runs periodic cron jobs (user scanning, cleanup)
2. **FastAPI Routes**: REST API endpoints
3. **Database Pool**: Managed via lifespan events

### 9.3 Worker Entry Point

**Command**: `celery -A app.workers.celery_app worker --loglevel=info --concurrency=4`

**File**: `app/workers/celery_app.py`

```python
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "drift_detection_service",
    broker=settings.celery_broker_url,      # Redis DB 1
    backend=settings.celery_result_backend,  # Redis DB 2
    include=["app.workers.scan_worker"]      # Auto-discover tasks
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    task_time_limit=300,    # 5 minutes hard limit
    worker_prefetch_multiplier=1,  # Process 1 task at a time
)
```

**Tasks** (defined in `app/workers/scan_worker.py`):
- `scan_user_drift`: Execute drift detection for a user

**Command Breakdown**:
- `-A app.workers.celery_app` - Application module
- `worker` - Start a worker process
- `--loglevel=info` - Logging verbosity
- `--concurrency=4` - Run 4 worker processes

### 9.4 Consumer Entry Point

**Command**: `python -m app.consumer`

**File**: `app/consumer/__main__.py`

```python
from app.consumer.redis_consumer import main

if __name__ == "__main__":
    main()
```

**File**: `app/consumer/redis_consumer.py`

```python
class RedisConsumer:
    def __init__(self):
        self.stream_name = "behavior.events"
        self.consumer_group = "drift_detection_service"
        self.consumer_name = "consumer_1"
    
    def run(self):
        """Main event loop."""
        while self.running:
            # Read from Redis Stream
            messages = self.redis_client.xreadgroup(
                groupname=self.consumer_group,
                consumername=self.consumer_name,
                streams={self.stream_name: ">"},
                count=10,
                block=5000  # 5 second timeout
            )
            
            for message in messages:
                self.handler.handle(message)
                self.redis_client.xack(...)  # Acknowledge
```

**Purpose**: Continuously read behavior events from Redis Streams and update local snapshots.

---

## 10. Testing Infrastructure

### 10.1 Test Configuration

**File**: `pytest.ini`

```ini
[pytest]
# Test discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Output options
addopts = -v --tb=short --strict-markers -ra

# Async support
asyncio_mode = auto

# Markers
markers =
    unit: Unit tests (no external dependencies)
    integration: Integration tests (require database/Redis)
    slow: Slow tests (can be skipped in CI)
```

### 10.2 Test Structure

```
tests/
├── conftest.py              # Pytest fixtures
├── test_aggregator.py       # DriftAggregator tests
├── test_api.py              # API endpoint tests
├── test_detectors.py        # Detector algorithm tests
├── test_models.py           # Data model validation tests
└── test_utils.py            # Utility function tests
```

### 10.3 Running Tests

```bash
# Inside container
docker exec drift-api pytest -v

# With markers
docker exec drift-api pytest -v -m unit
docker exec drift-api pytest -v -m "not slow"

# Specific file
docker exec drift-api pytest tests/test_detectors.py -v

# With coverage
docker exec drift-api pytest --cov=app --cov-report=html
```

### 10.4 Test Fixtures (conftest.py)

```python
@pytest.fixture
def sample_snapshot():
    """Provide a sample BehaviorSnapshot for testing."""
    return BehaviorSnapshot(
        user_id="user_123",
        window_start=now_ms() - (60 * 24 * 60 * 60 * 1000),
        window_end=now_ms(),
        behaviors=[
            BehaviorRecord(
                behavior_id="b1",
                target="Python",
                intent="PREFERENCE",
                polarity="POSITIVE",
                credibility=0.9,
                reinforcement_count=5,
                state="ACTIVE",
                created_at=now_ms(),
                last_seen_at=now_ms()
            )
        ]
    )
```

---

## 11. Deployment Workflow

### 11.1 Complete Deployment Process

```
┌──────────────────────────────────────────────────────────┐
│          DEPLOYMENT WORKFLOW (Step-by-Step)              │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Step 1: Prerequisites                                   │
│  ──────────────────────────────────────────────────────  │
│  1. Install Docker + Docker Compose                      │
│  2. Clone repository                                     │
│  3. Have PostgreSQL database (Supabase or local)         │
│                                                          │
│  Step 2: Setup shared infrastructure                     │
│  ──────────────────────────────────────────────────────  │
│  $ docker network create shared-network                  │
│  $ docker run -d --name shared-redis \                   │
│      --network shared-network \                          │
│      -p 6379:6379 redis:7-alpine                         │
│                                                          │
│  Step 3: Configure environment                           │
│  ──────────────────────────────────────────────────────  │
│  $ make setup                                            │
│  $ vim .env    # Edit DATABASE_URL + settings            │
│                                                          │
│  Step 4: Build images                                    │
│  ──────────────────────────────────────────────────────  │
│  $ make build                                            │
│                                                          │
│  Step 5: Run database migrations                         │
│  ──────────────────────────────────────────────────────  │
│  $ make up                                               │
│  $ docker exec drift-api alembic upgrade head            │
│                                                          │
│  Step 6: Verify deployment                               │
│  ──────────────────────────────────────────────────────  │
│  $ make status                                           │
│  $ curl http://localhost:8000/api/v1/health              │
│                                                          │
│  Step 7: Monitor logs                                    │
│  ──────────────────────────────────────────────────────  │
│  $ make logs                                             │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 11.2 Quick Start Commands

```bash
# One-time setup
git clone <repo>
cd drift_detection_service
docker network create shared-network
docker run -d --name shared-redis --network shared-network redis:7-alpine
make setup
# Edit .env with DATABASE_URL

# Build and start
make build
make up
docker exec drift-api alembic upgrade head

# Verify
make status

# View logs
make logs
```

### 11.3 Production Deployment Checklist

- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Set `DEBUG=false`
- [ ] Configure `DATABASE_URL` with production database
- [ ] Set strong `SECRET_KEY` (if applicable)
- [ ] Configure resource limits in `docker-compose.yml`
- [ ] Set up reverse proxy (Nginx) for API
- [ ] Enable HTTPS with SSL certificates
- [ ] Configure log aggregation (e.g., ELK stack)
- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Configure backup strategy for PostgreSQL
- [ ] Enable Redis persistence (RDB or AOF)
- [ ] Scale workers based on load (`make scale-workers N=5`)

---

## 12. Build Optimization Techniques

### 12.1 Docker Layer Caching

**Principle**: Docker caches each layer. If a layer hasn't changed, it reuses the cached version.

**Optimization Strategy**:

```dockerfile
# ✓ GOOD: Install dependencies first (changes rarely)
COPY requirements.txt .
RUN pip install -r requirements.txt

# ✓ GOOD: Copy code last (changes often)
COPY . .

# ✗ BAD: Copy everything first
COPY . .
RUN pip install -r requirements.txt
```

**Result**: Changing code doesn't invalidate the pip install cache.

### 12.2 Multi-Stage Build Benefits

| Benefit | Explanation |
|---------|-------------|
| **Smaller Images** | Build tools (gcc, g++) not included in final image |
| **Security** | No compilation tools → smaller attack surface |
| **Modularity** | Separate build vs. runtime concerns |
| **Caching** | Builder stage cached independently |

### 12.3 Dependency Pinning

All dependencies use **exact versions** (not version ranges):

```
fastapi==0.110.0     # ✓ GOOD (exact version)
fastapi>=0.110.0     # ✗ BAD (may break with updates)
```

**Reason**: Ensures reproducible builds across environments.

### 12.4 ML Model Caching

```dockerfile
# Pre-download ML model during build
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('all-MiniLM-L6-v2')"
```

**Benefit**: Model (~80MB) downloaded once at build time, not at runtime.

### 12.5 .dockerignore File

Create a `.dockerignore` to exclude unnecessary files:

```
# Virtual environments
venv/
.venv/
env/

# Python artifacts
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/

# IDE
.vscode/
.idea/

# Git
.git/
.gitignore

# Documentation
*.md
docs/

# Test files
tests/

# Environment
.env
.env.example
```

**Benefit**: Reduces build context size, speeds up builds.

---

## 13. Network Architecture

### 13.1 Shared Network Design

```
┌──────────────────────────────────────────────────────────────────┐
│                     Docker Host                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              shared-network (external)                     │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │  │
│  │  │ shared-redis │  │  drift-api   │  │  drift-worker    │  │  │
│  │  │ (redis:7)    │  │              │  │                  │  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └───────┬──────────┘  │  │
│  │         │                 │                   │             │  │
│  │         └─────────────────┴───────────────────┘             │  │
│  │                                                             │  │
│  │  ┌──────────────────┐                                      │  │
│  │  │ drift-consumer   │                                      │  │
│  │  │                  │                                      │  │
│  │  └───────┬──────────┘                                      │  │
│  │          │                                                 │  │
│  │          └─────────────────────────────────────────────────┘  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Port Mapping:                                                   │
│  ┌──────────────────────┐                                       │
│  │ 8000:8000 → drift-api │  (Host → Container)                 │
│  │ 6379:6379 → shared-redis │                                   │
│  └──────────────────────┘                                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 13.2 Why Shared Network?

**Problem**: Multiple microservices need to communicate via Redis.

**Solution**: Use a single external Docker network that all services join.

**Benefits**:
1. **Service Discovery**: Containers can reach each other by name (`shared-redis`)
2. **Scalability**: Add more services to same network
3. **Isolation**: Services on different networks can't communicate
4. **Simplicity**: No complex networking configuration

### 13.3 DNS Resolution in Docker

Inside the `shared-network`, Docker provides automatic DNS:

```python
# In application code
redis_url = "redis://shared-redis:6379/0"
```

Docker resolves `shared-redis` to the container's IP automatically.

### 13.4 Creating the Network

```bash
# Create network (one-time setup)
docker network create shared-network

# Verify
docker network ls

# Inspect
docker network inspect shared-network
```

### 13.5 Redis Database Separation

Redis has 16 databases (0-15). The system uses 3:

| DB | Purpose | Used By |
|----|---------|---------|
| **0** | Redis Streams (behavior.events, drift.events) | API, Consumer, Worker |
| **1** | Celery Broker (task queue) | API, Worker |
| **2** | Celery Result Backend (task results) | API, Worker |

**Syntax**: `redis://host:port/database`

Example:
- `redis://shared-redis:6379/0` → DB 0
- `redis://shared-redis:6379/1` → DB 1

---

## 14. Environment Variables Reference

### 14.1 Complete Environment Variable List

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| **Application** | | | |
| `ENVIRONMENT` | `development` | No | `development`, `production` |
| `DEBUG` | `true` | No | Enable debug mode |
| `LOG_LEVEL` | `INFO` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| **Database** | | | |
| `DATABASE_URL` | - | **Yes** | PostgreSQL connection string |
| `DB_POOL_SIZE` | `10` | No | Connection pool size |
| `DB_MAX_OVERFLOW` | `20` | No | Max overflow connections |
| **Redis** | | | |
| `REDIS_URL` | `redis://localhost:6379/0` | No | Redis connection URL |
| `REDIS_STREAM_BEHAVIOR_EVENTS` | `behavior.events` | No | Behavior event stream name |
| `REDIS_STREAM_DRIFT_EVENTS` | `drift.events` | No | Drift event stream name |
| `REDIS_CONSUMER_GROUP` | `drift_detection_service` | No | Consumer group name |
| `REDIS_CONSUMER_NAME` | `detector_1` | No | Consumer name |
| `REDIS_BLOCK_MS` | `5000` | No | Stream read timeout (ms) |
| `REDIS_MAX_EVENTS_PER_READ` | `10` | No | Max events per read |
| **Celery** | | | |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | No | Celery broker URL |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | No | Result backend URL |
| `CELERY_TASK_TIME_LIMIT` | `300` | No | Hard task timeout (seconds) |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | No | Task prefetch count |
| **Drift Detection** | | | |
| `DRIFT_SCORE_THRESHOLD` | `0.6` | No | Minimum drift score to create event |
| `MIN_BEHAVIORS_FOR_DRIFT` | `5` | No | Minimum behaviors required |
| `MIN_DAYS_OF_HISTORY` | `14` | No | Minimum days of user history |
| `SCAN_COOLDOWN_SECONDS` | `3600` | No | Cooldown between scans (1 hour) |
| `REFERENCE_WINDOW_DAYS` | `30` | No | Reference window size (days) |
| `REFERENCE_OFFSET_DAYS` | `30` | No | Reference window offset (days ago) |
| `CURRENT_WINDOW_DAYS` | `30` | No | Current window size (days) |
| **Scheduling** | | | |
| `ACTIVE_USER_SCAN_INTERVAL_HOURS` | `24` | No | Active user scan interval |
| `MODERATE_USER_SCAN_INTERVAL_HOURS` | `72` | No | Moderate user scan interval |
| `ACTIVE_USER_DAYS_THRESHOLD` | `7` | No | Days to consider "active" |
| `MODERATE_USER_DAYS_THRESHOLD` | `30` | No | Days to consider "moderate" |

### 14.2 Example .env File

```bash
# ═══════════════════════════════════════════════════════════════
# Drift Detection Service - Environment Configuration
# ═══════════════════════════════════════════════════════════════

# ─── Application ───────────────────────────────────────────────
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# ─── Database ──────────────────────────────────────────────────
DATABASE_URL=postgresql://user:password@db.example.com:5432/drift_db

# ─── Redis (Docker) ────────────────────────────────────────────
REDIS_URL=redis://shared-redis:6379/0
CELERY_BROKER_URL=redis://shared-redis:6379/1
CELERY_RESULT_BACKEND=redis://shared-redis:6379/2

# ─── Drift Detection ───────────────────────────────────────────
MIN_BEHAVIORS_FOR_DRIFT=5
MIN_DAYS_OF_HISTORY=14
SCAN_COOLDOWN_SECONDS=3600
DRIFT_SCORE_THRESHOLD=0.6

# ─── Scheduling ────────────────────────────────────────────────
ACTIVE_USER_SCAN_INTERVAL_HOURS=24
MODERATE_USER_SCAN_INTERVAL_HOURS=72
```

---

## 15. Build Troubleshooting

### 15.1 Common Build Issues

#### Issue 1: Docker Compose Can't Find Network

```
ERROR: Network shared-network declared as external, but could not be found
```

**Solution**:
```bash
docker network create shared-network
```

#### Issue 2: Can't Connect to shared-redis

```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solution**: Ensure `shared-redis` is running:
```bash
docker run -d --name shared-redis --network shared-network redis:7-alpine
```

#### Issue 3: Docker Compose Uses Wrong .env

**Problem**: Docker Compose loads `.env` from current directory.

**Solution**: Ensure you're in project root when running `docker-compose`.

#### Issue 4: Database Migration Fails

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**: Verify `DATABASE_URL` in `.env`:
```bash
# Test connection
docker exec drift-api python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')"
```

#### Issue 5: ML Model Download Fails During Build

```
urllib.error.URLError: <urlopen error [Errno 111] Connection refused>
```

**Solution**: Build requires internet access. If behind proxy, configure Docker proxy.

### 15.2 Debug Commands

```bash
# Check if containers are running
docker ps

# Check container logs
docker logs drift-api
docker logs drift-worker
docker logs drift-consumer

# Check container health
docker inspect drift-api | grep -A 10 Health

# Check network connectivity
docker exec drift-api ping shared-redis

# Check Redis connectivity
docker exec drift-api redis-cli -h shared-redis ping

# Check database connectivity
docker exec drift-api python -c "import psycopg2; psycopg2.connect('$DATABASE_URL')"

# Enter container shell
docker exec -it drift-api bash

# View environment variables
docker exec drift-api env
```

### 15.3 Performance Troubleshooting

```bash
# Check resource usage
docker stats

# Check worker status
docker exec drift-worker celery -A app.workers.celery_app inspect active

# Check Redis memory
docker exec shared-redis redis-cli info memory

# Check PostgreSQL connections
docker exec drift-api python -c "from app.db.connection import get_pool_stats; print(get_pool_stats())"
```

---

## Appendix A: Complete Build Command Reference

### Docker Commands

```bash
# Build image
docker build -t drift-detection .

# Build without cache
docker build --no-cache -t drift-detection .

# Run image manually
docker run -p 8000:8000 drift-detection

# Stop all containers
docker stop $(docker ps -q)

# Remove all containers
docker rm $(docker ps -aq)

# Remove all images
docker rmi $(docker images -q)
```

### Docker Compose Commands

```bash
# Build images
docker-compose build

# Build without cache
docker-compose build --no-cache

# Start services
docker-compose up -d

# Start specific service
docker-compose up -d api

# Stop services
docker-compose stop

# Stop and remove
docker-compose down

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f api

# Scale workers
docker-compose up -d --scale worker=3

# Restart service
docker-compose restart api
```

### Makefile Commands

```bash
make help              # Show all commands
make setup             # Create .env
make build             # Build images
make rebuild           # Build without cache
make up                # Start services
make down              # Stop services
make restart           # Restart all
make logs              # View all logs
make logs-api          # View API logs
make logs-worker       # View worker logs
make logs-consumer     # View consumer logs
make status            # Check health
make shell             # Open API shell
make test              # Run tests
make clean             # Remove containers
make clean-all         # Remove everything
```

---

## Appendix B: System Dataflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE SYSTEM DATAFLOW                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  External Source                                                        │
│  ┌──────────────────┐                                                   │
│  │ Behavior Service │                                                   │
│  └────────┬─────────┘                                                   │
│           │ Publishes behavior events                                   │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │   Redis Streams  │                                                   │
│  │ behavior.events  │                                                   │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           │ Consumed by                                                 │
│           ▼                                                             │
│  ┌──────────────────────┐                                              │
│  │  drift-consumer       │                                              │
│  │  (Redis Consumer)     │                                              │
│  └────────┬──────────────┘                                              │
│           │                                                             │
│           │ Updates snapshots                                           │
│           ▼                                                             │
│  ┌──────────────────────────────┐                                      │
│  │ PostgreSQL                   │                                      │
│  │ - behavior_snapshots         │                                      │
│  │ - conflict_snapshots         │                                      │
│  │ - drift_scan_jobs            │                                      │
│  └──────────┬───────────────────┘                                      │
│             │                                                           │
│             │ Read by                                                   │
│             ▼                                                           │
│  ┌──────────────────────────────┐                                      │
│  │  drift-api (APScheduler)     │                                      │
│  │  Periodic user scans         │                                      │
│  └────────┬─────────────────────┘                                      │
│           │                                                             │
│           │ Enqueues scan jobs                                          │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │  Celery Broker   │                                                   │
│  │  (Redis DB 1)    │                                                   │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           │ Consumed by                                                 │
│           ▼                                                             │
│  ┌──────────────────────┐                                              │
│  │  drift-worker         │                                              │
│  │  (Celery Worker)      │                                              │
│  └────────┬──────────────┘                                              │
│           │                                                             │
│           │ Executes drift detection                                    │
│           ▼                                                             │
│  ┌──────────────────────────────────────┐                              │
│  │  DriftDetector Pipeline:             │                              │
│  │  1. Build snapshots                  │                              │
│  │  2. Run 5 detectors                  │                              │
│  │  3. Aggregate signals                │                              │
│  │  4. Create drift events              │                              │
│  └────────┬─────────────────────────────┘                              │
│           │                                                             │
│           │ Writes results                                              │
│           ▼                                                             │
│  ┌──────────────────────────────┐                                      │
│  │ PostgreSQL                   │                                      │
│  │ - drift_events               │                                      │
│  └──────────┬───────────────────┘                                      │
│             │                                                           │
│             │ Publishes to                                              │
│             ▼                                                           │
│  ┌──────────────────┐                                                   │
│  │  Redis Streams   │                                                   │
│  │  drift.events    │                                                   │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           │ Consumed by                                                 │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ Downstream       │                                                   │
│  │ Services         │                                                   │
│  └──────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix C: Build System Cheat Sheet

### Quick Reference Table

| Task | Command |
|------|---------|
| **Initial Setup** | |
| Create .env | `make setup` |
| Create network | `docker network create shared-network` |
| Start Redis | `docker run -d --name shared-redis --network shared-network redis:7-alpine` |
| **Build & Deploy** | |
| Build images | `make build` |
| Start services | `make up` |
| Run migrations | `docker exec drift-api alembic upgrade head` |
| Check health | `make status` |
| **Development** | |
| View logs | `make logs` |
| Open shell | `make shell` |
| Run tests | `make test` |
| Restart services | `make restart` |
| **Production** | |
| Scale workers | `make scale-workers N=5` |
| Check worker health | `make worker-ping` |
| View active tasks | `make worker-active` |
| **Cleanup** | |
| Stop services | `make down` |
| Remove all | `make clean-all` |

---

## Conclusion

This document provides a complete, LLM-optimized explanation of the Drift Detection Service build system. Any AI model should now understand:

1. ✅ **Multi-stage Docker build** (builder + runtime stages)
2. ✅ **Docker Compose orchestration** (3 services, shared network)
3. ✅ **Makefile automation** (user-friendly commands)
4. ✅ **Dependency management** (requirements.txt, ML model caching)
5. ✅ **Database migrations** (Alembic schema versioning)
6. ✅ **Configuration system** (Pydantic Settings, environment variables)
7. ✅ **Service entry points** (API, Worker, Consumer)
8. ✅ **Test infrastructure** (pytest, markers, fixtures)
9. ✅ **Deployment workflow** (setup → build → migrate → deploy)
10. ✅ **Network architecture** (shared-network, DNS resolution)
11. ✅ **Build optimizations** (layer caching, multi-stage, pinned deps)
12. ✅ **Troubleshooting** (common issues, debug commands)

**Key Insight**: The entire system is built on a **single Docker image** with **three different entry points**, orchestrated by **Docker Compose**, and managed via a **Makefile** for simplicity. This architecture provides **scalability**, **maintainability**, and **reproducibility**.
