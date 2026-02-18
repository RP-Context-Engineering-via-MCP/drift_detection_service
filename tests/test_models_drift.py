"""
Tests for drift data models (DriftSignal and DriftEvent).
"""

import pytest
from datetime import datetime

from app.models.drift import DriftSignal, DriftEvent, DriftType, DriftSeverity
from tests.conftest import days_ago, now


class TestDriftSignal:
    """Tests for DriftSignal data model."""
    
    def test_create_drift_signal(self):
        """Test creating a drift signal with all required fields."""
        signal = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.75,
            affected_targets=["python", "machine learning"],
            evidence={"new_topics": ["pytorch", "tensorflow"]},
            confidence=0.85,
        )
        
        assert signal.drift_type == DriftType.TOPIC_EMERGENCE
        assert signal.drift_score == 0.75
        assert len(signal.affected_targets) == 2
        assert signal.confidence == 0.85
    
    def test_drift_signal_severity_calculation(self):
        """Test that severity is calculated correctly from drift_score."""
        # NO_DRIFT (0.0-0.3)
        no_drift = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.2,
            affected_targets=["test"],
            evidence={},
            confidence=0.5,
        )
        assert no_drift.severity == DriftSeverity.NO_DRIFT
        
        # WEAK_DRIFT (0.3-0.6)
        weak = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.4,
            affected_targets=["test"],
            evidence={},
            confidence=0.5,
        )
        assert weak.severity == DriftSeverity.WEAK_DRIFT
        
        # MODERATE_DRIFT (0.6-0.8)
        moderate = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.7,
            affected_targets=["test"],
            evidence={},
            confidence=0.5,
        )
        assert moderate.severity == DriftSeverity.MODERATE_DRIFT
        
        # STRONG_DRIFT (0.8-1.0)
        strong = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.9,
            affected_targets=["test"],
            evidence={},
            confidence=0.5,
        )
        assert strong.severity == DriftSeverity.STRONG_DRIFT
    
    def test_is_actionable_property(self):
        """Test is_actionable based on severity."""
        weak = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.4,
            affected_targets=["test"],
            evidence={},
            confidence=0.5,
        )
        assert weak.is_actionable is False
        
        moderate = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.7,
            affected_targets=["test"],
            evidence={},
            confidence=0.5,
        )
        assert moderate.is_actionable is True
        
        strong = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.9,
            affected_targets=["test"],
            evidence={},
            confidence=0.5,
        )
        assert strong.is_actionable is True
    
    def test_drift_signal_validation_score(self):
        """Test drift_score must be between 0 and 1."""
        with pytest.raises(ValueError, match="drift_score must be between"):
            DriftSignal(
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=1.5,
                affected_targets=["test"],
                evidence={},
                confidence=0.5,
            )
    
    def test_drift_signal_validation_confidence(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValueError, match="confidence must be between"):
            DriftSignal(
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=0.5,
                affected_targets=["test"],
                evidence={},
                confidence=2.0,
            )
    
    def test_drift_signal_to_dict(self):
        """Test converting signal to dictionary."""
        signal = DriftSignal(
            drift_type=DriftType.PREFERENCE_REVERSAL,
            drift_score=0.85,
            affected_targets=["remote work"],
            evidence={"old_polarity": "POSITIVE", "new_polarity": "NEGATIVE"},
            confidence=0.9,
        )
        
        data = signal.to_dict()
        
        assert data["drift_type"] == "PREFERENCE_REVERSAL"
        assert data["drift_score"] == 0.85
        assert data["severity"] == "STRONG_DRIFT"
        assert "evidence" in data


