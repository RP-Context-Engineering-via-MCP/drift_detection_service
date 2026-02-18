"""
Test configuration and fixtures for drift detection tests.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from app.models.behavior import BehaviorRecord, ConflictRecord
from app.models.snapshot import BehaviorSnapshot


# ─── Time Utilities ──────────────────────────────────────────────────────

def now() -> int:
    """Get current timestamp as integer."""
    return int(datetime.now(timezone.utc).timestamp())


def days_ago(n: int) -> int:
    """
    Get timestamp for n days ago.
    
    Args:
        n: Number of days in the past
        
    Returns:
        Unix timestamp
    """
    dt = datetime.now(timezone.utc) - timedelta(days=n)
    return int(dt.timestamp())


def days_from_now(n: int) -> int:
    """
    Get timestamp for n days in the future.
    
    Args:
        n: Number of days in the future
        
    Returns:
        Unix timestamp
    """
    dt = datetime.now(timezone.utc) + timedelta(days=n)
    return int(dt.timestamp())


# ─── Factory Functions ───────────────────────────────────────────────────

def make_behavior(**kwargs) -> BehaviorRecord:
    """
    Factory for test BehaviorRecord instances with sensible defaults.
    
    Usage:
        behavior = make_behavior(target="python", reinforcement_count=5)
    
    Returns:
        BehaviorRecord with default or overridden values
    """
    # Generate unique behavior_id using UUID to avoid duplicates
    unique_id = str(uuid.uuid4())[:8]
    
    defaults = {
        "user_id": "test_user",
        "behavior_id": f"beh_{now()}_{unique_id}",
        "target": "python",
        "intent": "PREFERENCE",
        "context": "general",
        "polarity": "POSITIVE",
        "credibility": 0.75,
        "reinforcement_count": 1,
        "state": "ACTIVE",
        "created_at": days_ago(30),
        "last_seen_at": days_ago(1),
        "snapshot_updated_at": days_ago(1),
    }
    
    # Override defaults with provided kwargs
    defaults.update(kwargs)
    
    return BehaviorRecord(**defaults)


def make_conflict(**kwargs) -> ConflictRecord:
    """
    Factory for test ConflictRecord instances with sensible defaults.
    
    Usage:
        conflict = make_conflict(old_polarity="POSITIVE", new_polarity="NEGATIVE")
    
    Returns:
        ConflictRecord with default or overridden values
    """
    # Generate unique IDs using UUID to avoid duplicates
    unique_id = str(uuid.uuid4())[:8]
    
    defaults = {
        "user_id": "test_user",
        "conflict_id": f"conf_{now()}_{unique_id}",
        "behavior_id_1": f"beh1_{now()}_{unique_id}",
        "behavior_id_2": f"beh2_{now()}_{unique_id}",
        "conflict_type": "RESOLVABLE",
        "resolution_status": "AUTO_RESOLVED",
        "old_polarity": None,
        "new_polarity": None,
        "old_target": None,
        "new_target": None,
        "created_at": days_ago(1),
    }
    
    # Override defaults with provided kwargs
    defaults.update(kwargs)
    
    return ConflictRecord(**defaults)


def make_snapshot(
    user_id: str = "test_user",
    behaviors: list = None,
    conflicts: list = None,
    days_ago_start: int = 30,
    days_ago_end: int = 0,
) -> BehaviorSnapshot:
    """
    Factory for test BehaviorSnapshot instances.
    
    Args:
        user_id: User ID for the snapshot
        behaviors: List of BehaviorRecord objects (creates default if None)
        conflicts: List of ConflictRecord objects
        days_ago_start: How many days ago the window starts
        days_ago_end: How many days ago the window ends (0 = now)
    
    Returns:
        BehaviorSnapshot with default or provided data
    """
    now_dt = datetime.now(timezone.utc)
    window_start = now_dt - timedelta(days=days_ago_start)
    window_end = now_dt - timedelta(days=days_ago_end)
    
    if behaviors is None:
        behaviors = [
            make_behavior(user_id=user_id, target="python"),
            make_behavior(user_id=user_id, target="javascript"),
        ]
    
    if conflicts is None:
        conflicts = []
    
    return BehaviorSnapshot(
        user_id=user_id,
        window_start=window_start,
        window_end=window_end,
        behaviors=behaviors,
        conflict_records=conflicts,
    )


# ─── Test Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def sample_behavior() -> BehaviorRecord:
    """Fixture providing a sample behavior record."""
    return make_behavior()


@pytest.fixture
def sample_conflict() -> ConflictRecord:
    """Fixture providing a sample conflict record."""
    return make_conflict(
        old_polarity="POSITIVE",
        new_polarity="NEGATIVE",
    )


@pytest.fixture
def sample_snapshot() -> BehaviorSnapshot:
    """Fixture providing a sample behavior snapshot."""
    return make_snapshot()


@pytest.fixture
def empty_snapshot() -> BehaviorSnapshot:
    """Fixture providing an empty behavior snapshot."""
    return make_snapshot(behaviors=[], conflicts=[])
