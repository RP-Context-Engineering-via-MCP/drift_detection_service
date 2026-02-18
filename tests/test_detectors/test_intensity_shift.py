"""
Tests for IntensityShiftDetector.

Tests detection of credibility changes (intensity shifts) in user behaviors.
"""

import pytest

from app.detectors.intensity_shift import IntensityShiftDetector
from app.models.drift import DriftType
from app.config import Settings
from tests.conftest import make_behavior, make_snapshot


class TestIntensityShiftDetector:
    """Test suite for IntensityShiftDetector."""
    
    def test_credibility_increase_detected(self):
        """Test that credibility increase (stronger conviction) is detected."""
        # Reference: vim with low credibility
        ref_behaviors = [
            make_behavior(
                behavior_id="beh_vim_old",
                target="vim",
                credibility=0.4,
                reinforcement_count=3
            ),
        ]
        
        # Current: vim with high credibility
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_vim_new",
                target="vim",
                credibility=0.9,
                reinforcement_count=5
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        # Should detect intensity shift
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.drift_type == DriftType.INTENSITY_SHIFT
        assert "vim" in signal.affected_targets
        assert signal.evidence["direction"] == "INCREASE"
        assert signal.evidence["reference_credibility"] == 0.4
        assert signal.evidence["current_credibility"] == 0.9
        assert signal.evidence["credibility_delta"] == pytest.approx(0.5, rel=0.01)
        
        # Drift score should equal delta
        assert signal.drift_score == pytest.approx(0.5, rel=0.01)
    
    def test_credibility_decrease_detected(self):
        """Test that credibility decrease (weaker conviction) is detected."""
        # Reference: React with high credibility
        ref_behaviors = [
            make_behavior(
                behavior_id="beh_react_old",
                target="React",
                credibility=0.85,
                reinforcement_count=4
            ),
        ]
        
        # Current: React with low credibility
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_react_new",
                target="React",
                credibility=0.35,
                reinforcement_count=2
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.drift_type == DriftType.INTENSITY_SHIFT
        assert signal.evidence["direction"] == "DECREASE"
        assert signal.drift_score == pytest.approx(0.5, rel=0.01)
    
    def test_small_delta_no_signal(self):
        """Test that small credibility changes below threshold are ignored."""
        # Small change: 0.50 → 0.60 (delta = 0.10, below default threshold of 0.25)
        ref_behaviors = [
            make_behavior(
                target="python",
                credibility=0.50
            ),
        ]
        
        cur_behaviors = [
            make_behavior(
                target="python",
                credibility=0.60
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        # Delta below threshold, no signal
        assert len(signals) == 0
    
    def test_score_equals_delta(self):
        """Test that drift score equals the credibility delta."""
        # 0.30 → 0.90, delta = 0.60
        ref_behaviors = [
            make_behavior(
                target="kubernetes",
                credibility=0.30
            ),
        ]
        
        cur_behaviors = [
            make_behavior(
                target="kubernetes",
                credibility=0.90
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Score should equal delta
        expected_delta = 0.60
        assert signal.drift_score == pytest.approx(expected_delta, rel=0.01)
        assert signal.evidence["credibility_delta"] == pytest.approx(expected_delta, rel=0.01)
    
    def test_confidence_based_on_lower_credibility(self):
        """Test that confidence is based on the lower of the two credibilities."""
        # High → High: confidence should be high
        ref_behaviors_high = [
            make_behavior(target="topic1", credibility=0.80),
        ]
        cur_behaviors_high = [
            make_behavior(target="topic1", credibility=0.50),
        ]
        
        # Low → High: confidence should be low (based on lower value)
        ref_behaviors_low = [
            make_behavior(target="topic2", credibility=0.20),
        ]
        cur_behaviors_low = [
            make_behavior(target="topic2", credibility=0.80),
        ]
        
        reference = make_snapshot(
            behaviors=ref_behaviors_high + ref_behaviors_low
        )
        current = make_snapshot(
            behaviors=cur_behaviors_high + cur_behaviors_low
        )
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 2
        
        # Find signals by target
        signal_high = next(s for s in signals if "topic1" in s.affected_targets)
        signal_low = next(s for s in signals if "topic2" in s.affected_targets)
        
        # topic1: min(0.80, 0.50) = 0.50
        assert signal_high.confidence == pytest.approx(0.50, rel=0.01)
        
        # topic2: min(0.20, 0.80) = 0.20
        assert signal_low.confidence == pytest.approx(0.20, rel=0.01)
    
    def test_multiple_targets_detected(self):
        """Test detection of intensity shifts across multiple targets."""
        ref_behaviors = [
            make_behavior(target="docker", credibility=0.40),
            make_behavior(target="kubernetes", credibility=0.30),
            make_behavior(target="terraform", credibility=0.80),
        ]
        
        cur_behaviors = [
            make_behavior(target="docker", credibility=0.90),  # +0.50
            make_behavior(target="kubernetes", credibility=0.85),  # +0.55
            make_behavior(target="terraform", credibility=0.35),  # -0.45
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        # All three should be detected
        assert len(signals) == 3
        
        targets = [s.affected_targets[0] for s in signals]
        assert "docker" in targets
        assert "kubernetes" in targets
        assert "terraform" in targets
    
    def test_new_topic_not_detected(self):
        """Test that topics only in current window are not detected (no comparison)."""
        # New topic in current (not in reference)
        ref_behaviors = [
            make_behavior(target="python", credibility=0.70),
        ]
        
        cur_behaviors = [
            make_behavior(target="python", credibility=0.40),  # Changed from 0.50 to 0.40 to exceed threshold
            make_behavior(target="rust", credibility=0.90),  # New topic
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        # Only python should be detected (rust has no reference)
        assert len(signals) == 1
        assert "python" in signals[0].affected_targets
    
    def test_abandoned_topic_not_detected(self):
        """Test that topics only in reference window are not detected."""
        # Topic disappeared in current window
        ref_behaviors = [
            make_behavior(target="php", credibility=0.70),
            make_behavior(target="python", credibility=0.50),
        ]
        
        cur_behaviors = [
            make_behavior(target="python", credibility=0.80),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        # Only python should be detected (php is abandoned, not shifted)
        assert len(signals) == 1
        assert "python" in signals[0].affected_targets
    
    def test_custom_threshold(self):
        """Test detector with custom delta threshold."""
        # Change of 0.15 (below default 0.25, but above custom 0.10)
        ref_behaviors = [
            make_behavior(target="topic", credibility=0.50),
        ]
        
        cur_behaviors = [
            make_behavior(target="topic", credibility=0.65),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        # With default threshold (0.25), no signal
        detector_default = IntensityShiftDetector()
        signals_default = detector_default.detect(reference, current)
        assert len(signals_default) == 0
        
        # With custom low threshold (0.10), signal detected
        settings_custom = Settings(intensity_delta_threshold=0.10)
        detector_custom = IntensityShiftDetector(settings=settings_custom)
        signals_custom = detector_custom.detect(reference, current)
        assert len(signals_custom) == 1
    
    def test_relative_change_percentage(self):
        """Test that relative change percentage is calculated correctly."""
        # 0.40 → 0.80 = +100% change
        ref_behaviors = [
            make_behavior(target="topic", credibility=0.40),
        ]
        
        cur_behaviors = [
            make_behavior(target="topic", credibility=0.80),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # (0.80 - 0.40) / 0.40 * 100 = 100%
        assert signal.evidence["relative_change_pct"] == pytest.approx(100.0, rel=0.1)
    
    def test_average_credibility_multiple_behaviors(self):
        """Test that credibility is averaged across multiple behaviors per target."""
        # Reference: two python behaviors with 0.40 and 0.60 (avg = 0.50)
        ref_behaviors = [
            make_behavior(
                behavior_id="beh_py_1",
                target="python",
                credibility=0.40
            ),
            make_behavior(
                behavior_id="beh_py_2",
                target="python",
                credibility=0.60
            ),
        ]
        
        # Current: two python behaviors with 0.70 and 0.90 (avg = 0.80)
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_py_3",
                target="python",
                credibility=0.70
            ),
            make_behavior(
                behavior_id="beh_py_4",
                target="python",
                credibility=0.90
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = IntensityShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Should use averages: 0.80 - 0.50 = 0.30 delta
        assert signal.evidence["reference_credibility"] == pytest.approx(0.50, rel=0.01)
        assert signal.evidence["current_credibility"] == pytest.approx(0.80, rel=0.01)
        assert signal.evidence["credibility_delta"] == pytest.approx(0.30, rel=0.01)
