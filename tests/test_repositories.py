"""
Unit tests for database repositories.

Tests BehaviorRepository, ConflictRepository, and DriftEventRepository
with an in-memory SQLite database or test PostgreSQL instance.
"""

import pytest
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Generator

from app.models.behavior import BehaviorRecord, ConflictRecord
from app.models.drift import DriftEvent, DriftType, DriftSeverity
from app.db.repositories import (
    BehaviorRepository,
    ConflictRepository,
    DriftEventRepository,
)


def now_ts() -> int:
    """Get current timestamp."""
    return int(datetime.now(timezone.utc).timestamp())


def days_ago_ts(days: int) -> int:
    """Get timestamp N days ago."""
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return int(dt.timestamp())


@pytest.fixture
def test_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Create an in-memory SQLite database for testing.
    
    Note: SQLite syntax differs slightly from PostgreSQL,
    but it's sufficient for unit testing repository logic.
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    # Create behavior_snapshots table
    cursor.execute("""
        CREATE TABLE behavior_snapshots (
            user_id TEXT NOT NULL,
            behavior_id TEXT NOT NULL,
            target TEXT NOT NULL,
            intent TEXT NOT NULL,
            context TEXT NOT NULL,
            polarity TEXT NOT NULL,
            credibility REAL NOT NULL,
            reinforcement_count INTEGER NOT NULL,
            state TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            last_seen_at INTEGER NOT NULL,
            snapshot_updated_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, behavior_id)
        )
    """)
    
    # Create conflict_snapshots table
    cursor.execute("""
        CREATE TABLE conflict_snapshots (
            user_id TEXT NOT NULL,
            conflict_id TEXT NOT NULL,
            conflict_type TEXT NOT NULL,
            behavior_id_1 TEXT NOT NULL,
            behavior_id_2 TEXT NOT NULL,
            old_target TEXT,
            new_target TEXT,
            old_polarity TEXT,
            new_polarity TEXT,
            resolution_status TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, conflict_id)
        )
    """)
    
    # Create drift_events table
    cursor.execute("""
        CREATE TABLE drift_events (
            drift_event_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            drift_type TEXT NOT NULL,
            drift_score REAL NOT NULL,
            severity TEXT NOT NULL,
            affected_targets TEXT NOT NULL,
            evidence TEXT NOT NULL,
            confidence REAL NOT NULL,
            reference_window_start INTEGER NOT NULL,
            reference_window_end INTEGER NOT NULL,
            current_window_start INTEGER NOT NULL,
            current_window_end INTEGER NOT NULL,
            detected_at INTEGER NOT NULL,
            acknowledged_at INTEGER,
            behavior_ref_ids TEXT,
            conflict_ref_ids TEXT
        )
    """)
    
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def behavior_repo(test_db) -> BehaviorRepository:
    """Create BehaviorRepository with test database."""
    return BehaviorRepository(test_db)


@pytest.fixture
def conflict_repo(test_db) -> ConflictRepository:
    """Create ConflictRepository with test database."""
    return ConflictRepository(test_db)


@pytest.fixture
def drift_event_repo(test_db) -> DriftEventRepository:
    """Create DriftEventRepository with test database."""
    return DriftEventRepository(test_db)


def insert_test_behavior(conn: sqlite3.Connection, behavior: BehaviorRecord):
    """Helper to insert a test behavior."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO behavior_snapshots (
            user_id, behavior_id, target, intent, context,
            polarity, credibility, reinforcement_count, state,
            created_at, last_seen_at, snapshot_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            behavior.user_id,
            behavior.behavior_id,
            behavior.target,
            behavior.intent,
            behavior.context,
            behavior.polarity,
            behavior.credibility,
            behavior.reinforcement_count,
            behavior.state,
            behavior.created_at,
            behavior.last_seen_at,
            behavior.snapshot_updated_at,
        ),
    )
    conn.commit()


def insert_test_conflict(conn: sqlite3.Connection, conflict: ConflictRecord):
    """Helper to insert a test conflict."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO conflict_snapshots (
            user_id, conflict_id, conflict_type,
            behavior_id_1, behavior_id_2,
            old_target, new_target,
            old_polarity, new_polarity,
            resolution_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conflict.user_id,
            conflict.conflict_id,
            conflict.conflict_type,
            conflict.behavior_id_1,
            conflict.behavior_id_2,
            conflict.old_target,
            conflict.new_target,
            conflict.old_polarity,
            conflict.new_polarity,
            conflict.resolution_status,
            conflict.created_at,
        ),
    )
    conn.commit()


