# Behavioral Drift Detection System

## Overview

The Drift Detection Service identifies **behavioral drift** in users by comparing their historical behavior patterns (reference window) against their recent behavior patterns (current window). When significant changes are detected, drift events are generated and published for downstream processing.

---

## Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DRIFT DETECTION PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐    ┌──────────────────┐    ┌────────────────────────┐   │
│   │   Behavior   │    │  Redis Consumer  │    │   BehaviorEventHandler │   │
│   │   Service    │───▶│  (behavior.events│───▶│   - Upsert snapshots   │   │
│   │              │    │     stream)      │    │   - Enqueue scan jobs  │   │
│   └──────────────┘    └──────────────────┘    └────────────────────────┘   │
│                                                          │                  │
│                                                          ▼                  │
│                                               ┌────────────────────────┐   │
│                                               │    Celery Worker       │   │
│                                               │    (Scan Worker)       │   │
│                                               └────────────────────────┘   │
│                                                          │                  │
│                                                          ▼                  │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                        DRIFT DETECTOR                                 │ │
│   │  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐  │ │
│   │  │ Snapshot Builder│───▶│  5 Drift Detectors│───▶│ Drift Aggregator│  │ │
│   │  │ (Reference +    │    │  (analyze both   │    │ (deduplicate &  │  │ │
│   │  │  Current)       │    │  snapshots)      │    │  filter)        │  │ │
│   │  └─────────────────┘    └──────────────────┘    └─────────────────┘  │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                          │                  │
│                                                          ▼                  │
│                                               ┌────────────────────────┐   │
│                                               │  DriftEventWriter      │   │
│                                               │  - Persist to DB       │   │
│                                               │  - Publish to Redis    │   │
│                                               │    (drift.events)      │   │
│                                               └────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### Behavior Snapshots

A **BehaviorSnapshot** represents a user's complete behavior profile within a specific time window. It contains:

| Field | Description |
|-------|-------------|
| `user_id` | User identifier |
| `window_start` / `window_end` | Time window boundaries |
| `behaviors` | List of `BehaviorRecord` objects |
| `conflict_records` | List of `ConflictRecord` objects |
| `topic_distribution` | Computed distribution of topics (targets) |
| `intent_distribution` | Computed distribution of intents |
| `polarity_by_target` | Current polarity (POSITIVE/NEGATIVE) per target |

### Behavior Record

Each behavior record tracks:

```python
BehaviorRecord:
    user_id: str
    behavior_id: str
    target: str           # e.g., "Python", "Docker", "React"
    intent: str           # PREFERENCE | CONSTRAINT | HABIT | SKILL | COMMUNICATION
    context: str          # e.g., "backend", "data_science", "general"
    polarity: str         # POSITIVE | NEGATIVE
    credibility: float    # 0.0 – 1.0 (conviction strength)
    reinforcement_count: int  # How many times behavior was reinforced
    state: str            # ACTIVE | SUPERSEDED
    created_at: int       # Unix timestamp
    last_seen_at: int     # Unix timestamp
```

---

## Time Windows

The system compares two time windows:

| Window | Default Configuration | Purpose |
|--------|----------------------|---------|
| **Reference Window** | 30-60 days ago | Historical baseline for comparison |
| **Current Window** | Last 30 days | Recent behavior to detect changes |

```
Timeline:
────────────────────────────────────────────────────────────────────▶ Now
         │                    │                   │
    60 days ago          30 days ago           Today
         └────────────────────┘                   │
           Reference Window                       │
                              └───────────────────┘
                                 Current Window
```

**Key Difference:**
- **Reference Window**: Includes behaviors that were active during that period (even if now `SUPERSEDED`)
- **Current Window**: Only includes currently `ACTIVE` behaviors

---

## Drift Detection Pipeline

### Step 1: Pre-flight Checks

Before running detection, the system validates:

1. **Sufficient Data**: User must have:
   - At least `5` active behaviors (configurable: `min_behaviors_for_drift`)
   - At least `14` days of history (configurable: `min_days_of_history`)

2. **Cooldown Period**: At least `1 hour` since last scan for this user (configurable: `scan_cooldown_seconds`)

### Step 2: Build Snapshots

The `SnapshotBuilder` queries the database to create:
- **Reference Snapshot**: Historical behaviors (includes superseded)
- **Current Snapshot**: Recent active behaviors

### Step 3: Run Detectors

Five specialized detectors analyze both snapshots:

```
┌────────────────────────────────────────────────────────────────────┐
│                         DRIFT DETECTORS                             │
├────────────────────────────────────────────────────────────────────┤
│  1. TopicEmergenceDetector    → New topics appearing               │
│  2. TopicAbandonmentDetector  → Old topics going silent            │
│  3. PreferenceReversalDetector → Opinion polarity flips            │
│  4. IntensityShiftDetector    → Conviction strength changes        │
│  5. ContextShiftDetector      → Context expansion/contraction      │
└────────────────────────────────────────────────────────────────────┘
```

