"""
Tests for TopicEmergenceDetector.

Tests detection of new topics appearing with significant activity.
"""

import pytest
from unittest.mock import patch
from datetime import datetime

from app.detectors.topic_emergence import TopicEmergenceDetector
from app.models.drift import DriftType
from app.config import Settings
from tests.conftest import make_behavior, make_snapshot, days_ago


class TestTopicEmergenceDetector:
    """Test suite for TopicEmergenceDetector."""
    
    def test_new_topic_high_reinforcement(self):
        """Test that new topic with high reinforcement is detected."""
        # Reference: only python
        ref_behaviors = [
            make_behavior(
                target="python",
                reinforcement_count=5
            ),
        ]
        
        # Current: python + machine learning (new)
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_py",
                target="python",
                reinforcement_count=3
            ),
            make_behavior(
                behavior_id="beh_ml",
                target="machine learning",
                reinforcement_count=4,
                last_seen_at=days_ago(2)
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        # Should detect machine learning as emerging
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.drift_type == DriftType.TOPIC_EMERGENCE
        assert "machine learning" in signal.affected_targets
        assert signal.evidence["emerging_target"] == "machine learning"
        assert signal.evidence["reinforcement_count"] == 4
    
    def test_single_mention_no_signal(self):
        """Test that single mention (no reinforcement) is filtered out."""
        # Reference: empty
        ref_behaviors = []
        
        # Current: new topic with only 1 reinforcement (below threshold of 2)
        cur_behaviors = [
            make_behavior(
                target="new_topic",
                reinforcement_count=1
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        # Below reinforcement threshold, no signal
        assert len(signals) == 0
    
    def test_recency_weight_calculation(self):
        """Test that recent mentions have higher scores than old mentions."""
        ref_behaviors = []
        
        # Recent topic: mentioned 2 days ago
        cur_recent = [
            make_behavior(
                behavior_id="beh_recent",
                target="recent_topic",
                reinforcement_count=3,
                last_seen_at=days_ago(2)
            ),
        ]
        
        # Old topic: mentioned 28 days ago
        cur_old = [
            make_behavior(
                behavior_id="beh_old",
                target="old_topic",
                reinforcement_count=3,
                last_seen_at=days_ago(28)
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_recent + cur_old)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 2
        
        signal_recent = next(s for s in signals if "recent_topic" in s.affected_targets)
        signal_old = next(s for s in signals if "old_topic" in s.affected_targets)
        
        # Recent topic should have higher recency weight
        assert signal_recent.evidence["recency_weight"] > signal_old.evidence["recency_weight"]
        
        # And higher overall drift score
        assert signal_recent.drift_score > signal_old.drift_score
    
    def test_relative_importance_calculation(self):
        """Test that drift score reflects relative importance in current window."""
        ref_behaviors = []
        
        # Topic with 50% of total reinforcement
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_major",
                target="major_topic",
                reinforcement_count=5,
                last_seen_at=days_ago(1)
            ),
            make_behavior(
                behavior_id="beh_minor",
                target="minor_topic",
                reinforcement_count=5,
                last_seen_at=days_ago(1)
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 2
        
        # Both should have same relative importance (0.5)
        for signal in signals:
            relative_importance = signal.evidence["relative_importance"]
            assert relative_importance == pytest.approx(0.5, rel=0.01)
    
    def test_confidence_based_on_reinforcement(self):
        """Test that confidence increases with reinforcement count."""
        ref_behaviors = []
        
        # Low reinforcement
        cur_low = [
            make_behavior(
                behavior_id="beh_low",
                target="low_reinforcement",
                reinforcement_count=2
            ),
        ]
        
        # High reinforcement
        cur_high = [
            make_behavior(
                behavior_id="beh_high",
                target="high_reinforcement",
                reinforcement_count=10
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_low + cur_high)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 2
        
        signal_low = next(s for s in signals if "low_reinforcement" in s.affected_targets)
        signal_high = next(s for s in signals if "high_reinforcement" in s.affected_targets)
        
        # Higher reinforcement should have higher confidence
        assert signal_high.confidence > signal_low.confidence
    
    def test_multiple_emerging_topics(self):
        """Test detection of multiple emerging topics."""
        ref_behaviors = [
            make_behavior(target="python", reinforcement_count=5),
        ]
        
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_py",
                target="python",
                reinforcement_count=3
            ),
            make_behavior(
                behavior_id="beh_ml",
                target="machine learning",
                reinforcement_count=4
            ),
            make_behavior(
                behavior_id="beh_dl",
                target="deep learning",
                reinforcement_count=3
            ),
            make_behavior(
                behavior_id="beh_nn",
                target="neural networks",
                reinforcement_count=2
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        # Should detect all 3 new topics
        assert len(signals) == 3
        
        targets = [s.affected_targets[0] for s in signals]
        assert "machine learning" in targets
        assert "deep learning" in targets
        assert "neural networks" in targets
    
    def test_existing_topic_not_detected(self):
        """Test that topics present in both windows are not detected."""
        # Topic in both windows
        ref_behaviors = [
            make_behavior(
                target="docker",
                reinforcement_count=3
            ),
        ]
        
        cur_behaviors = [
            make_behavior(
                target="docker",
                reinforcement_count=5
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        # Not new, no signal
        assert len(signals) == 0
    
    def test_custom_min_reinforcement(self):
        """Test detector with custom reinforcement threshold."""
        ref_behaviors = []
        
        # Topic with 3 reinforcements
        cur_behaviors = [
            make_behavior(
                target="topic",
                reinforcement_count=3
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        # With default threshold (2), detected
        detector_default = TopicEmergenceDetector()
        signals_default = detector_default.detect(reference, current)
        assert len(signals_default) == 1
        
        # With high threshold (5), not detected
        settings_high = Settings(emergence_min_reinforcement=5)
        detector_high = TopicEmergenceDetector(settings=settings_high)
        signals_high = detector_high.detect(reference, current)
        assert len(signals_high) == 0
    
    def test_contexts_tracked_in_evidence(self):
        """Test that contexts are tracked in evidence."""
        ref_behaviors = []
        
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_1",
                target="kubernetes",
                context="devops",
                reinforcement_count=2
            ),
            make_behavior(
                behavior_id="beh_2",
                target="kubernetes",
                context="cloud",
                reinforcement_count=1
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Should track contexts
        contexts = signal.evidence["contexts"]
        assert "devops" in contexts or "cloud" in contexts
        assert len(contexts) >= 1
    
    def test_average_credibility_tracked(self):
        """Test that average credibility is tracked in evidence."""
        ref_behaviors = []
        
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_1",
                target="rust",
                credibility=0.70,
                reinforcement_count=1
            ),
            make_behavior(
                behavior_id="beh_2",
                target="rust",
                credibility=0.90,
                reinforcement_count=1
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Average credibility should be (0.70 + 0.90) / 2 = 0.80
        assert signal.evidence["avg_credibility"] == pytest.approx(0.80, rel=0.01)
    
    def test_behavior_count_tracked(self):
        """Test that number of behaviors is tracked."""
        ref_behaviors = []
        
        # New topic with 3 separate behaviors
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_1",
                target="topic",
                reinforcement_count=1
            ),
            make_behavior(
                behavior_id="beh_2",
                target="topic",
                reinforcement_count=1
            ),
            make_behavior(
                behavior_id="beh_3",
                target="topic",
                reinforcement_count=1
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.evidence["behavior_count"] == 3
        assert signal.evidence["reinforcement_count"] == 3
    
    def test_empty_current_window_no_signal(self):
        """Test that empty current window produces no signals."""
        ref_behaviors = [
            make_behavior(target="python", reinforcement_count=5),
        ]
        
        current_behaviors = []
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=current_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 0
    
    def test_all_topics_existing_no_signal(self):
        """Test that if all current topics existed before, no signals."""
        ref_behaviors = [
            make_behavior(target="python", reinforcement_count=3),
            make_behavior(target="javascript", reinforcement_count=2),
        ]
        
        cur_behaviors = [
            make_behavior(target="python", reinforcement_count=4),
            make_behavior(target="javascript", reinforcement_count=3),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        # No new topics
        assert len(signals) == 0
    
    def test_drift_score_combines_importance_and_recency(self):
        """Test that drift score is product of importance and recency."""
        ref_behaviors = []
        
        # New topic: 50% importance, recent (high recency weight ~1.0)
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_1",
                target="topic",
                reinforcement_count=10,
                last_seen_at=days_ago(1)
            ),
            make_behavior(
                behavior_id="beh_2",
                target="other",
                reinforcement_count=10,
                last_seen_at=days_ago(1)
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = TopicEmergenceDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 2
        
        for signal in signals:
            importance = signal.evidence["relative_importance"]
            recency = signal.evidence["recency_weight"]
            
            # Drift score should be approximately importance * recency
            expected_score = importance * recency
            assert signal.drift_score == pytest.approx(expected_score, rel=0.01)