# ============================================================================
# BehaviorRepository Tests
# ============================================================================


class TestBehaviorRepository:
    """Test suite for BehaviorRepository."""

    def test_get_behaviors_in_window_returns_correct_behaviors(
        self, test_db, behavior_repo
    ):
        """Test that get_behaviors_in_window returns behaviors in time range."""
        # Insert test behaviors
        behaviors = [
            BehaviorRecord(
                user_id="user1",
                behavior_id="beh1",
                target="python",
                intent="PREFERENCE",
                context="general",
                polarity="POSITIVE",
                credibility=0.8,
                reinforcement_count=5,
                state="ACTIVE",
                created_at=days_ago_ts(50),
                last_seen_at=days_ago_ts(50),
                snapshot_updated_at=days_ago_ts(50),
            ),
            BehaviorRecord(
                user_id="user1",
                behavior_id="beh2",
                target="javascript",
                intent="PREFERENCE",
                context="web",
                polarity="POSITIVE",
                credibility=0.7,
                reinforcement_count=3,
                state="ACTIVE",
                created_at=days_ago_ts(20),
                last_seen_at=days_ago_ts(20),
                snapshot_updated_at=days_ago_ts(20),
            ),
            BehaviorRecord(
                user_id="user1",
                behavior_id="beh3",
                target="rust",
                intent="PREFERENCE",
                context="systems",
                polarity="POSITIVE",
                credibility=0.9,
                reinforcement_count=2,
                state="ACTIVE",
                created_at=days_ago_ts(5),
                last_seen_at=days_ago_ts(5),
                snapshot_updated_at=days_ago_ts(5),
            ),
        ]
        
        for behavior in behaviors:
            insert_test_behavior(test_db, behavior)
        
        # Query behaviors in window (30-10 days ago)
        result = behavior_repo.get_behaviors_in_window(
            "user1", days_ago_ts(30), days_ago_ts(10)
        )
        
        # Should only return beh2 (20 days ago)
        assert len(result) == 1
        assert result[0].behavior_id == "beh2"
        assert result[0].target == "javascript"

    def test_get_behaviors_in_window_empty(self, test_db, behavior_repo):
        """Test that empty window returns empty list."""
        result = behavior_repo.get_behaviors_in_window(
            "user_nonexistent", days_ago_ts(30), days_ago_ts(10)
        )
        assert result == []

    def test_count_active_behaviors(self, test_db, behavior_repo):
        """Test counting active behaviors."""
        behaviors = [
            BehaviorRecord(
                user_id="user2",
                behavior_id="beh1",
                target="vim",
                intent="PREFERENCE",
                context="editor",
                polarity="POSITIVE",
                credibility=0.8,
                reinforcement_count=5,
                state="ACTIVE",
                created_at=days_ago_ts(10),
                last_seen_at=days_ago_ts(10),
                snapshot_updated_at=days_ago_ts(10),
            ),
            BehaviorRecord(
                user_id="user2",
                behavior_id="beh2",
                target="emacs",
                intent="PREFERENCE",
                context="editor",
                polarity="NEGATIVE",
                credibility=0.6,
                reinforcement_count=2,
                state="SUPERSEDED",  # Not active
                created_at=days_ago_ts(20),
                last_seen_at=days_ago_ts(20),
                snapshot_updated_at=days_ago_ts(20),
            ),
            BehaviorRecord(
                user_id="user2",
                behavior_id="beh3",
                target="vscode",
                intent="PREFERENCE",
                context="editor",
                polarity="POSITIVE",
                credibility=0.7,
                reinforcement_count=3,
                state="ACTIVE",
                created_at=days_ago_ts(5),
                last_seen_at=days_ago_ts(5),
                snapshot_updated_at=days_ago_ts(5),
            ),
        ]
        
        for behavior in behaviors:
            insert_test_behavior(test_db, behavior)
        
        count = behavior_repo.count_active_behaviors("user2")
        assert count == 2  # Only beh1 and beh3 are active

    def test_get_earliest_behavior_date(self, test_db, behavior_repo):
        """Test getting earliest behavior timestamp."""
        behaviors = [
            BehaviorRecord(
                user_id="user3",
                behavior_id="beh1",
                target="docker",
                intent="PREFERENCE",
                context="devops",
                polarity="POSITIVE",
                credibility=0.8,
                reinforcement_count=5,
                state="ACTIVE",
                created_at=days_ago_ts(100),  # Oldest
                last_seen_at=days_ago_ts(100),
                snapshot_updated_at=days_ago_ts(100),
            ),
            BehaviorRecord(
                user_id="user3",
                behavior_id="beh2",
                target="kubernetes",
                intent="PREFERENCE",
                context="devops",
                polarity="POSITIVE",
                credibility=0.7,
                reinforcement_count=3,
                state="ACTIVE",
                created_at=days_ago_ts(50),
                last_seen_at=days_ago_ts(50),
                snapshot_updated_at=days_ago_ts(50),
            ),
        ]
        
        for behavior in behaviors:
            insert_test_behavior(test_db, behavior)
        
        earliest = behavior_repo.get_earliest_behavior_date("user3")
        assert earliest == days_ago_ts(100)

    def test_get_earliest_behavior_date_no_data(self, test_db, behavior_repo):
        """Test earliest date with no behaviors."""
        earliest = behavior_repo.get_earliest_behavior_date("user_nonexistent")
        assert earliest is None

    def test_get_behaviors_by_target(self, test_db, behavior_repo):
        """Test filtering behaviors by target."""
        behaviors = [
            BehaviorRecord(
                user_id="user4",
                behavior_id="beh1",
                target="python",
                intent="PREFERENCE",
                context="general",
                polarity="POSITIVE",
                credibility=0.8,
                reinforcement_count=5,
                state="ACTIVE",
                created_at=days_ago_ts(30),
                last_seen_at=days_ago_ts(1),
                snapshot_updated_at=days_ago_ts(1),
            ),
            BehaviorRecord(
                user_id="user4",
                behavior_id="beh2",
                target="python",
                intent="PREFERENCE",
                context="data science",
                polarity="POSITIVE",
                credibility=0.9,
                reinforcement_count=7,
                state="ACTIVE",
                created_at=days_ago_ts(20),
                last_seen_at=days_ago_ts(2),
                snapshot_updated_at=days_ago_ts(2),
            ),
            BehaviorRecord(
                user_id="user4",
                behavior_id="beh3",
                target="javascript",
                intent="PREFERENCE",
                context="web",
                polarity="POSITIVE",
                credibility=0.7,
                reinforcement_count=3,
                state="ACTIVE",
                created_at=days_ago_ts(10),
                last_seen_at=days_ago_ts(3),
                snapshot_updated_at=days_ago_ts(3),
            ),
        ]
        
        for behavior in behaviors:
            insert_test_behavior(test_db, behavior)
        
        python_behaviors = behavior_repo.get_behaviors_by_target("user4", "python")
        assert len(python_behaviors) == 2
        assert all(b.target == "python" for b in python_behaviors)


