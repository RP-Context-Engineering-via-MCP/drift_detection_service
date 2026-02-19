"""
Unit tests for drift detectors.

Tests for:
- TopicEmergenceDetector
- TopicAbandonmentDetector
- PreferenceReversalDetector
- IntensityShiftDetector
- ContextShiftDetector
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.detectors.topic_emergence import TopicEmergenceDetector
from app.detectors.topic_abandonment import TopicAbandonmentDetector
from app.detectors.preference_reversal import PreferenceReversalDetector
from app.detectors.intensity_shift import IntensityShiftDetector
from app.detectors.context_shift import ContextShiftDetector
from app.models.drift import DriftType
from app.models.snapshot import BehaviorSnapshot


class TestTopicEmergenceDetector:
    """Tests for TopicEmergenceDetector."""
    
    def test_detect_new_topic(self, reference_snapshot, current_snapshot, test_settings):
        """Test detecting a new topic that emerges in current window."""
        detector = TopicEmergenceDetector(test_settings)
        signals = detector.detect(reference_snapshot, current_snapshot)
        
        # Should detect rust and kubernetes as emerging
        assert len(signals) >= 1
        
        emerging_targets = set()
        for signal in signals:
            assert signal.drift_type == DriftType.TOPIC_EMERGENCE
            emerging_targets.update(signal.affected_targets)
        
        # Rust and kubernetes are in current but not reference
        assert "rust" in emerging_targets or "kubernetes" in emerging_targets
    
    def test_no_emergence_same_topics(self, behavior_factory, test_settings):
        """Test no emergence when topics are the same."""
        now = datetime.now(timezone.utc)
        
        # Same topics in both windows
        ref_behaviors = [
            behavior_factory(behavior_id="r1", target="python", days_ago=45),
        ]
        cur_behaviors = [
            behavior_factory(behavior_id="c1", target="python", days_ago=10),
        ]
        
        reference = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=60),
            window_end=now - timedelta(days=30),
            behaviors=ref_behaviors,
        )
        current = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=cur_behaviors,
        )
        
        detector = TopicEmergenceDetector(test_settings)
        signals = detector.detect(reference, current)
        
        assert len(signals) == 0
    
    def test_min_reinforcement_filter(self, behavior_factory, test_settings):
        """Test that topics with low reinforcement are filtered out."""
        now = datetime.now(timezone.utc)
        
        ref_behaviors = []
        cur_behaviors = [
            # Low reinforcement - should be filtered
            behavior_factory(behavior_id="c1", target="go", reinforcement_count=1, days_ago=5),
        ]
        
        reference = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=60),
            window_end=now - timedelta(days=30),
            behaviors=ref_behaviors,
        )
        current = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=cur_behaviors,
        )
        
        detector = TopicEmergenceDetector(test_settings)
        signals = detector.detect(reference, current)
        
        # Should be filtered out due to low reinforcement
        assert len(signals) == 0


class TestTopicAbandonmentDetector:
    """Tests for TopicAbandonmentDetector."""
    
    def test_detect_abandoned_topic(self, behavior_factory, test_settings):
        """Test detecting an abandoned topic."""
        now = datetime.now(timezone.utc)
        
        # Topic "java" was active in reference but absent in current
        ref_behaviors = [
            behavior_factory(
                behavior_id="r1", 
                target="java", 
                reinforcement_count=5,
                days_ago=45,
                last_seen_days_ago=35,  # Last seen 35 days ago
            ),
        ]
        cur_behaviors = [
            behavior_factory(behavior_id="c1", target="python", days_ago=10),
        ]
        
        reference = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=60),
            window_end=now - timedelta(days=30),
            behaviors=ref_behaviors,
        )
        current = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=cur_behaviors,
        )
        
        detector = TopicAbandonmentDetector(test_settings)
        signals = detector.detect(reference, current)
        
        # Java should be detected as abandoned
        assert len(signals) >= 1
        abandoned_targets = set()
        for signal in signals:
            assert signal.drift_type == DriftType.TOPIC_ABANDONMENT
            abandoned_targets.update(signal.affected_targets)
        
        assert "java" in abandoned_targets
    
    def test_no_abandonment_topic_still_active(self, reference_snapshot, current_snapshot, test_settings):
        """Test no abandonment when topic is still active."""
        detector = TopicAbandonmentDetector(test_settings)
        signals = detector.detect(reference_snapshot, current_snapshot)
        
        # Python is in both windows - should not be abandoned
        for signal in signals:
            assert "python" not in signal.affected_targets


class TestIntensityShiftDetector:
    """Tests for IntensityShiftDetector."""
    
    def test_detect_credibility_increase(self, behavior_factory, test_settings):
        """Test detecting increase in credibility."""
        now = datetime.now(timezone.utc)
        
        # Same topic, different credibility
        ref_behaviors = [
            behavior_factory(behavior_id="r1", target="python", credibility=0.5, days_ago=45),
        ]
        cur_behaviors = [
            behavior_factory(behavior_id="c1", target="python", credibility=0.9, days_ago=10),
        ]
        
        reference = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=60),
            window_end=now - timedelta(days=30),
            behaviors=ref_behaviors,
        )
        current = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=cur_behaviors,
        )
        
        detector = IntensityShiftDetector(test_settings)
        signals = detector.detect(reference, current)
        
        # Should detect intensity shift
        assert len(signals) >= 1
        for signal in signals:
            assert signal.drift_type == DriftType.INTENSITY_SHIFT
            assert "python" in signal.affected_targets
            assert signal.evidence.get("direction") == "INCREASE"
    
    def test_no_shift_below_threshold(self, behavior_factory, test_settings):
        """Test no shift detected when delta is below threshold."""
        now = datetime.now(timezone.utc)
        
        # Small credibility change (below 0.25 threshold)
        ref_behaviors = [
            behavior_factory(behavior_id="r1", target="python", credibility=0.7, days_ago=45),
        ]
        cur_behaviors = [
            behavior_factory(behavior_id="c1", target="python", credibility=0.8, days_ago=10),
        ]
        
        reference = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=60),
            window_end=now - timedelta(days=30),
            behaviors=ref_behaviors,
        )
        current = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=cur_behaviors,
        )
        
        detector = IntensityShiftDetector(test_settings)
        signals = detector.detect(reference, current)
        
        # Should not detect shift (delta = 0.1 < 0.25 threshold)
        assert len(signals) == 0


class TestPreferenceReversalDetector:
    """Tests for PreferenceReversalDetector."""
    
    def test_detect_polarity_reversal(self, behavior_factory, conflict_factory, test_settings):
        """Test detecting a polarity reversal from conflict."""
        now = datetime.now(timezone.utc)
        
        # Create behaviors with IDs matching the conflict's behavior_id_1 and behavior_id_2
        # The conflict factory defaults to behavior_id_1="beh_001" and behavior_id_2="beh_002"
        ref_behaviors = [
            behavior_factory(
                behavior_id="beh_001",  # Matches conflict.behavior_id_1
                target="python",
                polarity="POSITIVE",
                credibility=0.8,
                days_ago=45,
            ),
        ]
        cur_behaviors = [
            behavior_factory(
                behavior_id="beh_002",  # Matches conflict.behavior_id_2
                target="python",
                polarity="NEGATIVE",
                credibility=0.9,
                days_ago=10,
            ),
        ]
        conflicts = [
            conflict_factory(
                conflict_id="c1",
                behavior_id_1="beh_001",
                behavior_id_2="beh_002",
                old_polarity="POSITIVE",
                new_polarity="NEGATIVE",
            ),
        ]
        
        reference = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=60),
            window_end=now - timedelta(days=30),
            behaviors=ref_behaviors,
        )
        current = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=cur_behaviors,
            conflict_records=conflicts,
        )
        
        detector = PreferenceReversalDetector(test_settings)
        signals = detector.detect(reference, current)
        
        # Should detect the reversal
        assert len(signals) >= 1
        for signal in signals:
            assert signal.drift_type == DriftType.PREFERENCE_REVERSAL
    
    def test_no_reversal_without_conflicts(self, empty_snapshot, current_snapshot, test_settings):
        """Test no reversal when there are no conflicts."""
        detector = PreferenceReversalDetector(test_settings)
        signals = detector.detect(empty_snapshot, current_snapshot)
        
        # No conflicts = no reversals
        assert len(signals) == 0


class TestContextShiftDetector:
    """Tests for ContextShiftDetector."""
    
    def test_detect_context_expansion(self, behavior_factory, test_settings):
        """Test detecting context expansion (specific → general)."""
        now = datetime.now(timezone.utc)
        
        # Python was in specific context, now in general
        ref_behaviors = [
            behavior_factory(behavior_id="r1", target="python", context="data-science", days_ago=45),
        ]
        cur_behaviors = [
            behavior_factory(behavior_id="c1", target="python", context="general", days_ago=10),
        ]
        
        reference = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=60),
            window_end=now - timedelta(days=30),
            behaviors=ref_behaviors,
        )
        current = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=cur_behaviors,
        )
        
        detector = ContextShiftDetector(test_settings)
        signals = detector.detect(reference, current)
        
        # Should detect expansion
        expansion_signals = [s for s in signals if s.drift_type == DriftType.CONTEXT_EXPANSION]
        assert len(expansion_signals) >= 1
    
    def test_detect_context_contraction(self, behavior_factory, test_settings):
        """Test detecting context contraction (general → specific)."""
        now = datetime.now(timezone.utc)
        
        # Python was in general context, now in specific
        ref_behaviors = [
            behavior_factory(behavior_id="r1", target="docker", context="general", days_ago=45),
        ]
        cur_behaviors = [
            behavior_factory(behavior_id="c1", target="docker", context="microservices", days_ago=10),
        ]
        
        reference = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=60),
            window_end=now - timedelta(days=30),
            behaviors=ref_behaviors,
        )
        current = BehaviorSnapshot(
            user_id="user_123",
            window_start=now - timedelta(days=30),
            window_end=now,
            behaviors=cur_behaviors,
        )
        
        detector = ContextShiftDetector(test_settings)
        signals = detector.detect(reference, current)
        
        # Should detect contraction
        contraction_signals = [s for s in signals if s.drift_type == DriftType.CONTEXT_CONTRACTION]
        assert len(contraction_signals) >= 1
