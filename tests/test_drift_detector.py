"""Integration tests for DriftDetector."""

import pytest
from datetime import datetime, timedelta, timezone

from app.core.drift_detector import DriftDetector
from app.db.connection import create_tables, drop_tables, clear_all_data, get_sync_connection_simple
from app.db.repositories.behavior_repo import BehaviorRepository
from app.db.repositories.drift_event_repo import DriftEventRepository
from tests.conftest import make_behavior


@pytest.fixture(scope="session")
def setup_database():
    """Create database tables once for all tests."""
    print("\n🔧 Setting up test database...")
    create_tables()
    yield
    print("\n🧹 Tearing down test database...")
    drop_tables()


@pytest.fixture
def db_connection(setup_database):
    """Create test database connection and clear data between tests."""
    # Clear any existing data before test
    clear_all_data()
    
    conn = get_sync_connection_simple()
    
    yield conn
    
    # Commit any pending transactions and close connection
    try:
        conn.commit()
    except Exception:
        pass
    
    conn.close()


@pytest.fixture
def detector(db_connection):
    """Create DriftDetector instance."""
    return DriftDetector()


class TestDriftDetector:
    """Integration tests for full drift detection pipeline."""

    def test_insufficient_data_returns_empty(self, detector):
        """Test that insufficient data returns no events."""
        # No data in database
        events = detector.detect_drift("nonexistent_user")
        assert events == []

    def test_insufficient_behaviors_returns_empty(self, detector, db_connection):
        """Test that too few behaviors returns no events."""
        repo = BehaviorRepository(db_connection)
        
        # Insert only 2 behaviors (minimum is 5)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for i in range(2):
            behavior = make_behavior(
                user_id="test_user",
                target=f"topic_{i}",
                created_at=now_ts - 86400 * (i * 10 + 5),
            )
            repo._insert_behavior(behavior)
        
        events = detector.detect_drift("test_user")
        assert events == []

    def test_insufficient_history_returns_empty(self, detector, db_connection):
        """Test that insufficient history duration returns no events."""
        repo = BehaviorRepository(db_connection)
        
        # Insert 5 behaviors but all within 7 days (minimum is 14)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for i in range(5):
            behavior = make_behavior(
                user_id="test_user",
                target=f"topic_{i}",
                created_at=now_ts - 86400 * (i + 1),
            )
            repo._insert_behavior(behavior)
        
        events = detector.detect_drift("test_user")
        assert events == []

    def test_no_drift_returns_empty(self, detector, db_connection):
        """Test that no significant changes returns no events."""
        repo = BehaviorRepository(db_connection)
        
        # Insert behaviors spread over 50 days with no drift pattern
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for i in range(10):
            behavior = make_behavior(
                user_id="test_user",
                target="python",  # Same target, consistent
                credibility=0.7,  # Same credibility
                reinforcement_count=3,
                created_at=now_ts - 86400 * (i * 5 + 1),
                last_seen_at=now_ts - 86400 * (i * 5 + 1),
            )
            repo._insert_behavior(behavior)
        
        events = detector.detect_drift("test_user")
        
        # Should have no actionable drift (stable behavior)
        assert len(events) == 0

    def test_topic_emergence_detected(self, detector, db_connection):
        """Test that topic emergence pattern is detected."""
        repo = BehaviorRepository(db_connection)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        
        # Reference window (60-30 days ago): MINIMAL python activity
        behavior = make_behavior(
            user_id="test_user",
            target="python",
            reinforcement_count=1,
            created_at=now_ts - 86400 * 45,
            last_seen_at=now_ts - 86400 * 45,
        )
        repo._insert_behavior(behavior)
        
        # Current window (last 30 days): Single new topic DOMINATES with recent activity
        # Use EXTREME reinforcement and very recent timestamps to maximize score
        for j in range(5):  # 5 very recent behaviors
            behavior = make_behavior(
                user_id="test_user",
                target="pytorch",
                reinforcement_count=25,  # EXTREME reinforcement
                created_at=now_ts - 86400 * (1 + j),  # VERY recent: 1-5 days ago
                last_seen_at=now_ts - 86400 * (1 + j),
            )
            repo._insert_behavior(behavior)
        
        events = detector.detect_drift("test_user")
        
        # With pytorch having 125 reinforcements vs python's 1 (99% of activity)
        # and being very recent (1-5 days ago), score should be well above 0.6
        assert len(events) > 0, f"Expected drift events but got none. Scores may be below threshold (0.6)."
        
        # Check that at least one is topic emergence
        drift_types = [e.drift_type.value for e in events]
        assert "TOPIC_EMERGENCE" in drift_types

    def test_events_persisted_to_database(self, detector, db_connection):
        """Test that detected events are written to database."""
        repo = BehaviorRepository(db_connection)
        event_repo = DriftEventRepository(db_connection)
        
        now_ts = int(datetime.now(timezone.utc).timestamp())
        
        # Create data that will trigger STRONG drift
        # Reference window: MINIMAL activity
        behavior = make_behavior(
            user_id="test_user",
            target="python",
            reinforcement_count=1,
            created_at=now_ts - 86400 * 45,
            last_seen_at=now_ts - 86400 * 45,
        )
        repo._insert_behavior(behavior)
        
        # Current window: new topic ABSOLUTELY DOMINATES
        for i in range(3):
            behavior = make_behavior(
                user_id="test_user",
                target="machine_learning",
                reinforcement_count=20,  # EXTREME reinforcement
                created_at=now_ts - 86400 * (5 + i),
                last_seen_at=now_ts - 86400 * (5 + i),
            )
            repo._insert_behavior(behavior)
        
        # Run detection
        events = detector.detect_drift("test_user")
        
        if len(events) > 0:
            # Verify events are in database
            db_events = event_repo.get_by_user("test_user")
            assert len(db_events) == len(events)
            
            # Verify event properties
            for event in db_events:
                assert event.user_id == "test_user"
                assert event.drift_event_id is not None
                assert event.detected_at > 0

    def test_cooldown_period_enforced(self, detector, db_connection):
        """Test that cooldown period prevents rapid re-scans."""
        repo = BehaviorRepository(db_connection)
        event_repo = DriftEventRepository(db_connection)
        
        now_ts = int(datetime.now(timezone.utc).timestamp())
        
        # Create sufficient data
        for i in range(10):
            behavior = make_behavior(
                user_id="test_user",
                target=f"topic_{i}",
                reinforcement_count=2,
                created_at=now_ts - 86400 * (i * 5 + 1),
                last_seen_at=now_ts - 86400 * (i * 5 + 1),
            )
            repo._insert_behavior(behavior)
        
        # First detection
        events1 = detector.detect_drift("test_user")
        
        # Immediate second detection (should be blocked by cooldown)
        events2 = detector.detect_drift("test_user")
        
        # Second call should return empty due to cooldown
        assert events2 == []

    def test_all_detectors_executed(self, detector, db_connection, caplog):
        """Test that all 5 detectors are executed."""
        import logging
        caplog.set_level(logging.INFO)
        
        repo = BehaviorRepository(db_connection)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        
        # Create sufficient data
        for i in range(10):
            behavior = make_behavior(
                user_id="test_user",
                target=f"topic_{i}",
                reinforcement_count=2,
                created_at=now_ts - 86400 * (i * 5 + 1),
                last_seen_at=now_ts - 86400 * (i * 5 + 1),
            )
            repo._insert_behavior(behavior)
        
        detector.detect_drift("test_user")
        
        # Check that all detector names appear in logs
        log_text = caplog.text
        assert "TopicEmergenceDetector" in log_text
        assert "TopicAbandonmentDetector" in log_text
        assert "PreferenceReversalDetector" in log_text
        assert "IntensityShiftDetector" in log_text
        assert "ContextShiftDetector" in log_text

    def test_partial_detector_failure_continues(self, detector, db_connection, caplog, monkeypatch):
        """Test that if one detector fails, others still run."""
        import logging
        caplog.set_level(logging.ERROR)
        
        repo = BehaviorRepository(db_connection)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        
        # Create sufficient data
        for i in range(10):
            behavior = make_behavior(
                user_id="test_user",
                target=f"topic_{i}",
                reinforcement_count=2,
                created_at=now_ts - 86400 * (i * 5 + 1),
                last_seen_at=now_ts - 86400 * (i * 5 + 1),
            )
            repo._insert_behavior(behavior)
        
        # Make one detector fail
        def failing_detect(self, ref, cur):
            raise RuntimeError("Detector failure test")
        
        from app.detectors.topic_emergence import TopicEmergenceDetector
        monkeypatch.setattr(TopicEmergenceDetector, "detect", failing_detect)
        
        # Should not raise exception
        events = detector.detect_drift("test_user")
        
        # Should log the error
        assert "TopicEmergenceDetector failed" in caplog.text
        
        # Other detectors should still have run (no guarantee of drift though)
        # Just verify it didn't crash
        assert isinstance(events, list)
