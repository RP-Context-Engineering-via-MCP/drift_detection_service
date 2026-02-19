"""
Pytest Configuration and Fixtures.

Provides shared fixtures for testing the drift detection service.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import List
from unittest.mock import MagicMock, patch

from app.config import Settings
from app.models.behavior import BehaviorRecord, ConflictRecord
from app.models.snapshot import BehaviorSnapshot
from app.models.drift import DriftSignal, DriftEvent, DriftType, DriftSeverity


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with default values."""
    return Settings(
        database_url="postgresql://test:test@localhost/test_db",
        debug=True,
        environment="test",
        drift_score_threshold=0.6,
        min_behaviors_for_drift=3,
        min_days_of_history=7,
        scan_cooldown_seconds=60,
        current_window_days=30,
        reference_window_start_days=60,
        reference_window_end_days=30,
        abandonment_silence_days=30,
        min_reinforcement_for_abandonment=2,
        intensity_delta_threshold=0.25,
        emergence_min_reinforcement=2,
    )


# ============================================================================
# Behavior Record Fixtures
# ============================================================================

@pytest.fixture
def sample_behavior() -> BehaviorRecord:
    """Create a sample behavior record."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    return BehaviorRecord(
        user_id="user_123",
        behavior_id="beh_001",
        target="python",
        intent="PREFERENCE",
        context="backend",
        polarity="POSITIVE",
        credibility=0.8,
        reinforcement_count=5,
        state="ACTIVE",
        created_at=now_ts - 86400 * 10,  # 10 days ago
        last_seen_at=now_ts - 86400,  # 1 day ago
        snapshot_updated_at=now_ts,
    )


@pytest.fixture
def behavior_factory():
    """Factory to create behavior records with custom attributes."""
    def _create_behavior(
        user_id: str = "user_123",
        behavior_id: str = "beh_001",
        target: str = "python",
        intent: str = "PREFERENCE",
        context: str = "backend",
        polarity: str = "POSITIVE",
        credibility: float = 0.8,
        reinforcement_count: int = 5,
        state: str = "ACTIVE",
        days_ago: int = 10,
        last_seen_days_ago: int = 1,
    ) -> BehaviorRecord:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        return BehaviorRecord(
            user_id=user_id,
            behavior_id=behavior_id,
            target=target,
            intent=intent,
            context=context,
            polarity=polarity,
            credibility=credibility,
            reinforcement_count=reinforcement_count,
            state=state,
            created_at=now_ts - 86400 * days_ago,
            last_seen_at=now_ts - 86400 * last_seen_days_ago,
            snapshot_updated_at=now_ts,
        )
    return _create_behavior


# ============================================================================
# Conflict Record Fixtures
# ============================================================================

@pytest.fixture
def sample_conflict() -> ConflictRecord:
    """Create a sample conflict record with polarity reversal."""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    return ConflictRecord(
        user_id="user_123",
        conflict_id="conf_001",
        behavior_id_1="beh_001",
        behavior_id_2="beh_002",
        conflict_type="POLARITY_CONFLICT",  # Align with publisher format
        resolution_status="AUTO_RESOLVED",
        old_polarity="POSITIVE",
        new_polarity="NEGATIVE",
        old_target=None,
        new_target=None,
        created_at=now_ts - 86400 * 5,  # 5 days ago
    )


@pytest.fixture
def conflict_factory():
    """Factory to create conflict records with custom attributes."""
    def _create_conflict(
        user_id: str = "user_123",
        conflict_id: str = "conf_001",
        behavior_id_1: str = "beh_001",
        behavior_id_2: str = "beh_002",
        conflict_type: str = "POLARITY_CONFLICT",  # Align with publisher format
        resolution_status: str = "AUTO_RESOLVED",
        old_polarity: str = "POSITIVE",
        new_polarity: str = "NEGATIVE",
        days_ago: int = 5,
    ) -> ConflictRecord:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        return ConflictRecord(
            user_id=user_id,
            conflict_id=conflict_id,
            behavior_id_1=behavior_id_1,
            behavior_id_2=behavior_id_2,
            conflict_type=conflict_type,
            resolution_status=resolution_status,
            old_polarity=old_polarity,
            new_polarity=new_polarity,
            old_target=None,
            new_target=None,
            created_at=now_ts - 86400 * days_ago,
        )
    return _create_conflict


# ============================================================================
# Snapshot Fixtures
# ============================================================================

@pytest.fixture
def empty_snapshot() -> BehaviorSnapshot:
    """Create an empty snapshot."""
    now = datetime.now(timezone.utc)
    return BehaviorSnapshot(
        user_id="user_123",
        window_start=now - timedelta(days=30),
        window_end=now,
        behaviors=[],
        conflict_records=[],
    )


@pytest.fixture
def reference_snapshot(behavior_factory) -> BehaviorSnapshot:
    """Create a reference snapshot with sample behaviors."""
    now = datetime.now(timezone.utc)
    behaviors = [
        behavior_factory(behavior_id="beh_ref_1", target="python", reinforcement_count=10, days_ago=45),
        behavior_factory(behavior_id="beh_ref_2", target="java", reinforcement_count=5, days_ago=50),
        behavior_factory(behavior_id="beh_ref_3", target="docker", reinforcement_count=3, days_ago=40),
    ]
    return BehaviorSnapshot(
        user_id="user_123",
        window_start=now - timedelta(days=60),
        window_end=now - timedelta(days=30),
        behaviors=behaviors,
        conflict_records=[],
    )


@pytest.fixture
def current_snapshot(behavior_factory) -> BehaviorSnapshot:
    """Create a current snapshot with sample behaviors."""
    now = datetime.now(timezone.utc)
    behaviors = [
        behavior_factory(behavior_id="beh_cur_1", target="python", reinforcement_count=15, days_ago=10),
        behavior_factory(behavior_id="beh_cur_2", target="rust", reinforcement_count=8, days_ago=5),  # New topic
        behavior_factory(behavior_id="beh_cur_3", target="kubernetes", reinforcement_count=6, days_ago=7),  # New topic
    ]
    return BehaviorSnapshot(
        user_id="user_123",
        window_start=now - timedelta(days=30),
        window_end=now,
        behaviors=behaviors,
        conflict_records=[],
    )


# ============================================================================
# Drift Signal Fixtures
# ============================================================================

@pytest.fixture
def sample_drift_signal() -> DriftSignal:
    """Create a sample drift signal."""
    return DriftSignal(
        drift_type=DriftType.TOPIC_EMERGENCE,
        drift_score=0.75,
        affected_targets=["rust", "kubernetes"],
        evidence={
            "emerging_target": "rust",
            "reinforcement_count": 8,
        },
        confidence=0.85,
    )


@pytest.fixture
def drift_signal_factory():
    """Factory to create drift signals with custom attributes."""
    def _create_signal(
        drift_type: DriftType = DriftType.TOPIC_EMERGENCE,
        drift_score: float = 0.75,
        affected_targets: List[str] = None,
        evidence: dict = None,
        confidence: float = 0.85,
    ) -> DriftSignal:
        return DriftSignal(
            drift_type=drift_type,
            drift_score=drift_score,
            affected_targets=affected_targets or ["target1"],
            evidence=evidence or {"test": True},
            confidence=confidence,
        )
    return _create_signal


# ============================================================================
# Mock Database Fixtures
# ============================================================================

@pytest.fixture
def mock_db_connection():
    """Create a mock database connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return conn


@pytest.fixture
def mock_behavior_repo(mock_db_connection):
    """Create a mock behavior repository."""
    from app.db.repositories.behavior_repo import BehaviorRepository
    repo = BehaviorRepository(mock_db_connection)
    return repo
