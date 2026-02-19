"""
Unit tests for drift detection models.

Tests for:
- BehaviorRecord
- ConflictRecord  
- DriftSignal
- DriftEvent
- BehaviorSnapshot
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.models.behavior import BehaviorRecord, ConflictRecord
from app.models.drift import DriftSignal, DriftEvent, DriftType, DriftSeverity
from app.models.snapshot import BehaviorSnapshot


class TestBehaviorRecord:
    """Tests for BehaviorRecord dataclass."""
    
    def test_create_valid_behavior(self, sample_behavior):
        """Test creating a valid behavior record."""
        assert sample_behavior.user_id == "user_123"
        assert sample_behavior.target == "python"
        assert sample_behavior.is_active is True
        assert sample_behavior.is_superseded is False
    
    def test_credibility_validation(self, behavior_factory):
        """Test that credibility must be between 0 and 1."""
        with pytest.raises(ValueError, match="Credibility must be between"):
            behavior_factory(credibility=1.5)
        
        with pytest.raises(ValueError, match="Credibility must be between"):
            behavior_factory(credibility=-0.1)
    
    def test_negative_reinforcement_validation(self, behavior_factory):
        """Test that reinforcement count cannot be negative."""
        with pytest.raises(ValueError, match="cannot be negative"):
            behavior_factory(reinforcement_count=-1)
    
    def test_invalid_state_validation(self, behavior_factory):
        """Test that state must be ACTIVE or SUPERSEDED."""
        with pytest.raises(ValueError, match="State must be"):
            behavior_factory(state="INVALID")
    
    def test_invalid_polarity_validation(self, behavior_factory):
        """Test that polarity must be POSITIVE or NEGATIVE."""
        with pytest.raises(ValueError, match="Polarity must be"):
            behavior_factory(polarity="NEUTRAL")
    
    def test_from_dict(self):
        """Test creating a behavior from dictionary."""
        data = {
            "user_id": "user_123",
            "behavior_id": "beh_001",
            "target": "python",
            "intent": "PREFERENCE",
            "context": "backend",
            "polarity": "POSITIVE",
            "credibility": 0.9,
            "reinforcement_count": 10,
            "state": "ACTIVE",
            "created_at": 1000000,
            "last_seen_at": 1000100,
            "snapshot_updated_at": 1000200,
        }
        behavior = BehaviorRecord.from_dict(data)
        assert behavior.target == "python"
        assert behavior.credibility == 0.9
    
    def test_to_dict(self, sample_behavior):
        """Test converting behavior to dictionary."""
        data = sample_behavior.to_dict()
        assert data["user_id"] == "user_123"
        assert data["target"] == "python"
        assert "credibility" in data


class TestConflictRecord:
    """Tests for ConflictRecord dataclass."""
    
    def test_create_valid_conflict(self, sample_conflict):
        """Test creating a valid conflict record."""
        assert sample_conflict.user_id == "user_123"
        assert sample_conflict.is_polarity_reversal is True
    
    def test_polarity_reversal_detection(self, conflict_factory):
        """Test detecting polarity reversals."""
        # Polarity reversal
        conflict = conflict_factory(old_polarity="POSITIVE", new_polarity="NEGATIVE")
        assert conflict.is_polarity_reversal is True
        
        # No reversal (same polarity)
        conflict = conflict_factory(old_polarity="POSITIVE", new_polarity="POSITIVE")
        assert conflict.is_polarity_reversal is False
        
        # No polarity fields
        conflict = conflict_factory(old_polarity=None, new_polarity=None)
        assert conflict.is_polarity_reversal is False
    
    def test_invalid_conflict_type(self):
        """Test that invalid conflict types are rejected."""
        with pytest.raises(ValueError, match="Conflict type must be"):
            ConflictRecord(
                user_id="user_123",
                conflict_id="conf_001",
                behavior_id_1="beh_001",
                behavior_id_2="beh_002",
                conflict_type="INVALID",
                resolution_status="AUTO_RESOLVED",
                old_polarity=None,
                new_polarity=None,
                old_target=None,
                new_target=None,
                created_at=1000000,
            )


class TestDriftSignal:
    """Tests for DriftSignal dataclass."""
    
    def test_create_valid_signal(self, sample_drift_signal):
        """Test creating a valid drift signal."""
        assert sample_drift_signal.drift_type == DriftType.TOPIC_EMERGENCE
        assert sample_drift_signal.drift_score == 0.75
    
    def test_severity_calculation(self, drift_signal_factory):
        """Test severity is calculated correctly from drift score."""
        # Strong drift
        signal = drift_signal_factory(drift_score=0.85)
        assert signal.severity == DriftSeverity.STRONG_DRIFT
        
        # Moderate drift
        signal = drift_signal_factory(drift_score=0.7)
        assert signal.severity == DriftSeverity.MODERATE_DRIFT
        
        # Weak drift
        signal = drift_signal_factory(drift_score=0.4)
        assert signal.severity == DriftSeverity.WEAK_DRIFT
        
        # No drift
        signal = drift_signal_factory(drift_score=0.2)
        assert signal.severity == DriftSeverity.NO_DRIFT
    
    def test_is_actionable(self, drift_signal_factory):
        """Test actionable flag is correct."""
        # Actionable (moderate or strong)
        signal = drift_signal_factory(drift_score=0.75)
        assert signal.is_actionable is True
        
        # Not actionable (weak or none)
        signal = drift_signal_factory(drift_score=0.4)
        assert signal.is_actionable is False
    
    def test_invalid_drift_score(self, drift_signal_factory):
        """Test that invalid drift scores are rejected."""
        with pytest.raises(ValueError, match="drift_score must be between"):
            drift_signal_factory(drift_score=1.5)
        
        with pytest.raises(ValueError, match="drift_score must be between"):
            drift_signal_factory(drift_score=-0.1)
    
    def test_invalid_confidence(self, drift_signal_factory):
        """Test that invalid confidence is rejected."""
        with pytest.raises(ValueError, match="confidence must be between"):
            drift_signal_factory(confidence=1.5)
    
    def test_to_dict(self, sample_drift_signal):
        """Test converting signal to dictionary."""
        data = sample_drift_signal.to_dict()
        assert data["drift_type"] == "TOPIC_EMERGENCE"
        assert data["drift_score"] == 0.75
        assert "severity" in data


class TestDriftEvent:
    """Tests for DriftEvent dataclass."""
    
    def test_from_signal(self, sample_drift_signal):
        """Test creating DriftEvent from DriftSignal."""
        event = DriftEvent.from_signal(
            signal=sample_drift_signal,
            user_id="user_123",
            reference_window_start=1000000,
            reference_window_end=1100000,
            current_window_start=1100000,
            current_window_end=1200000,
            detected_at=1200000,
        )
        
        assert event.user_id == "user_123"
        assert event.drift_type == DriftType.TOPIC_EMERGENCE
        assert event.drift_score == 0.75
        assert event.severity == DriftSeverity.MODERATE_DRIFT
    
    def test_drift_event_id_generation(self, sample_drift_signal):
        """Test that drift event ID is auto-generated."""
        event = DriftEvent.from_signal(
            signal=sample_drift_signal,
            user_id="user_123",
            reference_window_start=1000000,
            reference_window_end=1100000,
            current_window_start=1100000,
            current_window_end=1200000,
            detected_at=1200000,
        )
        
        assert event.drift_event_id is not None
        assert len(event.drift_event_id) > 0


class TestBehaviorSnapshot:
    """Tests for BehaviorSnapshot dataclass."""
    
    def test_empty_snapshot(self, empty_snapshot):
        """Test creating an empty snapshot."""
        assert empty_snapshot.user_id == "user_123"
        assert len(empty_snapshot.behaviors) == 0
        assert len(empty_snapshot.get_targets()) == 0
    
    def test_snapshot_with_behaviors(self, current_snapshot):
        """Test snapshot computes distributions correctly."""
        targets = current_snapshot.get_targets()
        assert "python" in targets
        assert "rust" in targets
        assert "kubernetes" in targets
    
    def test_get_reinforcement_count(self, current_snapshot):
        """Test getting reinforcement count for a target."""
        count = current_snapshot.get_reinforcement_count("python")
        assert count == 15
    
    def test_get_active_behaviors(self, current_snapshot):
        """Test getting only active behaviors."""
        active = current_snapshot.get_active_behaviors()
        assert len(active) == 3
        for behavior in active:
            assert behavior.is_active is True
    
    def test_topic_distribution(self, current_snapshot):
        """Test topic distribution calculation."""
        dist = current_snapshot.topic_distribution
        assert "python" in dist
        # Python has 15 reinforcements out of 29 total (15+8+6)
        assert dist["python"] == pytest.approx(15/29, rel=0.01)
    
    def test_get_contexts_for_target(self, behavior_factory):
        """Test getting contexts for a specific target."""
        now = datetime.now(timezone.utc)
        behaviors = [
            behavior_factory(behavior_id="b1", target="python", context="backend"),
            behavior_factory(behavior_id="b2", target="python", context="data-science"),
            behavior_factory(behavior_id="b3", target="java", context="backend"),
        ]
        snapshot = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=behaviors,
        )
        
        contexts = snapshot.get_contexts_for_target("python")
        assert "backend" in contexts
        assert "data-science" in contexts
    
    def test_has_target(self, current_snapshot):
        """Test checking if target exists."""
        assert current_snapshot.has_target("python") is True
        assert current_snapshot.has_target("nonexistent") is False