### Step 4: Aggregate Signals

The `DriftAggregator` processes raw signals:
1. Groups signals by affected targets
2. Keeps highest-scoring signal per target (deduplication)
3. Filters by threshold (`drift_score >= 0.6`)
4. Checks actionability (MODERATE or STRONG severity)
5. Sorts by score descending

### Step 5: Create & Persist Events

Signals are converted to `DriftEvent` objects and:
- Persisted to PostgreSQL (`drift_events` table)
- Published to Redis Streams (`drift.events`)

---

## Drift Types in Detail

### 1. Topic Emergence 🆕

**What it detects:** New topics appearing with significant activity

**Detection Logic:**
```
IF target ∈ current_targets AND target ∉ reference_targets:
    IF reinforcement_count >= 2:
        signal = TOPIC_EMERGENCE
```

**Score Calculation:**
```python
drift_score = reinforcement_weight × avg_credibility × recency_weight

where:
  reinforcement_weight = min(reinforcement_count / 4, 1.0)
  recency_weight = max(0.1, 1.0 - (days_ago / 14))
```

**Example:**
```
Reference: {Python, Docker, AWS}
Current:   {Python, Docker, AWS, Kubernetes}  ← NEW!

Signal: TOPIC_EMERGENCE for "Kubernetes" (if reinforced 2+ times)
```

---

### 2. Topic Abandonment 📉

**What it detects:** Previously active topics that have gone silent

**Detection Logic:**
```
IF target ∈ reference_targets AND target ∉ current_targets:
    IF historical_reinforcement >= 2:
        IF (now - last_seen_at) > 30 days:
            signal = TOPIC_ABANDONMENT
```

**Score Calculation:**
```python
# Based on historical importance that's now lost
if days_silent >= 60:
    drift_score = 0.8
else:
    drift_score = 0.5 + (days_silent / 60) × 0.3
```

**Example:**
```
Reference: {Python, Java, React}  ← Java was active
Current:   {Python, React}        ← Java absent for 45 days

Signal: TOPIC_ABANDONMENT for "Java"
```

---

### 3. Preference Reversal 🔄

**What it detects:** Opinion polarity flips (POSITIVE ↔ NEGATIVE)

**Detection Logic:**
```
FOR each conflict_record in current_snapshot:
    IF conflict.is_polarity_reversal:
        signal = PREFERENCE_REVERSAL
```

**Score Calculation:**
```python
# Average of old and new behavior credibilities
drift_score = (old_behavior.credibility + new_behavior.credibility) / 2
```

**Example:**
```
Reference: "I love Java" (POSITIVE, credibility=0.8)
Current:   "I dislike Java" (NEGATIVE, credibility=0.75)

Signal: PREFERENCE_REVERSAL (score = 0.775)
```

---

### 4. Intensity Shift ⚡

**What it detects:** Changes in conviction strength (credibility)

**Detection Logic:**
```
FOR each target in (reference_targets ∩ current_targets):
    delta = |current_credibility - reference_credibility|
    IF delta >= 0.25:  # intensity_delta_threshold
        signal = INTENSITY_SHIFT (direction: INCREASE or DECREASE)
```

**Score Calculation:**
```python
drift_score = delta  # Direct use of credibility change
```

**Example:**
```
Reference: Python credibility = 0.5
Current:   Python credibility = 0.85
Delta:     0.35 (>= 0.25 threshold)

Signal: INTENSITY_SHIFT (INCREASE, score=0.35)
```

---

### 5. Context Shift 🔀

**What it detects:** Changes in usage context patterns

| Shift Type | Detection | Example |
|------------|-----------|---------|
| **EXPANSION** | Specific → General | "Python in data_science" → "Python in general" |
| **CONTRACTION** | General → Specific | "Docker in general" → "Docker in microservices" |

**Detection Logic:**
```python
# EXPANSION: Didn't have "general" before, has it now
if "general" not in ref_contexts and "general" in cur_contexts:
    signal = CONTEXT_EXPANSION

# CONTRACTION: Had "general" before, doesn't have it now
if "general" in ref_contexts and "general" not in cur_contexts:
    signal = CONTEXT_CONTRACTION
```

**Score Calculation:**
```python
# Based on number of context changes
drift_score = min(context_change_count / 3, 1.0) × 0.7
```

---

## Drift Severity Levels

Drift scores are categorized into severity levels:

| Severity | Score Range | Actionable |
|----------|-------------|------------|
| `NO_DRIFT` | 0.0 - 0.3 | ❌ |
| `WEAK_DRIFT` | 0.3 - 0.6 | ❌ |
| `MODERATE_DRIFT` | 0.6 - 0.8 | ✅ |
| `STRONG_DRIFT` | 0.8 - 1.0 | ✅ |

