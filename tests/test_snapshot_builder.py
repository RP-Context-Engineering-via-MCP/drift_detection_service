"""Tests for SnapshotBuilder."""

import pytest
from datetime import datetime, timedelta, timezone

from app.core.snapshot_builder import SnapshotBuilder
from app.db.connection import create_tables, drop_tables, clear_all_data, get_sync_connection_simple
from tests.conftest import make_behavior, make_conflict


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
def snapshot_builder(db_connection):
    """Create SnapshotBuilder instance."""
    return SnapshotBuilder()


class TestSnapshotBuilder:
    """Test snapshot building from database."""

    def test_build_snapshot_empty(self, snapshot_builder):
        """Test building snapshot with no data returns empty snapshot."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        
        snapshot = snapshot_builder.build_snapshot("test_user", start, now)
        
        assert snapshot.user_id == "test_user"
        assert snapshot.window_start == start
        assert snapshot.window_end == now
        assert len(snapshot.behaviors) == 0
        assert len(snapshot.conflict_records) == 0
        assert len(snapshot.get_targets()) == 0

    def test_build_snapshot_with_behaviors(self, snapshot_builder, db_connection):
        """Test building snapshot with behaviors in window."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        
        # Insert behaviors into database
        behavior1 = make_behavior(
            user_id="test_user",
            target="python",
            created_at=int((now - timedelta(days=10)).timestamp()),
        )
        behavior2 = make_behavior(
            user_id="test_user",
            target="javascript",
            created_at=int((now - timedelta(days=5)).timestamp()),
        )
        
        # Insert using repository
        from app.db.repositories.behavior_repo import BehaviorRepository
        repo = BehaviorRepository(db_connection)
        repo._insert_behavior(behavior1)  # Helper method for testing
        repo._insert_behavior(behavior2)
        
        snapshot = snapshot_builder.build_snapshot("test_user", start, now)
        
        assert len(snapshot.behaviors) == 2
        assert "python" in snapshot.get_targets()
        assert "javascript" in snapshot.get_targets()

    def test_build_snapshot_filters_by_window(self, snapshot_builder, db_connection):
        """Test that only behaviors in window are included."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)
        window_end = now - timedelta(days=20)
        
        # Behavior inside window
        behavior_in = make_behavior(
            user_id="test_user",
            target="python",
            created_at=int((now - timedelta(days=25)).timestamp()),
        )
        # Behavior outside window (too recent)
        behavior_out = make_behavior(
            user_id="test_user",
            target="javascript",
            created_at=int((now - timedelta(days=5)).timestamp()),
        )
        
        from app.db.repositories.behavior_repo import BehaviorRepository
        repo = BehaviorRepository(db_connection)
        repo._insert_behavior(behavior_in)
        repo._insert_behavior(behavior_out)
        
        snapshot = snapshot_builder.build_snapshot("test_user", window_start, window_end)
        
        assert len(snapshot.behaviors) == 1
        assert "python" in snapshot.get_targets()
        assert "javascript" not in snapshot.get_targets()

    def test_build_reference_and_current(self, snapshot_builder):
        """Test building reference and current snapshots."""
        reference, current = snapshot_builder.build_reference_and_current("test_user")
        
        # Check that snapshots exist
        assert reference.user_id == "test_user"
        assert current.user_id == "test_user"
        
        # Check that windows don't overlap
        assert reference.window_end <= current.window_start
        
        # Check window durations are correct (approximately)
        from app.config import get_settings
        settings = get_settings()
        
        ref_duration = (reference.window_end - reference.window_start).days
        expected_ref_duration = settings.reference_window_start_days - settings.reference_window_end_days
        assert abs(ref_duration - expected_ref_duration) <= 1  # Allow 1 day tolerance
        
        cur_duration = (current.window_end - current.window_start).days
        assert abs(cur_duration - settings.current_window_days) <= 1

    def test_validate_sufficient_data_empty(self, snapshot_builder):
        """Test validation fails with no data."""
        result = snapshot_builder.validate_sufficient_data("nonexistent_user")
        assert result is False

    def test_validate_sufficient_data_insufficient_behaviors(
        self, snapshot_builder, db_connection
    ):
        """Test validation fails with too few behaviors."""
        # Insert only 2 behaviors (minimum is 5)
        from app.db.repositories.behavior_repo import BehaviorRepository
        repo = BehaviorRepository(db_connection)
        
        now_ts = int(datetime.now(timezone.utc).timestamp())
        behavior1 = make_behavior(user_id="test_user", created_at=now_ts - 86400*20)
        behavior2 = make_behavior(user_id="test_user", created_at=now_ts - 86400*15)
        
        repo._insert_behavior(behavior1)
        repo._insert_behavior(behavior2)
        
        result = snapshot_builder.validate_sufficient_data("test_user")
        assert result is False

    def test_validate_sufficient_data_insufficient_history(
        self, snapshot_builder, db_connection
    ):
        """Test validation fails with insufficient history duration."""
        from app.db.repositories.behavior_repo import BehaviorRepository
        repo = BehaviorRepository(db_connection)
        
        # Insert 5 behaviors but all recent (within 7 days, minimum is 14)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for i in range(5):
            behavior = make_behavior(
                user_id="test_user",
                target=f"topic_{i}",
                created_at=now_ts - 86400 * (i + 1),  # Last 5 days
            )
            repo._insert_behavior(behavior)
        
        result = snapshot_builder.validate_sufficient_data("test_user")
        assert result is False

    def test_validate_sufficient_data_passes(self, snapshot_builder, db_connection):
        """Test validation passes with sufficient data."""
        from app.db.repositories.behavior_repo import BehaviorRepository
        repo = BehaviorRepository(db_connection)
        
        # Insert 5 behaviors spread over 20 days
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for i in range(5):
            behavior = make_behavior(
                user_id="test_user",
                target=f"topic_{i}",
                created_at=now_ts - 86400 * (i * 4 + 1),  # Days 1, 5, 9, 13, 17
            )
            repo._insert_behavior(behavior)
        
        result = snapshot_builder.validate_sufficient_data("test_user")
        assert result is True