# ============================================================================
# ConflictRepository Tests
# ============================================================================


class TestConflictRepository:
    """Test suite for ConflictRepository."""

    def test_get_conflicts_in_window(self, test_db, conflict_repo):
        """Test retrieving conflicts in time window."""
        conflicts = [
            ConflictRecord(
                user_id="user5",
                conflict_id="conf1",
                conflict_type="RESOLVABLE",
                behavior_id_1="beh1",
                behavior_id_2="beh2",
                old_target="remote work",
                new_target="remote work",
                old_polarity="POSITIVE",
                new_polarity="NEGATIVE",
                resolution_status="AUTO_RESOLVED",
                created_at=days_ago_ts(25),
            ),
            ConflictRecord(
                user_id="user5",
                conflict_id="conf2",
                conflict_type="USER_DECISION_NEEDED",
                behavior_id_1="beh3",
                behavior_id_2="beh4",
                old_target="vim",
                new_target="vscode",
                old_polarity="POSITIVE",
                new_polarity="POSITIVE",
                resolution_status="PENDING",
                created_at=days_ago_ts(10),
            ),
        ]
        
        for conflict in conflicts:
            insert_test_conflict(test_db, conflict)
        
        # Query window (30-15 days ago)
        result = conflict_repo.get_conflicts_in_window(
            "user5", days_ago_ts(30), days_ago_ts(15)
        )
        
        # Should only return conf1
        assert len(result) == 1
        assert result[0].conflict_id == "conf1"

    def test_get_polarity_reversals(self, test_db, conflict_repo):
        """Test filtering to polarity reversals only."""
        conflicts = [
            ConflictRecord(
                user_id="user6",
                conflict_id="conf1",
                conflict_type="RESOLVABLE",
                behavior_id_1="beh1",
                behavior_id_2="beh2",
                old_target="topic1",
                new_target="topic1",
                old_polarity="POSITIVE",
                new_polarity="NEGATIVE",  # Reversal!
                resolution_status="AUTO_RESOLVED",
                created_at=days_ago_ts(20),
            ),
            ConflictRecord(
                user_id="user6",
                conflict_id="conf2",
                conflict_type="USER_DECISION_NEEDED",
                behavior_id_1="beh3",
                behavior_id_2="beh4",
                old_target="topic2",
                new_target="topic3",
                old_polarity="POSITIVE",
                new_polarity="POSITIVE",  # No reversal
                resolution_status="PENDING",
                created_at=days_ago_ts(15),
            ),
        ]
        
        for conflict in conflicts:
            insert_test_conflict(test_db, conflict)
        
        reversals = conflict_repo.get_polarity_reversals(
            "user6", days_ago_ts(30), days_ago_ts(10)
        )
        
        assert len(reversals) == 1
        assert reversals[0].conflict_id == "conf1"
        assert reversals[0].old_polarity == "POSITIVE"
        assert reversals[0].new_polarity == "NEGATIVE"

    def test_get_target_migrations(self, test_db, conflict_repo):
        """Test filtering to target migrations only."""
        conflicts = [
            ConflictRecord(
                user_id="user7",
                conflict_id="conf1",
                conflict_type="RESOLVABLE",
                behavior_id_1="beh1",
                behavior_id_2="beh2",
                old_target="topic1",
                new_target="topic1",  # Same target
                old_polarity="POSITIVE",
                new_polarity="NEGATIVE",
                resolution_status="AUTO_RESOLVED",
                created_at=days_ago_ts(20),
            ),
            ConflictRecord(
                user_id="user7",
                conflict_id="conf2",
                conflict_type="USER_DECISION_NEEDED",
                behavior_id_1="beh3",
                behavior_id_2="beh4",
                old_target="vim",
                new_target="vscode",  # Migration!
                old_polarity="POSITIVE",
                new_polarity="POSITIVE",
                resolution_status="PENDING",
                created_at=days_ago_ts(15),
            ),
        ]
        
        for conflict in conflicts:
            insert_test_conflict(test_db, conflict)
        
        migrations = conflict_repo.get_target_migrations(
            "user7", days_ago_ts(30), days_ago_ts(10)
        )
        
        assert len(migrations) == 1
        assert migrations[0].conflict_id == "conf2"
        assert migrations[0].old_target == "vim"
        assert migrations[0].new_target == "vscode"


