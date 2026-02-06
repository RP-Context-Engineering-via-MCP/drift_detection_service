# Drift Detection Service

A microservice for detecting and managing behavioral drift in user preferences over time. Implements temporal decay and accumulation-based drift detection.

## 🎯 Overview

This service is part of a larger behavior tracking system. It receives canonicalized behaviors from an Extraction Service and maintains a stateful representation of user behaviors, accounting for:

- **Temporal Decay**: Behaviors lose credibility over time if not reinforced
- **Drift Accumulation**: Repeated weak signals can override strong but stale behaviors
- **Semantic Conflict Resolution**: Uses vector similarity to identify related behaviors

## 🏗️ Architecture

### Microservice Pattern
- **Stateless Extraction Service** → Canonical Behaviors → **This Service (Stateful)**
- Clean separation between NLI/extraction and state management
- Database-backed with PostgreSQL + pgvector

### Core Components

```
┌─────────────────────────────────────────────────────┐
│            Process Behavior Request                 │
│  {user_id, timestamp, candidates[]}                 │
└────────────────┬────────────────────────────────────┘
                 │
         ┌───────▼───────┐
         │  Resolution   │
         │    Engine     │
         └───┬───────┬───┘
             │       │
    ┌────────▼──┐ ┌─▼──────────┐
    │  Drift    │ │ Semantic   │
    │ Detector  │ │  Search    │
    └───────────┘ └────────────┘
             │
      ┌──────▼───────┐
      │  PostgreSQL  │
      │  + pgvector  │
      └──────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Supabase account (free tier works fine)

### Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd drift_detection_service

# 2. Create virtual environment
python -m venv venv
source venv/Scripts/activate  # On Windows Git Bash
# Or: venv\Scripts\activate  # On Windows CMD/PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up Supabase
# - Create a new project at https://supabase.com
# - Go to Project Settings > Database
# - Copy the connection string (URI format)
# - Enable pgvector extension:
#   Go to SQL Editor and run: CREATE EXTENSION IF NOT EXISTS vector;

# 5. Create environment file
cp .env.example .env
# Edit .env and paste your Supabase connection string:
# DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres

# 6. Run the service (tables will be created automatically)
uvicorn app.main:app --reload --port 8001
```

### Verify Installation

```bash
# Check health
curl http://localhost:8001/api/v1/health

# View API documentation
# Open browser: http://localhost:8001/docs
```

## 📡 API Endpoints

### Health Check
```bash
GET /api/v1/health
```

### Process Behaviors
```bash
POST /api/v1/behaviors/process
Content-Type: application/json

{
  "user_id": "user_123",
  "timestamp": "2026-02-03T10:00:00Z",
  "candidates": [
    {
      "intent": "PREFERENCE",
      "target": "go language",
      "context": "backend development",
      "polarity": "POSITIVE",
      "extracted_credibility": 0.85,
      "embedding": [0.123, 0.456, ...]  // 3072-dim vector
    }
  ]
}
```

**Response:**
```json
{
  "status": "PROCESSED",
  "actions_taken": [
    {
      "type": "SUPERSEDE",
      "reason": "New credibility (0.85) exceeded decayed existing (0.35)",
      "details": "Drift type: TARGET_SHIFT. Behavior is stale: last seen 365 days ago",
      "old_behavior_id": "uuid-1",
      "new_behavior_id": "uuid-2",
      "drift_detected": true,
      "effective_credibility": 0.35
    }
  ],
  "processed_count": 1,
  "timestamp": "2026-02-03T10:00:05Z"
}
```

### Get User Behaviors
```bash
GET /api/v1/behaviors/user/{user_id}?state=ACTIVE&limit=50
```

## 🧠 Drift Detection Logic

### 1. Temporal Decay
Behaviors lose credibility over time using exponential decay:

```
effective_credibility = stored_credibility × (0.5)^(days_passed / half_life)
```

- **Default Half-Life**: 180 days (configurable)
- A behavior with 0.9 credibility after 1 year → 0.45 effective credibility
- After 2 years → 0.225 effective credibility

### 2. Drift Accumulation
Tracks rejected change attempts. If a user tries to change a behavior **3+ times in 30 days**, the system:
1. Recognizes persistent intent
2. Overrides credibility-based blocking
3. Forces a `SUPERSEDE` action

### 3. Resolution Actions

| Action | Trigger | Example |
|--------|---------|---------|
| **SUPERSEDE** | New credibility > Effective old credibility OR Drift accumulation | "Python" (old, stale) → "Go" (new, fresh) |
| **REINFORCE** | Identical behavior observed again | "I like Python" said twice |
| **INSERT** | No semantic conflict found | First time expressing preference |
| **IGNORE** | New weaker than existing (logged for drift) | Weak "try Go" vs strong "love Python" |

## ⚙️ Configuration

Key environment variables in `.env`:

```bash
# Database (Supabase)
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres

# Vector Embeddings
# Note: Supabase pgvector limits indexes to 2000 dimensions
# Recommended: Use 1536-dim embeddings (OpenAI text-embedding-ada-002)
EMBEDDING_DIMENSION=1536

# Drift Parameters
DECAY_HALF_LIFE_DAYS=180        # How quickly behaviors decay
DRIFT_SIGNAL_THRESHOLD=3        # Attempts needed to trigger drift
DRIFT_SIGNAL_WINDOW_DAYS=30     # Time window for counting attempts
SEMANTIC_GATE_THRESHOLD=0.55    # Vector distance threshold
```

## 🗄️ Database Schema

### `behaviors` Table
- Stores active and superseded behaviors
- Includes vector embeddings for semantic search
- Tracks temporal metadata (`last_seen_at`, `credibility`)

### `drift_signals` Table
- Logs rejected behavior change attempts
- Enables drift accumulation detection
- Links to existing behaviors via foreign key

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_drift_detector.py
```

## 📊 Monitoring

### Health Endpoints
- `/api/v1/health` - Basic health check
- `/api/v1/health/ready` - Readiness probe

### Logging
- JSON-formatted logs in production
- Human-readable logs in development
- Configurable log levels via `LOG_LEVEL` env var

## 🔒 Security Considerations

- Database credentials via environment variables
- Input validation using Pydantic schemas
- SQL injection protection via SQLAlchemy ORM
- CORS configured via `ALLOWED_ORIGINS`

## 🚢 Deployment

### Production Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables for production

3. Initialize database:
```bash
python scripts/init_db.py init
```

4. Run with production WSGI server:
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

## 📈 Performance

- **Vector Search**: Optimized with pgvector IVFFlat index
- **Database Connection Pooling**: Configurable pool size
- **Async Operations**: FastAPI async endpoints

## 🤝 Integration

### Upstream: Extraction Service
Sends canonical behaviors with embeddings.

### Downstream: Analytics/Frontend
Query user behavior history and drift patterns.

## 📝 License

[Your License Here]

## 👥 Contributors

[Your Team/Name]

## 📞 Support

For issues and questions, please open a GitHub issue or contact [your-email].
