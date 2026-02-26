# Drift Detection Service - Comprehensive System Analysis

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Architecture](#3-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Core Components](#5-core-components)
6. [Data Models](#6-data-models)
7. [Database Schema](#7-database-schema)
8. [API Layer](#8-api-layer)
9. [Drift Detection Pipeline](#9-drift-detection-pipeline)
10. [Detectors](#10-detectors)
11. [Message Processing](#11-message-processing)
12. [Background Workers](#12-background-workers)
13. [Scheduling System](#13-scheduling-system)
14. [Configuration Management](#14-configuration-management)
15. [Error Handling](#15-error-handling)
16. [Testing Strategy](#16-testing-strategy)
17. [Deployment](#17-deployment)
18. [Data Flow Diagrams](#18-data-flow-diagrams)
19. [Security Considerations](#19-security-considerations)
20. [Performance Considerations](#20-performance-considerations)

---

## 1. Executive Summary

The **Drift Detection Service** is a microservice designed to analyze behavioral drift in user preference patterns. It is part of a larger AI-driven adaptive system for personalizing user experiences.

### Key Capabilities

- **Real-time Event Processing**: Consumes behavior events from Redis Streams
- **Temporal Analysis**: Compares reference (historical) and current behavior windows
- **Multi-dimensional Detection**: Implements 5 specialized drift detection algorithms
- **Scheduled Scanning**: Periodic user scanning based on activity tiers
- **REST API**: Exposes endpoints for drift detection and event retrieval

### Drift Types Detected

| Drift Type | Description |
|------------|-------------|
| **TOPIC_EMERGENCE** | New topics appearing with significant activity |
| **TOPIC_ABANDONMENT** | Previously active topics going silent |
| **PREFERENCE_REVERSAL** | Polarity changes (positive ↔ negative sentiment) |
| **INTENSITY_SHIFT** | Changes in credibility/conviction strength |
| **CONTEXT_EXPANSION** | Specific context → general application |
| **CONTEXT_CONTRACTION** | General → specific context usage |

---

## 2. System Overview

### Purpose

The service detects significant changes (drift) in user behavior patterns over time by:

1. Maintaining local projections (snapshots) of user behaviors
2. Building temporal windows for comparison
3. Running multiple detection algorithms
4. Aggregating and deduplicating signals
5. Persisting and publishing drift events

### Position in Ecosystem

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Upstream Services                            │
│    ┌─────────────────┐     ┌─────────────────┐                      │
│    │ Behavior Service │     │ Conflict Service │                     │
│    └────────┬────────┘     └────────┬────────┘                      │
│             │                       │                                │
│             └──────────┬────────────┘                                │
│                        ▼                                             │
│              ┌─────────────────┐                                     │
│              │  Redis Streams  │                                     │
│              │ behavior.events │                                     │
│              └────────┬────────┘                                     │
│                       ▼                                              │
│    ┌────────────────────────────────────────────────┐               │
│    │         DRIFT DETECTION SERVICE                │               │
│    │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │               │
│    │  │ Consumer │  │   API    │  │ Workers  │     │               │
│    │  └──────────┘  └──────────┘  └──────────┘     │               │
│    └────────────────────────────────────────────────┘               │
│                       │                                              │
│                       ▼                                              │
│              ┌─────────────────┐                                     │
│              │  Redis Streams  │                                     │
│              │  drift.events   │                                     │
│              └────────┬────────┘                                     │
│                       ▼                                              │
│              ┌─────────────────┐                                     │
│              │ Downstream      │                                     │
│              │ Services        │                                     │
│              └─────────────────┘                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Architecture

### High-Level Architecture

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

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **FastAPI REST API** | HTTP endpoints for drift detection, event retrieval |
| **Redis Consumer** | Consumes behavior events from streams, updates snapshots |
| **Celery Workers** | Executes drift scan jobs asynchronously |
| **APScheduler** | Periodic user scanning, dead letter cleanup |
| **Drift Detector** | Orchestrates the detection pipeline |
| **Snapshot Builder** | Builds temporal behavior windows |
| **Detectors** | Algorithm implementations for each drift type |
| **Aggregator** | Deduplicates and filters signals |

---

## 4. Technology Stack

### Core Technologies

| Category | Technology | Version | Purpose |
|----------|------------|---------|---------|
| **Runtime** | Python | 3.11+ | Core language |
| **Web Framework** | FastAPI | 0.110.0 | REST API |
| **Task Queue** | Celery | 5.4.0 | Background processing |
| **Scheduler** | APScheduler | 3.10.4 | Cron-style jobs |
| **Database** | PostgreSQL/Supabase | - | Primary storage |
| **Message Broker** | Redis | 5.0.1 | Streams & task queue |
| **ML/Embeddings** | sentence-transformers | 2.7.0 | Topic clustering |

### Supporting Libraries

| Library | Purpose |
|---------|---------|
| **pydantic** | Data validation and settings |
| **asyncpg** | Async PostgreSQL driver |
| **psycopg2** | Sync PostgreSQL driver |
| **numpy** | Numerical computations |
| **scikit-learn** | DBSCAN clustering |
| **uvicorn** | ASGI server |

---

## 5. Core Components

### 5.1 DriftDetector (Orchestrator)

**Location**: `app/core/drift_detector.py`

The main orchestrator that coordinates the entire drift detection pipeline.

```python
class DriftDetector:
    """
    Main orchestrator for drift detection pipeline.
    
    Coordinates snapshot building, detector execution, signal aggregation,
    and event persistence.
    """
    
    def detect_drift(self, user_id: str) -> List[DriftEvent]:
        """
        Pipeline:
        1. Pre-flight checks (sufficient data, cooldown period)
        2. Build reference and current snapshots
        3. Run all detectors
        4. Aggregate and deduplicate signals
        5. Convert to events
        6. Persist to database
        """
```

**Key Features**:
- Dependency injection for testing flexibility
- Configurable detector set
- Pre-flight validation (data sufficiency, cooldown)
- Error resilience (continues if individual detectors fail)

### 5.2 SnapshotBuilder

**Location**: `app/core/snapshot_builder.py`

Constructs `BehaviorSnapshot` objects from database records for specific time windows.

```python
class SnapshotBuilder:
    """Constructs BehaviorSnapshot objects from database queries."""
    
    def build_reference_and_current(self, user_id: str) -> tuple[BehaviorSnapshot, BehaviorSnapshot]:
        """
        Build reference and current snapshots based on configuration.
        
        Reference window: [now - reference_window_start_days, now - reference_window_end_days]
        Current window: [now - current_window_days, now]
        """
```

**Window Configuration**:
- **Current Window**: Last 30 days (configurable)
- **Reference Window**: 60-30 days ago (configurable)
- **Reference**: Includes superseded behaviors for historical accuracy
- **Current**: Active behaviors only

### 5.3 DriftAggregator

**Location**: `app/core/drift_aggregator.py`

Deduplicates and filters drift signals from all detectors.

```python
class DriftAggregator:
    """Deduplicates and filters drift signals."""
    
    def aggregate(self, signals: List[DriftSignal]) -> List[DriftSignal]:
        """
        Strategy:
        1. Group signals by affected targets
        2. Keep only the highest-scoring signal per target
        3. Filter out signals below threshold
        4. Sort by drift_score descending
        """
```

**Aggregation Logic**:
- Groups by affected targets
- Keeps highest-scoring signal per target
- Filters by configurable threshold (default: 0.6)
- Returns sorted by drift score

---

## 6. Data Models

### 6.1 BehaviorRecord

**Location**: `app/models/behavior.py`

Local projection of a behavior from the upstream Behavior Service.

```python
@dataclass
class BehaviorRecord:
    user_id: str
    behavior_id: str
    target: str              # Topic/subject (e.g., "python", "react")
    intent: str              # PREFERENCE | CONSTRAINT | HABIT | SKILL | COMMUNICATION
    context: str             # backend | frontend | general | IDE | ...
    polarity: str            # POSITIVE | NEGATIVE
    credibility: float       # 0.0 – 1.0
    reinforcement_count: int # Number of times behavior was reinforced
    state: str               # ACTIVE | SUPERSEDED
    created_at: int          # Unix timestamp
    last_seen_at: int        # Unix timestamp
    snapshot_updated_at: int # When last updated by an event
```

### 6.2 ConflictRecord

**Location**: `app/models/behavior.py`

Local projection of resolved conflicts from the upstream Conflict Service.

```python
@dataclass
class ConflictRecord:
    user_id: str
    conflict_id: str
    behavior_id_1: str
    behavior_id_2: str
    conflict_type: str       # POLARITY_CONFLICT | TARGET_CONFLICT | CONTEXT_CONFLICT
    resolution_status: str   # AUTO_RESOLVED | PENDING | USER_RESOLVED | UNRESOLVED
    old_polarity: Optional[str]
    new_polarity: Optional[str]
    old_target: Optional[str]
    new_target: Optional[str]
    created_at: int
```

### 6.3 BehaviorSnapshot

**Location**: `app/models/snapshot.py`

Represents a user's complete behavior profile within a specific time window.

```python
@dataclass
class BehaviorSnapshot:
    user_id: str
    window_start: datetime
    window_end: datetime
    behaviors: List[BehaviorRecord]
    conflict_records: List[ConflictRecord]
    include_superseded: bool  # True for reference/historical windows
    
    # Computed properties (lazy-loaded)
    @property
    def topic_distribution(self) -> Dict[str, float]
    
    @property
    def intent_distribution(self) -> Dict[str, float]
    
    @property
    def polarity_by_target(self) -> Dict[str, str]
```

**Helper Methods**:
- `get_behaviors_by_target(target)` - Filter by target
- `get_reinforcement_count(target)` - Sum reinforcements
- `get_targets()` - Set of unique targets
- `get_contexts_for_target(target)` - Contexts used
- `get_average_credibility(target)` - Mean credibility
- `has_target(target)` - Existence check

### 6.4 DriftSignal

**Location**: `app/models/drift.py`

Output from a single detector module.

```python
@dataclass
class DriftSignal:
    drift_type: DriftType
    drift_score: float        # 0.0 (no drift) → 1.0 (strong drift)
    affected_targets: List[str]
    evidence: Dict[str, Any]  # Raw data that triggered this signal
    confidence: float         # 0.0-1.0
    
    @property
    def severity(self) -> DriftSeverity:
        """
        Score >= 0.8: STRONG_DRIFT
        Score 0.6-0.8: MODERATE_DRIFT
        Score 0.3-0.6: WEAK_DRIFT
        Score < 0.3: NO_DRIFT
        """
    
    @property
    def is_actionable(self) -> bool:
        """True if MODERATE or STRONG severity"""
```

### 6.5 DriftEvent

**Location**: `app/models/drift.py`

Drift event persisted to the database.

```python
@dataclass
class DriftEvent:
    drift_event_id: str
    user_id: str
    drift_type: DriftType
    drift_score: float
    severity: DriftSeverity
    affected_targets: List[str]
    evidence: Dict[str, Any]
    confidence: float
    
    # Time windows
    reference_window_start: int
    reference_window_end: int
    current_window_start: int
    current_window_end: int
    
    # Metadata
    detected_at: int
    acknowledged_at: Optional[int]
    behavior_ref_ids: List[str]
    conflict_ref_ids: List[str]
```

### 6.6 Enumerations

```python
class DriftType(str, Enum):
    TOPIC_EMERGENCE = "TOPIC_EMERGENCE"
    TOPIC_ABANDONMENT = "TOPIC_ABANDONMENT"
    PREFERENCE_REVERSAL = "PREFERENCE_REVERSAL"
    INTENSITY_SHIFT = "INTENSITY_SHIFT"
    CONTEXT_EXPANSION = "CONTEXT_EXPANSION"
    CONTEXT_CONTRACTION = "CONTEXT_CONTRACTION"

class DriftSeverity(str, Enum):
    NO_DRIFT = "NO_DRIFT"        # 0.0 - 0.3
    WEAK_DRIFT = "WEAK_DRIFT"    # 0.3 - 0.6
    MODERATE_DRIFT = "MODERATE_DRIFT"  # 0.6 - 0.8
    STRONG_DRIFT = "STRONG_DRIFT"      # 0.8 - 1.0
```

---

## 7. Database Schema

### 7.1 Tables

#### behavior_snapshots

Local projection of behaviors for drift analysis.

```sql
CREATE TABLE behavior_snapshots (
    user_id              TEXT NOT NULL,
    behavior_id          TEXT NOT NULL,
    target               TEXT NOT NULL,
    intent               TEXT NOT NULL,
    context              TEXT NOT NULL,
    polarity             TEXT NOT NULL,
    credibility          REAL NOT NULL,
    reinforcement_count  INTEGER NOT NULL,
    state                TEXT NOT NULL,
    created_at           BIGINT NOT NULL,
    last_seen_at         BIGINT NOT NULL,
    snapshot_updated_at  BIGINT NOT NULL,
    
    PRIMARY KEY (user_id, behavior_id)
);

-- Indexes
CREATE INDEX idx_bsnap_user_target ON behavior_snapshots(user_id, target);
CREATE INDEX idx_bsnap_user_state ON behavior_snapshots(user_id, state);
CREATE INDEX idx_bsnap_last_seen ON behavior_snapshots(user_id, last_seen_at);
CREATE INDEX idx_bsnap_created ON behavior_snapshots(user_id, created_at);
```

#### conflict_snapshots

Local projection of resolved conflicts.

```sql
CREATE TABLE conflict_snapshots (
    user_id            TEXT NOT NULL,
    conflict_id        TEXT NOT NULL,
    behavior_id_1      TEXT NOT NULL,
    behavior_id_2      TEXT NOT NULL,
    conflict_type      TEXT NOT NULL,
    resolution_status  TEXT NOT NULL,
    old_polarity       TEXT,
    new_polarity       TEXT,
    old_target         TEXT,
    new_target         TEXT,
    created_at         BIGINT NOT NULL,
    
    PRIMARY KEY (user_id, conflict_id)
);

CREATE INDEX idx_csnap_user_created ON conflict_snapshots(user_id, created_at);
```

#### drift_events

Detected drift events.

```sql
CREATE TABLE drift_events (
    drift_event_id          TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL,
    drift_type              TEXT NOT NULL,
    drift_score             REAL NOT NULL,
    confidence              REAL NOT NULL,
    severity                TEXT NOT NULL,
    affected_targets        TEXT[] NOT NULL,
    evidence                JSONB NOT NULL,
    reference_window_start  BIGINT NOT NULL,
    reference_window_end    BIGINT NOT NULL,
    current_window_start    BIGINT NOT NULL,
    current_window_end      BIGINT NOT NULL,
    detected_at             BIGINT NOT NULL,
    acknowledged_at         BIGINT,
    behavior_ref_ids        TEXT[],
    conflict_ref_ids        TEXT[]
);

CREATE INDEX idx_drift_user_detected ON drift_events(user_id, detected_at);
CREATE INDEX idx_drift_type ON drift_events(drift_type);
CREATE INDEX idx_drift_severity ON drift_events(severity);
CREATE INDEX idx_drift_user_type ON drift_events(user_id, drift_type);
```

#### drift_scan_jobs

Queue for scheduled drift detection jobs.

```sql
CREATE TABLE drift_scan_jobs (
    job_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          TEXT NOT NULL,
    trigger_event    TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'PENDING',
    priority         TEXT NOT NULL DEFAULT 'NORMAL',
    scheduled_at     BIGINT NOT NULL,
    started_at       BIGINT,
    completed_at     BIGINT,
    error_message    TEXT,
    
    CONSTRAINT valid_status CHECK (
        status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED', 'SKIPPED')
    )
);

CREATE INDEX idx_scan_jobs_user_status ON drift_scan_jobs(user_id, status);
CREATE INDEX idx_scan_jobs_status_scheduled ON drift_scan_jobs(status, scheduled_at);
```

---

## 8. API Layer

### 8.1 Endpoints

**Base URL**: `/api/v1`

#### Health Check
```http
GET /api/v1/health
```

**Response**:
```json
{
    "status": "healthy",
    "version": "1.0.0",
    "database": "connected",
    "timestamp": 1740556800
}
```

#### Detect Drift
```http
POST /api/v1/detect/{user_id}?force=false
```

**Parameters**:
- `user_id` (path) - User to analyze
- `force` (query) - Skip cooldown period

**Response**:
```json
{
    "user_id": "user_123",
    "detected_events": [
        {
            "drift_event_id": "drift_abc123",
            "user_id": "user_123",
            "drift_type": "TOPIC_EMERGENCE",
            "drift_score": 0.85,
            "severity": "STRONG_DRIFT",
            "affected_targets": ["pytorch", "tensorflow"],
            "evidence": {
                "emerging_target": "pytorch",
                "reinforcement_count": 5
            },
            "confidence": 0.9,
            "reference_window_start": 1704067200,
            "reference_window_end": 1706745600,
            "current_window_start": 1707350400,
            "current_window_end": 1709942400,
            "detected_at": 1709942400,
            "acknowledged_at": null,
            "behavior_ref_ids": [],
            "conflict_ref_ids": []
        }
    ],
    "detection_timestamp": 1709942400,
    "total_events": 1,
    "message": "Detected 1 drift event(s) for user user_123"
}
```

#### Get Drift Events
```http
GET /api/v1/events/{user_id}?drift_type=TOPIC_EMERGENCE&severity=STRONG_DRIFT&limit=50&offset=0
```

**Parameters**:
- `drift_type` (query) - Filter by drift type
- `severity` (query) - Filter by severity
- `start_date` (query) - Events after this date
- `end_date` (query) - Events before this date
- `limit` (query) - Max results (default: 50)
- `offset` (query) - Pagination offset

#### Get Single Event
```http
GET /api/v1/events/detail/{drift_event_id}
```

#### Acknowledge Event
```http
POST /api/v1/events/{drift_event_id}/acknowledge
```

### 8.2 Error Responses

| Status Code | Error | Description |
|-------------|-------|-------------|
| 400 | InsufficientDataError | User lacks sufficient data |
| 404 | UserNotFoundError | User not found |
| 404 | DriftEventNotFoundError | Event not found |
| 429 | CooldownError | Detection in cooldown |
| 500 | DatabaseError | Database operation failed |

---

## 9. Drift Detection Pipeline

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DRIFT DETECTION PIPELINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                               │
│  │  User ID     │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────┐                                       │
│  │  Pre-flight Checks   │                                       │
│  │  ├─ Sufficient data? │                                       │
│  │  ├─ In cooldown?     │                                       │
│  │  └─ Validate user    │                                       │
│  └──────────┬───────────┘                                       │
│             │ pass                                               │
│             ▼                                                    │
│  ┌──────────────────────────────────────────┐                   │
│  │        SNAPSHOT BUILDER                   │                  │
│  │  ┌─────────────────┐  ┌────────────────┐ │                   │
│  │  │    Reference    │  │    Current     │ │                   │
│  │  │    Snapshot     │  │    Snapshot    │ │                   │
│  │  │  (60-30 days)   │  │  (30-0 days)   │ │                   │
│  │  └────────┬────────┘  └───────┬────────┘ │                   │
│  └───────────┼───────────────────┼──────────┘                   │
│              └─────────┬─────────┘                               │
│                        ▼                                         │
│  ┌───────────────────────────────────────────────────────┐      │
│  │                    DETECTORS                           │      │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │      │
│  │  │   Topic     │ │   Topic     │ │ Preference  │     │      │
│  │  │ Emergence   │ │ Abandonment │ │  Reversal   │     │      │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘     │      │
│  │         │               │               │            │      │
│  │  ┌──────┴───────┐ ┌─────┴──────┐                     │      │
│  │  │  Intensity   │ │  Context   │                     │      │
│  │  │    Shift     │ │   Shift    │                     │      │
│  │  └──────┬───────┘ └─────┬──────┘                     │      │
│  └─────────┼───────────────┼────────────────────────────┘      │
│            └───────┬───────┘                                    │
│                    ▼                                             │
│  ┌──────────────────────────────────────┐                       │
│  │           AGGREGATOR                  │                       │
│  │  ├─ Group by affected targets        │                       │
│  │  ├─ Keep highest score per target    │                       │
│  │  ├─ Filter by threshold (0.6)        │                       │
│  │  └─ Sort by drift_score              │                       │
│  └─────────────────┬────────────────────┘                       │
│                    ▼                                             │
│  ┌──────────────────────────────────────┐                       │
│  │         EVENT CREATION                │                       │
│  │  Signal → DriftEvent                  │                       │
│  └─────────────────┬────────────────────┘                       │
│                    ▼                                             │
│  ┌──────────────────────────────────────┐                       │
│  │          PERSISTENCE                  │                       │
│  │  ├─ Write to PostgreSQL              │                       │
│  │  └─ Publish to Redis Streams         │                       │
│  └─────────────────┬────────────────────┘                       │
│                    ▼                                             │
│  ┌──────────────────────────────────────┐                       │
│  │      List[DriftEvent] Returned       │                       │
│  └──────────────────────────────────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Pre-flight Checks

1. **Sufficient Data**:
   - Minimum behaviors: 5 (configurable)
   - Minimum history: 14 days (configurable)

2. **Cooldown Period**:
   - Default: 1 hour between scans for same user
   - Can be bypassed with `force=true`

---

## 10. Detectors

### 10.1 BaseDetector

**Location**: `app/detectors/base.py`

Abstract base class for all detectors.

```python
class BaseDetector(ABC):
    @abstractmethod
    def detect(
        self,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> List[DriftSignal]:
        """Detect drift signals by comparing snapshots."""
        pass
```

### 10.2 TopicEmergenceDetector

**Location**: `app/detectors/topic_emergence.py`

Detects new topics appearing with significant activity.

**Detection Logic**:
1. Find topics in current but not in reference window
2. Filter by minimum reinforcement (default: 2)
3. Calculate drift score based on:
   - Relative importance (reinforcement / total)
   - Recency weight (newer = stronger)

**Evidence Captured**:
```json
{
    "emerging_target": "pytorch",
    "reinforcement_count": 5,
    "behavior_count": 2,
    "avg_credibility": 0.85,
    "avg_days_since_mention": 3.5,
    "recency_weight": 0.88,
    "relative_importance": 0.15,
    "contexts": ["machine_learning", "data_science"]
}
```

### 10.3 TopicAbandonmentDetector

**Location**: `app/detectors/topic_abandonment.py`

Detects previously active topics that have gone silent.

**Detection Logic**:
1. Get topics with sufficient reinforcement in reference (≥2)
2. Check if absent in current window
3. Verify silence exceeds threshold (30 days)
4. Calculate score based on historical activity

**Evidence Captured**:
```json
{
    "abandoned_target": "java",
    "historical_reinforcement": 15,
    "days_silent": 45,
    "silence_ratio": 1.5
}
```

### 10.4 PreferenceReversalDetector

**Location**: `app/detectors/preference_reversal.py`

Detects polarity flips (POSITIVE ↔ NEGATIVE).

**Detection Logic**:
1. Examine conflict records with polarity reversals
2. Find old and new behaviors
3. Score based on credibility of both behaviors

**Evidence Captured**:
```json
{
    "conflict_id": "conflict_abc",
    "old_polarity": "POSITIVE",
    "new_polarity": "NEGATIVE",
    "old_credibility": 0.7,
    "new_credibility": 0.85,
    "target": "typescript"
}
```

### 10.5 IntensityShiftDetector

**Location**: `app/detectors/intensity_shift.py`

Detects changes in credibility/conviction strength.

**Detection Logic**:
1. Find common targets in both windows
2. Calculate average credibility for each
3. Check if delta exceeds threshold (0.25)
4. Capture direction (INCREASE/DECREASE)

**Evidence Captured**:
```json
{
    "target": "docker",
    "direction": "INCREASE",
    "reference_credibility": 0.5,
    "current_credibility": 0.85,
    "credibility_delta": 0.35,
    "relative_change_pct": 70.0
}
```

### 10.6 ContextShiftDetector

**Location**: `app/detectors/context_shift.py`

Detects context expansion or contraction.

**Detection Logic**:
1. Build context maps for both windows
2. Find common targets
3. Detect expansion: specific → "general"
4. Detect contraction: "general" → specific

**Evidence Captured**:
```json
{
    "target": "python",
    "shift_type": "EXPANSION",
    "reference_contexts": ["data_science"],
    "current_contexts": ["general", "web"],
    "context_diversity_change": 2
}
```

### 10.7 Embedding-Based Clustering

**Location**: `app/detectors/utils/embedding_cluster.py`

Optional utility for semantic topic clustering using ML.

```python
def cluster_topics(topics: Set[str]) -> List[Set[str]]:
    """
    Cluster topics using sentence-transformers + DBSCAN.
    
    Uses: all-MiniLM-L6-v2 model (384 dimensions)
    Clustering: DBSCAN with cosine distance
    """
```

**Configuration**:
- Model: `all-MiniLM-L6-v2`
- DBSCAN epsilon: 0.4
- Min samples: 2

---

## 11. Message Processing

### 11.1 Redis Consumer

**Location**: `app/consumer/redis_consumer.py`

Consumes events from Redis Streams using consumer groups.

```python
class RedisConsumer:
    """Consumes events from Redis Streams and dispatches to event handlers."""
    
    # Configuration
    stream_name = "behavior.events"
    consumer_group = "drift_detection_service"
    
    def start(self):
        """Main consumption loop with graceful shutdown."""
```

**Features**:
- Consumer group semantics (exactly-once processing)
- Automatic reconnection with exponential backoff
- Graceful shutdown on SIGINT/SIGTERM
- Message acknowledgment after processing

### 11.2 BehaviorEventHandler

**Location**: `app/consumer/behavior_event_handler.py`

Processes different behavior event types.

**Supported Events**:

| Event Type | Action |
|------------|--------|
| `behavior.created` | Upsert behavior snapshot |
| `behavior.reinforced` | Update count & last_seen_at |
| `behavior.superseded` | Update state to SUPERSEDED |
| `behavior.conflict.resolved` | Insert conflict snapshot |

**Event Processing Flow**:
```
Redis Stream → Consumer → BehaviorEventHandler → Database Update → [Maybe enqueue scan]
```

### 11.3 DriftEventWriter

**Location**: `app/pipeline/drift_event_writer.py`

Persists drift events and publishes to Redis Streams.

```python
class DriftEventWriter:
    def write(self, events: List[DriftEvent]) -> List[str]:
        """
        1. Write events to PostgreSQL
        2. Publish to drift.events stream
        3. Return persisted event IDs
        """
```

**Atomicity**:
- Events only published to Redis if database write succeeds
- Individual failures don't halt entire batch

---

## 12. Background Workers

### 12.1 Celery Configuration

**Location**: `app/workers/celery_app.py`

```python
celery_app = Celery(
    "drift_detection_service",
    broker="redis://localhost:6379/1",
    backend="redis://localhost:6379/2",
    include=["app.workers.scan_worker"]
)

# Key settings
celery_app.conf.update(
    task_time_limit=300,          # 5 minutes hard limit
    task_soft_time_limit=240,     # 4 minutes soft limit
    worker_prefetch_multiplier=1, # Fair processing
    worker_max_tasks_per_child=100,
)
```

### 12.2 Scan Worker

**Location**: `app/workers/scan_worker.py`

Celery task for executing drift detection jobs.

```python
@celery_app.task(
    bind=True,
    base=ScanTask,
    name="app.workers.scan_worker.run_drift_scan",
    acks_late=True,
    reject_on_worker_lost=True,
)
def run_drift_scan(self, job_id: str) -> Dict[str, Any]:
    """
    Workflow:
    1. Retrieve job from database
    2. Validate status (must be PENDING)
    3. Update to RUNNING
    4. Execute drift detection
    5. Update to DONE or FAILED
    """
```

**Retry Configuration**:
- Max retries: 3
- Exponential backoff with jitter
- Max backoff: 10 minutes

---

## 13. Scheduling System

### 13.1 APScheduler Configuration

**Location**: `app/scheduler/cron.py`

```python
def build_scheduler() -> AsyncIOScheduler:
    """Configure periodic jobs."""
    
    scheduler.add_job(
        func=scan_active_users,
        trigger=IntervalTrigger(hours=24),
        id="scan_active_users",
    )
    
    scheduler.add_job(
        func=scan_moderate_users,
        trigger=IntervalTrigger(hours=72),
        id="scan_moderate_users",
    )
    
    scheduler.add_job(
        func=reap_dead_letters,
        trigger=IntervalTrigger(minutes=10),
        id="reap_dead_letters",
    )
```

### 13.2 User Tiers

| Tier | Activity Threshold | Scan Frequency |
|------|-------------------|----------------|
| **Active** | Last 7 days | Every 24 hours |
| **Moderate** | Last 30 days | Every 72 hours |
| **Dormant** | >30 days | Not scanned |

### 13.3 Dead Letter Handler

**Location**: `app/scheduler/dead_letter.py`

Handles messages stuck in the Pending Entries List (PEL).

**Dead Letter Criteria**:
- Idle > 5 minutes (configurable)
- Delivered 3+ times without acknowledgment

**Actions**:
1. Claim the message
2. Move to `.deadletter` stream
3. Acknowledge in original stream
4. Log for monitoring

---

## 14. Configuration Management

### 14.1 Settings Class

**Location**: `app/config.py`

All configuration managed through `pydantic-settings`.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
```

### 14.2 Configuration Categories

#### Application
| Setting | Default | Description |
|---------|---------|-------------|
| `app_name` | "Drift Detection Service" | Application name |
| `environment` | "development" | Environment (development/production) |
| `debug` | True | Debug mode |
| `log_level` | "INFO" | Logging level |

#### Database
| Setting | Default | Description |
|---------|---------|-------------|
| `database_url` | Required | PostgreSQL connection URL |
| `db_pool_size` | 10 | Connection pool size |
| `db_max_overflow` | 20 | Max overflow connections |

#### Redis
| Setting | Default | Description |
|---------|---------|-------------|
| `redis_url` | redis://localhost:6379/0 | Redis connection URL |
| `redis_stream_behavior_events` | behavior.events | Input stream |
| `redis_stream_drift_events` | drift.events | Output stream |
| `redis_consumer_group` | drift_detection_service | Consumer group |

#### Drift Detection
| Setting | Default | Description |
|---------|---------|-------------|
| `min_behaviors_for_drift` | 5 | Minimum behaviors required |
| `min_days_of_history` | 14 | Minimum history required |
| `scan_cooldown_seconds` | 3600 | Cooldown between scans |
| `drift_score_threshold` | 0.6 | Minimum score for events |

#### Time Windows
| Setting | Default | Description |
|---------|---------|-------------|
| `current_window_days` | 30 | Current window size |
| `reference_window_start_days` | 60 | Reference start (days ago) |
| `reference_window_end_days` | 30 | Reference end (days ago) |

#### Detector-Specific
| Setting | Default | Description |
|---------|---------|-------------|
| `abandonment_silence_days` | 30 | Days to consider abandoned |
| `min_reinforcement_for_abandonment` | 2 | Min historical activity |
| `intensity_delta_threshold` | 0.25 | Min credibility change |
| `emergence_min_reinforcement` | 2 | Min mentions for emergence |

#### ML/Embeddings
| Setting | Default | Description |
|---------|---------|-------------|
| `embedding_model` | all-MiniLM-L6-v2 | Sentence transformer model |
| `embedding_dimension` | 384 | Embedding vector size |
| `embedding_cluster_eps` | 0.4 | DBSCAN epsilon |
| `embedding_cluster_min_samples` | 2 | DBSCAN min samples |

---

## 15. Error Handling

### 15.1 Custom Exceptions

**Location**: `api/errors.py`

```python
class DriftDetectionError(Exception):
    """Base exception"""

class InsufficientDataError(DriftDetectionError):
    """User lacks sufficient data"""
    status_code = 400

class UserNotFoundError(DriftDetectionError):
    """User not found"""
    status_code = 404

class CooldownError(DriftDetectionError):
    """Detection in cooldown"""
    status_code = 429

class DriftEventNotFoundError(DriftDetectionError):
    """Event not found"""
    status_code = 404

class DatabaseError(DriftDetectionError):
    """Database operation failed"""
    status_code = 500
```

### 15.2 Exception Handlers

FastAPI exception handlers convert exceptions to JSON responses:

```python
app.add_exception_handler(DriftDetectionError, drift_detection_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)
```

### 15.3 Error Response Format

```json
{
    "error": "User user_123 has insufficient data for drift detection",
    "detail": null,
    "timestamp": 1740556800
}
```

---

## 16. Testing Strategy

### 16.1 Test Configuration

**Location**: `tests/conftest.py`

Fixtures for comprehensive testing:

```python
@pytest.fixture
def test_settings() -> Settings:
    """Test configuration with defaults."""

@pytest.fixture
def behavior_factory():
    """Factory for creating test behaviors."""

@pytest.fixture
def snapshot_factory():
    """Factory for creating test snapshots."""

@pytest.fixture
def mock_db_connection():
    """Mock database connection."""
```

### 16.2 Test Categories

| File | Focus |
|------|-------|
| `test_detectors.py` | Individual detector algorithms |
| `test_aggregator.py` | Signal aggregation logic |
| `test_models.py` | Data model validation |
| `test_api.py` | API endpoint testing |
| `test_utils.py` | Utility functions |

### 16.3 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_detectors.py

# Run with verbose output
pytest -v
```

---

## 17. Deployment

### 17.1 Docker Configuration

**Dockerfile** (multi-stage):
```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder
# Install dependencies, pre-download ML model

# Stage 2: Runtime
FROM python:3.11-slim
# Minimal production image with non-root user
```

**docker-compose.yml** services:

| Service | Container | Ports | Purpose |
|---------|-----------|-------|---------|
| `redis` | drift-redis | 6379 | Message broker, cache |
| `api` | drift-api | 8000 | FastAPI + APScheduler |
| `worker` | drift-worker | - | Celery workers |
| `consumer` | drift-consumer | - | Redis Stream consumer |

### 17.2 Service Commands

```bash
# Start all services
docker compose up -d --build

# View logs
docker compose logs -f api
docker compose logs -f worker

# Scale workers
docker compose up -d --scale worker=4

# Stop services
docker compose down
```

### 17.3 Environment Variables

Required environment variables:
```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

---

## 18. Data Flow Diagrams

### 18.1 Event Processing Flow

```
┌────────────────┐
│ Behavior       │
│ Service        │
└───────┬────────┘
        │ behavior.created
        │ behavior.reinforced
        │ behavior.superseded
        │ behavior.conflict.resolved
        ▼
┌────────────────────┐
│   Redis Stream     │
│  behavior.events   │
└───────┬────────────┘
        │
        ▼
┌────────────────────┐     ┌──────────────────┐
│  Redis Consumer    │────▶│ BehaviorEvent    │
│                    │     │ Handler          │
└────────────────────┘     └────────┬─────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
            │  Upsert      │ │  Update      │ │  Insert      │
            │  Behavior    │ │  Behavior    │ │  Conflict    │
            │  Snapshot    │ │  Snapshot    │ │  Snapshot    │
            └──────────────┘ └──────────────┘ └──────────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    ▼
                            ┌──────────────────┐
                            │ Maybe Enqueue    │
                            │ Scan Job         │
                            └──────────────────┘
```

### 18.2 Scheduled Scan Flow

```
┌────────────────┐
│  APScheduler   │
│  (Cron Job)    │
└───────┬────────┘
        │ Every 24h (active)
        │ Every 72h (moderate)
        ▼
┌────────────────────┐
│ Get Scannable      │
│ Users by Tier      │
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│ Enqueue Scan Jobs  │
│ (drift_scan_jobs)  │
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│  Celery Broker     │
│  (Redis)           │
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│  Celery Worker     │
│  run_drift_scan    │
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│  Drift Detector    │
│  Pipeline          │
└───────┬────────────┘
        │
        ▼
┌────────────────────┐     ┌────────────────────┐
│  PostgreSQL        │     │  Redis Stream      │
│  drift_events      │     │  drift.events      │
└────────────────────┘     └────────────────────┘
```

---

## 19. Security Considerations

### 19.1 Authentication & Authorization

- **Current State**: No built-in authentication
- **Recommendation**: Implement API key or JWT authentication
- **CORS**: Configured for all origins (restrict in production)

### 19.2 Data Protection

- Database credentials via environment variables
- Non-root user in Docker containers
- Connection pooling limits

### 19.3 Input Validation

- Pydantic models for request validation
- Parameter constraints (ranges, lengths)
- SQL parameterization (no raw queries)

### 19.4 Recommendations

1. Add rate limiting to API endpoints
2. Implement API authentication
3. Restrict CORS origins in production
4. Enable SSL/TLS for Redis connections
5. Audit logging for sensitive operations

---

## 20. Performance Considerations

### 20.1 Database Optimization

- **Indexes**: Comprehensive indexing on common query patterns
- **Connection Pooling**: Configurable pool sizes
- **Window Queries**: Optimized for time-range queries

### 20.2 Caching

- **Settings**: LRU cached (loaded once)
- **ML Model**: Cached after first load
- **Drift Detector**: Cached instance in API

### 20.3 Async vs Sync

- **API**: FastAPI (async capable, sync DB ops)
- **Consumer**: Sync loop with blocking reads
- **Workers**: Sync Celery tasks

### 20.4 Scaling Strategies

1. **Horizontal**: Scale Celery workers
2. **Vertical**: Increase pool sizes
3. **Sharding**: Partition by user_id

### 20.5 Monitoring Recommendations

1. Track detector execution times
2. Monitor Redis stream lag
3. Alert on dead letter accumulation
4. Database query performance

---

## Appendix A: File Structure Reference

```
drift_detection_service/
├── api/
│   ├── __init__.py
│   ├── dependencies.py     # FastAPI dependency injection
│   ├── errors.py           # Custom exceptions
│   ├── main.py             # FastAPI application
│   ├── models.py           # Pydantic request/response models
│   └── routes.py           # API endpoint definitions
├── app/
│   ├── __init__.py
│   ├── config.py           # Settings management
│   ├── consumer/
│   │   ├── __init__.py
│   │   ├── behavior_event_handler.py
│   │   └── redis_consumer.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── drift_aggregator.py
│   │   ├── drift_detector.py
│   │   └── snapshot_builder.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── repositories/
│   │       ├── behavior_repo.py
│   │       ├── conflict_repo.py
│   │       ├── drift_event_repo.py
│   │       └── scan_job_repo.py
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── context_shift.py
│   │   ├── intensity_shift.py
│   │   ├── preference_reversal.py
│   │   ├── topic_abandonment.py
│   │   ├── topic_emergence.py
│   │   └── utils/
│   │       └── embedding_cluster.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── behavior.py
│   │   ├── drift.py
│   │   └── snapshot.py
│   ├── pipeline/
│   │   └── drift_event_writer.py
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── cron.py
│   │   └── dead_letter.py
│   ├── utils/
│   │   └── time.py
│   └── workers/
│       ├── __init__.py
│       ├── celery_app.py
│       └── scan_worker.py
├── migrations/
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   ├── conftest.py
│   ├── test_aggregator.py
│   ├── test_api.py
│   ├── test_detectors.py
│   ├── test_models.py
│   └── test_utils.py
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pytest.ini
├── README.md
├── requirements.txt
└── run_api.py
```

---

## Appendix B: Quick Reference Commands

```bash
# Development
python run_api.py                    # Start API server
celery -A app.workers.celery_app worker --loglevel=info  # Start worker
python -m app.consumer.redis_consumer  # Start consumer

# Database
alembic upgrade head                 # Run migrations
alembic downgrade -1                 # Rollback one step

# Testing
pytest                               # Run all tests
pytest --cov=app                     # With coverage
pytest -k "test_detector"            # Filter tests

# Docker
docker compose up -d --build         # Start all services
docker compose logs -f               # View logs
docker compose down                  # Stop services
```

---

*Document generated: February 26, 2026*
*Version: 1.0.0*