# ============================================================================
# DriftEventRepository Tests
# ============================================================================


class TestDriftEventRepository:
    """Test suite for DriftEventRepository."""

    def test_insert_drift_event(self, test_db, drift_event_repo):
        """Test inserting a drift event."""
        event = DriftEvent(
            user_id="user8",
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.85,
            confidence=0.9,
            severity=DriftSeverity.STRONG_DRIFT,
            affected_targets=["pytorch", "tensorflow"],
            evidence={"cluster_size": 2, "is_domain_emergence": True},
            reference_window_start=days_ago_ts(60),
            reference_window_end=days_ago_ts(30),
            current_window_start=days_ago_ts(30),
            current_window_end=now_ts(),
            detected_at=now_ts(),
        )
        
        drift_event_id = drift_event_repo.insert(event)
        
        assert drift_event_id is not None
        assert drift_event_id.startswith("drift_")

    def test_get_by_id(self, test_db, drift_event_repo):
        """Test retrieving drift event by ID."""
        event = DriftEvent(
            user_id="user9",
            drift_type=DriftType.PREFERENCE_REVERSAL,
            drift_score=0.75,
            confidence=0.85,
            severity=DriftSeverity.MODERATE_DRIFT,
            affected_targets=["remote work"],
            evidence={"old_polarity": "POSITIVE", "new_polarity": "NEGATIVE"},
            reference_window_start=days_ago_ts(60),
            reference_window_end=days_ago_ts(30),
            current_window_start=days_ago_ts(30),
            current_window_end=now_ts(),
            detected_at=now_ts(),
            drift_event_id="test_event_123",
        )
        
        drift_event_repo.insert(event)
        
        # Retrieve by ID
        retrieved = drift_event_repo.get_by_id("test_event_123")
        
        assert retrieved is not None
        assert retrieved.drift_event_id == "test_event_123"
        assert retrieved.user_id == "user9"
        assert retrieved.drift_type == DriftType.PREFERENCE_REVERSAL
        assert retrieved.drift_score == 0.75

    def test_get_by_id_not_found(self, test_db, drift_event_repo):
        """Test get_by_id with non-existent ID."""
        result = drift_event_repo.get_by_id("nonexistent_id")
        assert result is None

    def test_get_by_user(self, test_db, drift_event_repo):
        """Test retrieving drift events by user."""
        events = [
            DriftEvent(
                user_id="user10",
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=0.85,
                confidence=0.9,
                severity=DriftSeverity.STRONG_DRIFT,
                affected_targets=["ml"],
                evidence={},
                reference_window_start=days_ago_ts(60),
                reference_window_end=days_ago_ts(30),
                current_window_start=days_ago_ts(30),
                current_window_end=now_ts(),
                detected_at=days_ago_ts(5),
                drift_event_id="event1",
            ),
            DriftEvent(
                user_id="user10",
                drift_type=DriftType.TOPIC_ABANDONMENT,
                drift_score=0.70,
                confidence=0.8,
                severity=DriftSeverity.MODERATE_DRIFT,
                affected_targets=["react"],
                evidence={},
                reference_window_start=days_ago_ts(60),
                reference_window_end=days_ago_ts(30),
                current_window_start=days_ago_ts(30),
                current_window_end=now_ts(),
                detected_at=days_ago_ts(2),
                drift_event_id="event2",
            ),
        ]
        
        for event in events:
            drift_event_repo.insert(event)
        
        # Retrieve all events for user
        user_events = drift_event_repo.get_by_user("user10")
        
        assert len(user_events) == 2
        # Should be sorted by detected_at DESC
        assert user_events[0].drift_event_id == "event2"  # More recent
        assert user_events[1].drift_event_id == "event1"

    def test_get_by_user_with_filters(self, test_db, drift_event_repo):
        """Test get_by_user with drift_type filter."""
        events = [
            DriftEvent(
                user_id="user11",
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=0.85,
                confidence=0.9,
                severity=DriftSeverity.STRONG_DRIFT,
                affected_targets=["ml"],
                evidence={},
                reference_window_start=days_ago_ts(60),
                reference_window_end=days_ago_ts(30),
                current_window_start=days_ago_ts(30),
                current_window_end=now_ts(),
                detected_at=now_ts(),
                drift_event_id="event1",
            ),
            DriftEvent(
                user_id="user11",
                drift_type=DriftType.TOPIC_ABANDONMENT,
                drift_score=0.70,
                confidence=0.8,
                severity=DriftSeverity.MODERATE_DRIFT,
                affected_targets=["react"],
                evidence={},
                reference_window_start=days_ago_ts(60),
                reference_window_end=days_ago_ts(30),
                current_window_start=days_ago_ts(30),
                current_window_end=now_ts(),
                detected_at=now_ts(),
                drift_event_id="event2",
            ),
        ]
        
        for event in events:
            drift_event_repo.insert(event)
        
        # Filter to only TOPIC_EMERGENCE
        filtered = drift_event_repo.get_by_user(
            "user11", drift_type=DriftType.TOPIC_EMERGENCE
        )
        
        assert len(filtered) == 1
        assert filtered[0].drift_type == DriftType.TOPIC_EMERGENCE

    def test_get_latest_detection_time(self, test_db, drift_event_repo):
        """Test getting latest detection timestamp."""
        events = [
            DriftEvent(
                user_id="user12",
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=0.85,
                confidence=0.9,
                severity=DriftSeverity.STRONG_DRIFT,
                affected_targets=["ml"],
                evidence={},
                reference_window_start=days_ago_ts(60),
                reference_window_end=days_ago_ts(30),
                current_window_start=days_ago_ts(30),
                current_window_end=now_ts(),
                detected_at=days_ago_ts(10),
                drift_event_id="event1",
            ),
            DriftEvent(
                user_id="user12",
                drift_type=DriftType.TOPIC_ABANDONMENT,
                drift_score=0.70,
                confidence=0.8,
                severity=DriftSeverity.MODERATE_DRIFT,
                affected_targets=["react"],
                evidence={},
                reference_window_start=days_ago_ts(60),
                reference_window_end=days_ago_ts(30),
                current_window_start=days_ago_ts(30),
                current_window_end=now_ts(),
                detected_at=days_ago_ts(3),  # Most recent
                drift_event_id="event2",
            ),
        ]
        
        for event in events:
            drift_event_repo.insert(event)
        
        latest = drift_event_repo.get_latest_detection_time("user12")
        assert latest == days_ago_ts(3)

    def test_update_acknowledged(self, test_db, drift_event_repo):
        """Test acknowledging a drift event."""
        event = DriftEvent(
            user_id="user13",
            drift_type=DriftType.PREFERENCE_REVERSAL,
            drift_score=0.75,
            confidence=0.85,
            severity=DriftSeverity.MODERATE_DRIFT,
            affected_targets=["topic"],
            evidence={},
            reference_window_start=days_ago_ts(60),
            reference_window_end=days_ago_ts(30),
            current_window_start=days_ago_ts(30),
            current_window_end=now_ts(),
            detected_at=now_ts(),
            drift_event_id="ack_test",
        )
        
        drift_event_repo.insert(event)
        
        # Acknowledge the event
        ack_ts = now_ts()
        result = drift_event_repo.update_acknowledged("ack_test", ack_ts)
        
        assert result is True
        
        # Verify acknowledgment was set
        retrieved = drift_event_repo.get_by_id("ack_test")
        assert retrieved.acknowledged_at == ack_ts

    def test_update_acknowledged_not_found(self, test_db, drift_event_repo):
        """Test acknowledging non-existent event."""
        result = drift_event_repo.update_acknowledged("nonexistent", now_ts())
        assert result is False
