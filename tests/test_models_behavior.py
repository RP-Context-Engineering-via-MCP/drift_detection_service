"""
Tests for behavior and conflict data models.
"""

import pytest
from datetime import datetime

from app.models.behavior import BehaviorRecord, ConflictRecord
from tests.conftest import make_behavior, make_conflict, days_ago


class TestBehaviorRecord:
    """Tests for BehaviorRecord data model."""
    
    def test_create_behavior_with_defaults(self):
        """Test creating a behavior with all required fields."""
        behavior = make_behavior()
        
        assert behavior.user_id == "test_user"
        assert behavior.target == "python"
        assert behavior.intent == "PREFERENCE"
        assert behavior.state == "ACTIVE"
        assert 0.0 <= behavior.credibility <= 1.0
        assert behavior.reinforcement_count >= 0
    
    def test_behavior_validation_credibility(self):
        """Test that credibility must be between 0 and 1."""
        with pytest.raises(ValueError, match="Credibility must be between"):
            make_behavior(credibility=1.5)
        
        with pytest.raises(ValueError, match="Credibility must be between"):
            make_behavior(credibility=-0.1)
    
    def test_behavior_validation_state(self):
        """Test that state must be ACTIVE or SUPERSEDED."""
        with pytest.raises(ValueError, match="State must be ACTIVE or SUPERSEDED"):
            make_behavior(state="INVALID")
    
    def test_behavior_validation_polarity(self):
        """Test that polarity must be POSITIVE or NEGATIVE."""
        with pytest.raises(ValueError, match="Polarity must be POSITIVE or NEGATIVE"):
            make_behavior(polarity="NEUTRAL")
    
    def test_behavior_to_dict(self):
        """Test converting behavior to dictionary."""
        behavior = make_behavior(target="typescript", reinforcement_count=3)
        data = behavior.to_dict()
        
        assert data["target"] == "typescript"
        assert data["reinforcement_count"] == 3
        assert "user_id" in data
        assert "behavior_id" in data
    
    def test_behavior_from_dict(self):
        """Test creating behavior from dictionary."""
        data = {
            "user_id": "user123",
            "behavior_id": "beh123",
            "target": "rust",
            "intent": "SKILL",
            "context": "backend",
            "polarity": "POSITIVE",
            "credibility": 0.85,
            "reinforcement_count": 7,
            "state": "ACTIVE",
            "created_at": days_ago(10),
            "last_seen_at": days_ago(1),
            "snapshot_updated_at": days_ago(1),
        }
        
        behavior = BehaviorRecord.from_dict(data)
        
        assert behavior.user_id == "user123"
        assert behavior.target == "rust"
        assert behavior.reinforcement_count == 7
        assert behavior.credibility == 0.85
    
    def test_behavior_is_active_property(self):
        """Test is_active property."""
        active = make_behavior(state="ACTIVE")
        superseded = make_behavior(state="SUPERSEDED")
        
        assert active.is_active is True
        assert active.is_superseded is False
        assert superseded.is_active is False
        assert superseded.is_superseded is True
    
    def test_behavior_datetime_properties(self):
        """Test datetime conversion properties."""
        behavior = make_behavior()
        
        assert isinstance(behavior.created_datetime, datetime)
        assert isinstance(behavior.last_seen_datetime, datetime)


class TestConflictRecord:
    """Tests for ConflictRecord data model."""
    
    def test_create_conflict_with_defaults(self):
        """Test creating a conflict with default fields."""
        conflict = make_conflict()
        
        assert conflict.user_id == "test_user"
        assert conflict.conflict_type in ["RESOLVABLE", "USER_DECISION_NEEDED"]
        assert conflict.resolution_status in ["AUTO_RESOLVED", "PENDING", "USER_RESOLVED"]
    
    def test_conflict_polarity_reversal(self):
        """Test detecting polarity reversals."""
        # Polarity reversal
        reversal = make_conflict(
            old_polarity="POSITIVE",
            new_polarity="NEGATIVE",
        )
        assert reversal.is_polarity_reversal is True
        
        # Same polarity - not a reversal
        no_reversal = make_conflict(
            old_polarity="POSITIVE",
            new_polarity="POSITIVE",
        )
        assert no_reversal.is_polarity_reversal is False
        
        # No polarity data
        no_data = make_conflict(old_polarity=None, new_polarity=None)
        assert no_data.is_polarity_reversal is False
    
    def test_conflict_target_migration(self):
        """Test detecting target migrations."""
        # Target migration
        migration = make_conflict(
            old_target="vim",
            new_target="vscode",
        )
        assert migration.is_target_migration is True
        
        # Same target - not a migration
        no_migration = make_conflict(
            old_target="vim",
            new_target="vim",
        )
        assert no_migration.is_target_migration is False
    
    def test_conflict_validation_type(self):
        """Test conflict type validation."""
        with pytest.raises(ValueError, match="Conflict type must be one of"):
            make_conflict(conflict_type="INVALID")
    
    def test_conflict_validation_status(self):
        """Test resolution status validation."""
        with pytest.raises(ValueError, match="Resolution status must be one of"):
            make_conflict(resolution_status="INVALID")
    
    def test_conflict_validation_polarity(self):
        """Test polarity validation."""
        with pytest.raises(ValueError, match="must be POSITIVE or NEGATIVE"):
            make_conflict(old_polarity="INVALID")
    
    def test_conflict_to_dict(self):
        """Test converting conflict to dictionary."""
        conflict = make_conflict(
            old_polarity="POSITIVE",
            new_polarity="NEGATIVE",
            old_target="remote work",
            new_target="office work",
        )
        
        data = conflict.to_dict()
        
        assert data["old_polarity"] == "POSITIVE"
        assert data["new_polarity"] == "NEGATIVE"
        assert data["old_target"] == "remote work"
        assert data["new_target"] == "office work"
    
    def test_conflict_from_dict(self):
        """Test creating conflict from dictionary."""
        data = {
            "user_id": "user456",
            "conflict_id": "conf456",
            "behavior_id_1": "beh1",
            "behavior_id_2": "beh2",
            "conflict_type": "RESOLVABLE",
            "resolution_status": "AUTO_RESOLVED",
            "old_polarity": "NEGATIVE",
            "new_polarity": "POSITIVE",
            "old_target": None,
            "new_target": None,
            "created_at": days_ago(5),
        }
        
        conflict = ConflictRecord.from_dict(data)
        
        assert conflict.user_id == "user456"
        assert conflict.old_polarity == "NEGATIVE"
        assert conflict.new_polarity == "POSITIVE"
        assert conflict.is_polarity_reversal is True


def test_behavior_and_conflict_integration():
    """Test that behaviors and conflicts work together."""
    behavior1 = make_behavior(
        behavior_id="beh1",
        target="python",
        polarity="POSITIVE",
    )
    
    behavior2 = make_behavior(
        behavior_id="beh2",
        target="python",
        polarity="NEGATIVE",
    )
    
    conflict = make_conflict(
        behavior_id_1=behavior1.behavior_id,
        behavior_id_2=behavior2.behavior_id,
        old_polarity=behavior1.polarity,
        new_polarity=behavior2.polarity,
    )
    
    assert conflict.is_polarity_reversal is True
    assert conflict.behavior_id_1 == behavior1.behavior_id
    assert conflict.behavior_id_2 == behavior2.behavior_id
