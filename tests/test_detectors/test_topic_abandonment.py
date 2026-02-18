"""
Tests for TopicAbandonmentDetector.

Tests detection of topics that were active historically but have gone silent.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.detectors.topic_abandonment import TopicAbandonmentDetector
from app.models.drift import DriftType
from app.config import Settings
from tests.conftest import make_behavior, make_snapshot, days_ago


class TestTopicAbandonmentDetector:
    """Test suite for TopicAbandonmentDetector."""
    
    def test_silent_topic_high_reinforcement_triggers(self):
        """Test that topic with high reinforcement going silent triggers signal."""
        # Create behaviors for "React" in reference window (60-30 days ago)
        react_behaviors = [
            make_behavior(
                behavior_id="beh_react_1",
                target="React",
                reinforcement_count=3,
                last_seen_at=days_ago(35)
            ),
            make_behavior(
                behavior_id="beh_react_2",
                target="React",
                reinforcement_count=2,
                last_seen_at=days_ago(32)
            ),
        ]
        
        # Create behaviors for current window (30-0 days ago) - React is absent
        python_behavior = make_behavior(
            behavior_id="beh_python",
            target="Python",
            reinforcement_count=5,
            last_seen_at=days_ago(1)
        )
        
        reference = make_snapshot(
            behaviors=react_behaviors,
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[python_behavior],
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        # Run detector
        detector = TopicAbandonmentDetector()
        signals = detector.detect(reference, current)
        
        # Should detect abandonment
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.drift_type == DriftType.TOPIC_ABANDONMENT
        assert "React" in signal.affected_targets
        assert signal.evidence["abandoned_target"] == "React"
        assert signal.evidence["historical_reinforcement_count"] == 5  # 3 + 2
        assert signal.evidence["days_silent"] >= 30
    
    def test_weak_topic_not_flagged(self):
        """Test that topics with low reinforcement are not flagged."""
        # Create behavior with only 1 reinforcement (below min threshold of 2)
        weak_behavior = make_behavior(
            behavior_id="beh_weak",
            target="weak_topic",
            reinforcement_count=1,
            last_seen_at=days_ago(35)
        )
        
        reference = make_snapshot(
            behaviors=[weak_behavior],
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[],  # Empty current window
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        detector = TopicAbandonmentDetector()
        signals = detector.detect(reference, current)
        
        # Should not detect - reinforcement too low
        assert len(signals) == 0
    
    def test_recent_activity_no_signal(self):
        """Test that recently active topics don't trigger abandonment."""
        # Create behavior that is still active in current window
        python_old = make_behavior(
            behavior_id="beh_python_old",
            target="Python",
            reinforcement_count=5,
            last_seen_at=days_ago(35)
        )
        
        python_new = make_behavior(
            behavior_id="beh_python_new",
            target="Python",
            reinforcement_count=3,
            last_seen_at=days_ago(1)  # Still active!
        )
        
        reference = make_snapshot(
            behaviors=[python_old],
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[python_new],
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        detector = TopicAbandonmentDetector()
        signals = detector.detect(reference, current)
        
        # Should not detect - still active
        assert len(signals) == 0
    
    def test_multiple_abandoned_topics(self):
        """Test detection of multiple abandoned topics."""
        # Create multiple topics in reference window
        reference_behaviors = [
            make_behavior(
                behavior_id="beh_react",
                target="React",
                reinforcement_count=5,
                last_seen_at=days_ago(35)
            ),
            make_behavior(
                behavior_id="beh_vue",
                target="Vue",
                reinforcement_count=4,
                last_seen_at=days_ago(40)
            ),
            make_behavior(
                behavior_id="beh_angular",
                target="Angular",
                reinforcement_count=3,
                last_seen_at=days_ago(38)
            ),
        ]
        
        # Current window has different topics
        current_behaviors = [
            make_behavior(
                behavior_id="beh_python",
                target="Python",
                reinforcement_count=2,
                last_seen_at=days_ago(1)
            ),
        ]
        
        reference = make_snapshot(
            behaviors=reference_behaviors,
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=current_behaviors,
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        detector = TopicAbandonmentDetector()
        signals = detector.detect(reference, current)
        
        # Should detect all three abandoned topics
        assert len(signals) == 3
        
        abandoned_targets = [s.affected_targets[0] for s in signals]
        assert "React" in abandoned_targets
        assert "Vue" in abandoned_targets
        assert "Angular" in abandoned_targets
    
    def test_days_silent_calculation(self):
        """Test that days_silent is calculated correctly."""
        # Create behavior seen 35 days ago
        old_behavior = make_behavior(
            behavior_id="beh_old",
            target="old_topic",
            reinforcement_count=5,
            last_seen_at=days_ago(35)
        )
        
        reference = make_snapshot(
            behaviors=[old_behavior],
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[],
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        detector = TopicAbandonmentDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Should be approximately 35 days silent
        days_silent = signal.evidence["days_silent"]
        assert 34 <= days_silent <= 36  # Allow for slight variation
    
    def test_drift_score_calculation(self):
        """Test drift score calculation based on weights."""
        # Create behavior with specific reinforcement
        behavior = make_behavior(
            behavior_id="beh_test",
            target="test_topic",
            reinforcement_count=5,  # historical_weight = 5/5 = 1.0
            last_seen_at=days_ago(31)  # just beyond threshold
        )
        
        reference = make_snapshot(
            behaviors=[behavior],
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[],
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        detector = TopicAbandonmentDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Check weights
        historical_weight = signal.evidence["historical_weight"]
        silence_weight = signal.evidence["silence_weight"]
        
        assert historical_weight == pytest.approx(1.0, rel=0.01)
        assert silence_weight >= 0.9  # At or slightly above threshold
        
        # Drift score should be product
        expected_score = historical_weight * silence_weight
        assert signal.drift_score == pytest.approx(expected_score, rel=0.01)
    
    def test_custom_thresholds(self):
        """Test detector with custom threshold settings."""
        # Create custom settings with lower thresholds
        settings = Settings(
            abandonment_silence_days=15,  # Shorter silence period
            min_reinforcement_for_abandonment=1  # Lower reinforcement
        )
        
        # Behavior with 20 days of silence (would not trigger with default 30)
        behavior = make_behavior(
            behavior_id="beh_test",
            target="test_topic",
            reinforcement_count=1,
            last_seen_at=days_ago(20)
        )
        
        reference = make_snapshot(
            behaviors=[behavior],
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[],
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        detector = TopicAbandonmentDetector(settings=settings)
        signals = detector.detect(reference, current)
        
        # Should detect with custom thresholds
        assert len(signals) == 1
    
    def test_empty_reference_no_signals(self):
        """Test that empty reference window produces no signals."""
        reference = make_snapshot(
            behaviors=[],
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[make_behavior()],
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        detector = TopicAbandonmentDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 0
    
    def test_confidence_based_on_reinforcement(self):
        """Test that confidence is based on historical reinforcement."""
        # High reinforcement = high confidence
        high_reinforcement = make_behavior(
            behavior_id="beh_high",
            target="high_topic",
            reinforcement_count=10,  # High!
            last_seen_at=days_ago(35)
        )
        
        # Low reinforcement = low confidence
        low_reinforcement = make_behavior(
            behavior_id="beh_low",
            target="low_topic",
            reinforcement_count=2,  # Just above threshold
            last_seen_at=days_ago(35)
        )
        
        reference = make_snapshot(
            behaviors=[high_reinforcement, low_reinforcement],
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[],
            conflicts=[],
            days_ago_start=30,
            days_ago_end=0
        )
        
        detector = TopicAbandonmentDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 2
        
        # Find signals by target
        high_signal = next(s for s in signals if "high_topic" in s.affected_targets)
        low_signal = next(s for s in signals if "low_topic" in s.affected_targets)
        
        # High reinforcement should have higher confidence
        assert high_signal.confidence > low_signal.confidence
