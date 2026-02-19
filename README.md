# Drift Detection Service

A microservice for detecting behavioral drift in user preference patterns. Part of a larger AI-driven adaptive system for personalizing user experiences.

## Overview

The Drift Detection Service analyzes user behavior patterns over time to identify significant changes (drift) in preferences, interests, and engagement. It processes behavior events from a message broker, maintains local snapshots of user behaviors, and runs detection algorithms to identify various types of drift.

### Drift Types Detected

| Drift Type | Description |
|------------|-------------|
| **TOPIC_EMERGENCE** | New topics appearing with significant activity |
| **TOPIC_ABANDONMENT** | Previously active topics going silent |
| **PREFERENCE_REVERSAL** | Polarity changes (positive ↔ negative sentiment) |
| **INTENSITY_SHIFT** | Changes in credibility/conviction strength |
| **CONTEXT_EXPANSION** | Specific context → general application |
| **CONTEXT_CONTRACTION** | General → specific context usage |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Drift Detection Service                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐  │
│  │   FastAPI    │    │   Celery     │    │      APScheduler         │  │
│  │   REST API   │    │   Workers    │    │     (Cron Jobs)          │  │
│  └──────┬───────┘    └──────┬───────┘    └───────────┬──────────────┘  │
│         │                   │                        │                  │
│         └───────────────────┴────────────────────────┘                  │
│                             │                                           │
│                    ┌────────┴────────┐                                  │
│                    │  Core Pipeline  │                                  │
│                    │                 │                                  │
│                    │ ┌─────────────┐ │                                  │
│                    │ │  Snapshot   │ │                                  │
│                    │ │  Builder    │ │                                  │
│                    │ └──────┬──────┘ │                                  │
│                    │        ↓        │                                  │
│                    │ ┌─────────────┐ │                                  │
│                    │ │  Detectors  │ │                                  │
│                    │ │  (5 types)  │ │                                  │
│                    │ └──────┬──────┘ │                                  │
│                    │        ↓        │                                  │
│                    │ ┌─────────────┐ │                                  │
│                    │ │ Aggregator  │ │                                  │
│                    │ └─────────────┘ │                                  │
│                    └─────────────────┘                                  │
│                             │                                           │
│         ┌───────────────────┼───────────────────┐                       │
│         ↓                   ↓                   ↓                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │  PostgreSQL │    │   Redis     │    │   Redis     │                 │
│  │  (Supabase) │    │  Streams    │    │   Broker    │                 │
│  └─────────────┘    └─────────────┘    └─────────────┘                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

- **Python 3.11+** - Runtime
- **FastAPI** - REST API framework
- **Celery** - Distributed task queue
- **APScheduler** - Cron-style job scheduling
- **PostgreSQL/Supabase** - Primary database
- **Redis** - Message broker & streams
- **Pydantic** - Data validation
- **sentence-transformers** - Topic embeddings (ML)

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL database (or Supabase account)

### Local Development

1. **Clone and setup environment**
   ```bash
   git clone <repository-url>
   cd drift_detection_service
   python -m venv venv
   source venv/Scripts/activate  # Windows
   # source venv/bin/activate    # Linux/Mac
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database URL and settings
   ```

3. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

4. **Start services with Docker Compose**
   ```bash
   docker-compose up -d
   ```

5. **Start the API (development)**
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```

6. **Start Celery worker**
   ```bash
   celery -A app.workers.celery_app worker --loglevel=info
   ```

### Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## Configuration

Configuration is managed via environment variables. See [app/config.py](app/config.py) for all options.

### Key Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `DRIFT_SCORE_THRESHOLD` | Minimum score to create event | `0.6` |
| `MIN_BEHAVIORS_FOR_DRIFT` | Minimum behaviors for detection | `5` |
| `SCAN_COOLDOWN_SECONDS` | Cooldown between user scans | `3600` |
| `CURRENT_WINDOW_DAYS` | Size of current analysis window | `30` |

## API Endpoints

### Health Check
```http
GET /api/v1/health
```

### Detect Drift
```http
POST /api/v1/detect/{user_id}?force=false
```

### Get Drift Events
```http
GET /api/v1/events/{user_id}?drift_type=TOPIC_EMERGENCE&severity=STRONG_DRIFT&limit=50
```

### Acknowledge Event
```http
POST /api/v1/events/{drift_event_id}/acknowledge
```

### API Documentation

When running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
drift_detection_service/
├── api/                      # REST API layer
│   ├── main.py              # FastAPI application
│   ├── routes.py            # API endpoints
│   ├── models.py            # Request/response models
│   ├── dependencies.py      # Dependency injection
│   └── errors.py            # Custom exceptions
├── app/
│   ├── config.py            # Configuration management
│   ├── core/                # Core business logic
│   │   ├── drift_detector.py    # Main orchestrator
│   │   ├── drift_aggregator.py  # Signal aggregation
│   │   └── snapshot_builder.py  # Behavior snapshots
│   ├── detectors/           # Drift detection algorithms
│   │   ├── base.py              # Abstract base class
│   │   ├── topic_emergence.py
│   │   ├── topic_abandonment.py
│   │   ├── preference_reversal.py
│   │   ├── intensity_shift.py
│   │   └── context_shift.py
│   ├── models/              # Domain models
│   │   ├── behavior.py
│   │   ├── drift.py
│   │   └── snapshot.py
│   ├── db/                  # Data access layer
│   │   ├── connection.py
│   │   └── repositories/
│   ├── consumer/            # Redis stream consumers
│   ├── pipeline/            # Event processing pipeline
│   ├── workers/             # Celery tasks
│   ├── scheduler/           # APScheduler jobs
│   └── utils/               # Shared utilities
├── migrations/              # Alembic migrations
├── tests/                   # Unit & integration tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=api

# Run specific test file
pytest tests/test_detectors.py

# Run only unit tests
pytest -m unit
```

## Database Migrations

Using Alembic for schema management:

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Run migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Development

### Adding a New Detector

1. Create a new file in `app/detectors/`
2. Extend `BaseDetector` class
3. Implement the `detect()` method
4. Add to detector list in `DriftDetector._create_default_detectors()`

```python
from app.detectors.base import BaseDetector
from app.models.drift import DriftSignal, DriftType

class MyNewDetector(BaseDetector):
    def detect(self, reference, current) -> List[DriftSignal]:
        signals = []
        # Your detection logic here
        return signals
```

### Code Style

- Use type hints
- Write docstrings for all public functions
- Follow PEP 8 conventions
- Run `black` for formatting
- Run `mypy` for type checking

## Monitoring

### Health Checks

- API: `GET /api/v1/health`
- Celery: `celery -A app.workers.celery_app inspect ping`

### Logs

Structured JSON logging is configured. Key log fields:
- `user_id`
- `drift_type`
- `drift_score`
- `execution_time_seconds`

## License

[Your License Here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests
4. Submit a pull request
