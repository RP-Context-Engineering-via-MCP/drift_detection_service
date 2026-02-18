"""
Tests for ContextShiftDetector.

Tests detection of context expansion and contraction patterns.
"""

import pytest

from app.detectors.context_shift import ContextShiftDetector
from app.models.drift import DriftType
from tests.conftest import make_behavior, make_snapshot


class TestContextShiftDetector:
    """Test suite for ContextShiftDetector."""
    
    def test_expansion_specific_to_general(self):
        """Test detection of context expansion (specific → general)."""
        # Reference: python in specific context
        ref_behaviors = [
            make_behavior(
                behavior_id="beh_py_1",
                target="python",
                context="data science"
            ),
            make_behavior(
                behavior_id="beh_py_2",
                target="python",
                context="machine learning"
            ),
        ]
        
        # Current: python in general context
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_py_3",
                target="python",
                context="general"
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        # Should detect expansion
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.drift_type == DriftType.CONTEXT_EXPANSION
        assert "python" in signal.affected_targets
        assert signal.evidence["shift_type"] == "EXPANSION"
        assert "general" in signal.evidence["current_contexts"]
        assert "general" not in signal.evidence["reference_contexts"]
    
    def test_contraction_general_to_specific(self):
        """Test detection of context contraction (general → specific)."""
        # Reference: docker in general context
        ref_behaviors = [
            make_behavior(
                behavior_id="beh_docker_1",
                target="docker",
                context="general"
            ),
        ]
        
        # Current: docker in specific contexts
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_docker_2",
                target="docker",
                context="microservices"
            ),
            make_behavior(
                behavior_id="beh_docker_3",
                target="docker",
                context="devops"
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        # Should detect contraction
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.drift_type == DriftType.CONTEXT_CONTRACTION
        assert "docker" in signal.affected_targets
        assert signal.evidence["shift_type"] == "CONTRACTION"
        assert "general" in signal.evidence["reference_contexts"]
        assert "general" not in signal.evidence["current_contexts"]
    
    def test_no_change_no_signal(self):
        """Test that unchanged contexts produce no signal."""
        # Same contexts in both windows
        ref_behaviors = [
            make_behavior(
                target="kubernetes",
                context="devops"
            ),
        ]
        
        cur_behaviors = [
            make_behavior(
                target="kubernetes",
                context="devops"
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        # No shift, no signal
        assert len(signals) == 0
    
    def test_context_addition_not_shift(self):
        """Test that adding context without general ↔ specific change is not a shift."""
        # Reference: python in "web" context
        ref_behaviors = [
            make_behavior(
                target="python",
                context="web"
            ),
        ]
        
        # Current: python in "web" and "api" contexts (addition, not shift)
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_py_1",
                target="python",
                context="web"
            ),
            make_behavior(
                behavior_id="beh_py_2",
                target="python",
                context="api"
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        # Adding specific contexts without general is not a shift
        assert len(signals) == 0
    
    def test_general_plus_specific_not_expansion(self):
        """Test that having both general and specific is not expansion if general existed."""
        # Reference: already has "general"
        ref_behaviors = [
            make_behavior(
                target="javascript",
                context="general"
            ),
        ]
        
        # Current: still has "general" + added "frontend"
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_js_1",
                target="javascript",
                context="general"
            ),
            make_behavior(
                behavior_id="beh_js_2",
                target="javascript",
                context="frontend"
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        # No expansion (already had general)
        assert len(signals) == 0
    
    def test_specific_plus_general_remains_not_contraction(self):
        """Test that keeping general while adding specific is not contraction."""
        # Reference: only "general"
        ref_behaviors = [
            make_behavior(
                target="go",
                context="general"
            ),
        ]
        
        # Current: "general" + "backend"
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_go_1",
                target="go",
                context="general"
            ),
            make_behavior(
                behavior_id="beh_go_2",
                target="go",
                context="backend"
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        # No contraction (still has general)
        assert len(signals) == 0
    
    def test_multiple_targets_shifts(self):
        """Test detection of shifts across multiple targets."""
        ref_behaviors = [
            # python: specific contexts
            make_behavior(
                behavior_id="beh_py_1",
                target="python",
                context="data science"
            ),
            # rust: general context
            make_behavior(
                behavior_id="beh_rust_1",
                target="rust",
                context="general"
            ),
        ]
        
        cur_behaviors = [
            # python: expanded to general
            make_behavior(
                behavior_id="beh_py_2",
                target="python",
                context="general"
            ),
            # rust: contracted to specific
            make_behavior(
                behavior_id="beh_rust_2",
                target="rust",
                context="systems"
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        # Should detect both shifts
        assert len(signals) == 2
        
        # Find signals by target
        python_signal = next(s for s in signals if "python" in s.affected_targets)
        rust_signal = next(s for s in signals if "rust" in s.affected_targets)
        
        assert python_signal.evidence["shift_type"] == "EXPANSION"
        assert rust_signal.evidence["shift_type"] == "CONTRACTION"
    
    def test_contexts_added_and_removed_tracking(self):
        """Test that added and removed contexts are tracked in evidence."""
        ref_behaviors = [
            make_behavior(
                behavior_id="beh_1",
                target="topic",
                context="context1"
            ),
            make_behavior(
                behavior_id="beh_2",
                target="topic",
                context="context2"
            ),
        ]
        
        cur_behaviors = [
            make_behavior(
                behavior_id="beh_3",
                target="topic",
                context="context2"  # Kept
            ),
            make_behavior(
                behavior_id="beh_4",
                target="topic",
                context="context3"  # Added
            ),
            make_behavior(
                behavior_id="beh_5",
                target="topic",
                context="general"  # Added (expansion)
            ),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Check tracking
        assert "context1" in signal.evidence["contexts_removed"]
        assert "context3" in signal.evidence["contexts_added"]
        assert "general" in signal.evidence["contexts_added"]
    
    def test_drift_score_based_on_diversity_change(self):
        """Test that drift score increases with larger context diversity changes."""
        # Small change: 1 → 2 contexts
        ref_small = [
            make_behavior(target="topic1", context="web"),
        ]
        cur_small = [
            make_behavior(behavior_id="beh_1", target="topic1", context="general"),
        ]
        
        # Large change: 1 → 4 contexts
        ref_large = [
            make_behavior(target="topic2", context="specific"),
        ]
        cur_large = [
            make_behavior(behavior_id="beh_2", target="topic2", context="general"),
            make_behavior(behavior_id="beh_3", target="topic2", context="web"),
            make_behavior(behavior_id="beh_4", target="topic2", context="api"),
        ]
        
        reference = make_snapshot(behaviors=ref_small + ref_large)
        current = make_snapshot(behaviors=cur_small + cur_large)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 2
        
        signal_small = next(s for s in signals if "topic1" in s.affected_targets)
        signal_large = next(s for s in signals if "topic2" in s.affected_targets)
        
        # Larger diversity change should have higher score
        assert signal_large.drift_score > signal_small.drift_score
    
    def test_confidence_based_on_context_count(self):
        """Test that confidence increases with more contexts involved."""
        # Few contexts
        ref_few = [
            make_behavior(target="topic1", context="specific"),
        ]
        cur_few = [
            make_behavior(target="topic1", context="general"),
        ]
        
        # Many contexts
        ref_many = [
            make_behavior(behavior_id="beh_1", target="topic2", context="ctx1"),
            make_behavior(behavior_id="beh_2", target="topic2", context="ctx2"),
            make_behavior(behavior_id="beh_3", target="topic2", context="ctx3"),
        ]
        cur_many = [
            make_behavior(behavior_id="beh_4", target="topic2", context="general"),
            make_behavior(behavior_id="beh_5", target="topic2", context="ctx4"),
            make_behavior(behavior_id="beh_6", target="topic2", context="ctx5"),
        ]
        
        reference = make_snapshot(behaviors=ref_few + ref_many)
        current = make_snapshot(behaviors=cur_few + cur_many)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 2
        
        signal_few = next(s for s in signals if "topic1" in s.affected_targets)
        signal_many = next(s for s in signals if "topic2" in s.affected_targets)
        
        # More contexts should have higher confidence
        assert signal_many.confidence > signal_few.confidence
    
    def test_empty_snapshots_no_error(self):
        """Test that empty snapshots are handled gracefully."""
        reference = make_snapshot(behaviors=[])
        current = make_snapshot(behaviors=[])
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 0
    
    def test_no_common_targets_no_signal(self):
        """Test that completely different targets produce no signals."""
        ref_behaviors = [
            make_behavior(target="python", context="web"),
        ]
        
        cur_behaviors = [
            make_behavior(target="rust", context="systems"),
        ]
        
        reference = make_snapshot(behaviors=ref_behaviors)
        current = make_snapshot(behaviors=cur_behaviors)
        
        detector = ContextShiftDetector()
        signals = detector.detect(reference, current)
        
        # No common targets, no shifts
        assert len(signals) == 0