class TestDriftEvent:
    """Tests for DriftEvent data model."""
    
    def test_create_drift_event(self):
        """Test creating a drift event with all fields."""
        event = DriftEvent(
            drift_type=DriftType.TOPIC_ABANDONMENT,
            drift_score=0.72,
            confidence=0.8,
            severity=DriftSeverity.MODERATE_DRIFT,
            affected_targets=["react", "frontend"],
            evidence={"days_silent": 35},
            user_id="user123",
            reference_window_start=days_ago(60),
            reference_window_end=days_ago(30),
            current_window_start=days_ago(30),
            current_window_end=now(),
            detected_at=now(),
        )
        
        assert event.user_id == "user123"
        assert event.drift_type == DriftType.TOPIC_ABANDONMENT
        assert event.drift_score == 0.72
        assert len(event.drift_event_id) > 0  # UUID generated
    
    def test_drift_event_from_signal(self):
        """Test creating a DriftEvent from a DriftSignal."""
        signal = DriftSignal(
            drift_type=DriftType.INTENSITY_SHIFT,
            drift_score=0.68,
            affected_targets=["python"],
            evidence={"credibility_delta": 0.3},
            confidence=0.75,
        )
        
        event = DriftEvent.from_signal(
            signal=signal,
            user_id="user456",
            reference_window_start=days_ago(60),
            reference_window_end=days_ago(30),
            current_window_start=days_ago(30),
            current_window_end=now(),
            detected_at=now(),
            behavior_ref_ids=["beh1", "beh2"],
        )
        
        assert event.drift_type == signal.drift_type
        assert event.drift_score == signal.drift_score
        assert event.affected_targets == signal.affected_targets
        assert event.user_id == "user456"
        assert len(event.behavior_ref_ids) == 2
    
    def test_drift_event_validation(self):
        """Test drift event validation."""
        with pytest.raises(ValueError, match="drift_score must be between"):
            DriftEvent(
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=1.5,
                confidence=0.8,
                severity=DriftSeverity.STRONG_DRIFT,
                affected_targets=["test"],
                evidence={},
                user_id="user",
                reference_window_start=0,
                reference_window_end=0,
                current_window_start=0,
                current_window_end=0,
                detected_at=0,
            )
    
    def test_drift_event_to_dict(self):
        """Test converting event to dictionary."""
        event = DriftEvent(
            drift_type=DriftType.CONTEXT_EXPANSION,
            drift_score=0.65,
            confidence=0.7,
            severity=DriftSeverity.MODERATE_DRIFT,
            affected_targets=["python"],
            evidence={"old_context": "backend", "new_context": "general"},
            user_id="user789",
            reference_window_start=days_ago(60),
            reference_window_end=days_ago(30),
            current_window_start=days_ago(30),
            current_window_end=now(),
            detected_at=now(),
        )
        
        data = event.to_dict()
        
        assert data["user_id"] == "user789"
        assert data["drift_type"] == "CONTEXT_EXPANSION"
        assert data["severity"] == "MODERATE_DRIFT"
        assert "drift_event_id" in data
        assert "evidence" in data
    
    def test_drift_event_from_dict(self):
        """Test creating event from dictionary."""
        data = {
            "drift_event_id": "evt123",
            "user_id": "user999",
            "drift_type": "PREFERENCE_REVERSAL",
            "drift_score": 0.88,
            "confidence": 0.92,
            "severity": "STRONG_DRIFT",
            "affected_targets": ["remote work"],
            "evidence": {"reason": "polarity flip"},
            "reference_window_start": days_ago(60),
            "reference_window_end": days_ago(30),
            "current_window_start": days_ago(30),
            "current_window_end": now(),
            "detected_at": now(),
            "acknowledged_at": None,
            "behavior_ref_ids": [],
            "conflict_ref_ids": [],
        }
        
        event = DriftEvent.from_dict(data)
        
        assert event.drift_event_id == "evt123"
        assert event.user_id == "user999"
        assert event.drift_type == DriftType.PREFERENCE_REVERSAL
    
    def test_acknowledge_drift_event(self):
        """Test acknowledging a drift event."""
        event = DriftEvent(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.75,
            confidence=0.8,
            severity=DriftSeverity.MODERATE_DRIFT,
            affected_targets=["ml"],
            evidence={},
            user_id="user",
            reference_window_start=0,
            reference_window_end=0,
            current_window_start=0,
            current_window_end=0,
            detected_at=now(),
        )
        
        assert event.is_acknowledged is False
        
        ack_time = now()
        event.acknowledge(ack_time)
        
        assert event.is_acknowledged is True
        assert event.acknowledged_at == ack_time
    
    def test_detected_datetime_property(self):
        """Test converting detected_at to datetime."""
        detected_ts = now()
        event = DriftEvent(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.75,
            confidence=0.8,
            severity=DriftSeverity.MODERATE_DRIFT,
            affected_targets=["test"],
            evidence={},
            user_id="user",
            reference_window_start=0,
            reference_window_end=0,
            current_window_start=0,
            current_window_end=0,
            detected_at=detected_ts,
        )
        
        assert isinstance(event.detected_datetime, datetime)
        assert event.detected_datetime.timestamp() == pytest.approx(detected_ts, abs=1)


def test_drift_type_enum():
    """Test DriftType enum values."""
    assert DriftType.TOPIC_EMERGENCE == "TOPIC_EMERGENCE"
    assert DriftType.TOPIC_ABANDONMENT == "TOPIC_ABANDONMENT"
    assert DriftType.PREFERENCE_REVERSAL == "PREFERENCE_REVERSAL"
    assert DriftType.INTENSITY_SHIFT == "INTENSITY_SHIFT"
    assert DriftType.CONTEXT_EXPANSION == "CONTEXT_EXPANSION"
    assert DriftType.CONTEXT_CONTRACTION == "CONTEXT_CONTRACTION"


def test_drift_severity_enum():
    """Test DriftSeverity enum values."""
    assert DriftSeverity.NO_DRIFT == "NO_DRIFT"
    assert DriftSeverity.WEAK_DRIFT == "WEAK_DRIFT"
    assert DriftSeverity.MODERATE_DRIFT == "MODERATE_DRIFT"
    assert DriftSeverity.STRONG_DRIFT == "STRONG_DRIFT"