Only **MODERATE** and **STRONG** severity signals create drift events.

---

## Configuration Parameters

### Core Thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `drift_score_threshold` | 0.6 | Minimum score to create an event |
| `min_behaviors_for_drift` | 5 | Minimum behaviors required |
| `min_days_of_history` | 14 | Minimum history required |
| `scan_cooldown_seconds` | 3600 | Cooldown between scans (1 hour) |

### Time Windows

| Parameter | Default | Description |
|-----------|---------|-------------|
| `current_window_days` | 30 | Size of current window |
| `reference_window_start_days` | 60 | Reference window starts N days ago |
| `reference_window_end_days` | 30 | Reference window ends N days ago |

### Detector-Specific

| Parameter | Default | Detector |
|-----------|---------|----------|
| `emergence_min_reinforcement` | 2 | TopicEmergence |
| `recency_weight_days` | 14 | TopicEmergence |
| `abandonment_silence_days` | 30 | TopicAbandonment |
| `min_reinforcement_for_abandonment` | 2 | TopicAbandonment |
| `intensity_delta_threshold` | 0.25 | IntensityShift |

---

## Data Flow Summary

```
1. Behavior Service publishes events → behavior.events stream
                    ↓
2. RedisConsumer reads events → BehaviorEventHandler processes
                    ↓
3. Handler upserts behavior_snapshots & conflict_snapshots tables
                    ↓
4. Handler enqueues drift scan job (if gates pass)
                    ↓
5. Celery Worker picks up job → runs DriftDetector.detect_drift(user_id)
                    ↓
6. SnapshotBuilder creates reference & current BehaviorSnapshots
                    ↓
7. All 5 detectors analyze snapshots → produce DriftSignals
                    ↓
8. DriftAggregator deduplicates & filters signals
                    ↓
9. Signals converted to DriftEvents → persisted to drift_events table
                    ↓
10. DriftEventWriter publishes to drift.events stream
                    ↓
11. Downstream services consume drift events for recommendations, alerts, etc.
```

---

## DriftEvent Output Schema

```python
DriftEvent:
    drift_event_id: str           # UUID
    user_id: str
    drift_type: DriftType         # TOPIC_EMERGENCE | TOPIC_ABANDONMENT | etc.
    drift_score: float            # 0.0 - 1.0
    confidence: float             # 0.0 - 1.0
    severity: DriftSeverity       # NO_DRIFT | WEAK | MODERATE | STRONG
    affected_targets: List[str]   # e.g., ["Python", "Docker"]
    evidence: Dict[str, Any]      # Detector-specific metadata
    reference_window_start: int   # Unix timestamp
    reference_window_end: int
    current_window_start: int
    current_window_end: int
    detected_at: int              # When drift was detected
    acknowledged_at: int | None   # When user acknowledged (if applicable)
```

---

## Example Detection Scenario

**User: alice_dev**

**Reference Window (30-60 days ago):**
```
Behaviors:
- Python (general, POSITIVE, credibility=0.6, reinforcement=5)
- Docker (backend, POSITIVE, credibility=0.7, reinforcement=3)
- Java (backend, POSITIVE, credibility=0.5, reinforcement=2)
```

**Current Window (last 30 days):**
```
Behaviors:
- Python (general, POSITIVE, credibility=0.9, reinforcement=8)  ← Intensity UP
- Docker (general, POSITIVE, credibility=0.7, reinforcement=4)  ← Context EXPANSION
- Kubernetes (devops, POSITIVE, credibility=0.75, reinforcement=3)  ← NEW TOPIC
- Java: NO ACTIVITY for 45 days  ← ABANDONED
```

**Detected Drift Events:**

| Type | Target | Score | Evidence |
|------|--------|-------|----------|
| `TOPIC_EMERGENCE` | Kubernetes | 0.75 | New topic with 3 reinforcements |
| `TOPIC_ABANDONMENT` | Java | 0.65 | Silent for 45 days, had 2+ reinforcements |
| `INTENSITY_SHIFT` | Python | 0.30 | Credibility: 0.6 → 0.9 (delta=0.3) |
| `CONTEXT_EXPANSION` | Docker | 0.60 | backend → general |

---

## Key Design Decisions

1. **Superseded Behaviors in Reference**: Historical windows include superseded behaviors to accurately represent past state.

2. **Per-Target Deduplication**: Only the highest-scoring signal per target is kept to avoid alert fatigue.

3. **Minimum Reinforcement Gates**: Casual mentions (1 reinforcement) don't trigger emergence/abandonment.

4. **Recency Weighting**: More recent activity carries higher weight in scoring.

5. **Cooldown Period**: Prevents excessive scanning for rapidly changing users.

6. **Actionability Filter**: Only MODERATE+ severity events are persisted, reducing noise.
