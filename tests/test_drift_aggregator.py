"""Tests for DriftAggregator."""

import pytest

from app.core.drift_aggregator import DriftAggregator
from app.models.drift import DriftSignal, DriftType


class TestDriftAggregator:
    """Test signal aggregation and deduplication."""

    def test_aggregate_empty_list(self):
        """Test aggregating empty list returns empty list."""
        aggregator = DriftAggregator()
        result = aggregator.aggregate([])
        assert result == []

    def test_aggregate_single_signal(self):
        """Test aggregating single signal returns it if above threshold."""
        aggregator = DriftAggregator()
        
        signal = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.8,
            affected_targets=["python"],
            evidence={"test": "data"},
            confidence=0.9,
        )
        
        result = aggregator.aggregate([signal])
        assert len(result) == 1
        assert result[0] == signal

    def test_filter_below_threshold(self):
        """Test that signals below threshold are filtered out."""
        aggregator = DriftAggregator()
        
        # Default threshold is 0.6
        weak_signal = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.3,  # Below threshold
            affected_targets=["python"],
            evidence={},
            confidence=0.5,
        )
        
        result = aggregator.aggregate([weak_signal])
        assert len(result) == 0

    def test_deduplicate_same_target_keeps_highest(self):
        """Test that only highest-scoring signal per target is kept."""
        aggregator = DriftAggregator()
        
        # Two signals for same target with different scores
        signal1 = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.7,
            affected_targets=["python"],
            evidence={"source": "signal1"},
            confidence=0.8,
        )
        
        signal2 = DriftSignal(
            drift_type=DriftType.INTENSITY_SHIFT,
            drift_score=0.9,  # Higher score
            affected_targets=["python"],
            evidence={"source": "signal2"},
            confidence=0.85,
        )
        
        result = aggregator.aggregate([signal1, signal2])
        
        # Should keep only signal2 (higher score)
        assert len(result) == 1
        assert result[0] == signal2
        assert result[0].drift_score == 0.9

    def test_multiple_targets_preserved(self):
        """Test that signals for different targets are all kept."""
        aggregator = DriftAggregator()
        
        signal1 = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.8,
            affected_targets=["python"],
            evidence={},
            confidence=0.9,
        )
        
        signal2 = DriftSignal(
            drift_type=DriftType.TOPIC_ABANDONMENT,
            drift_score=0.7,
            affected_targets=["javascript"],
            evidence={},
            confidence=0.85,
        )
        
        result = aggregator.aggregate([signal1, signal2])
        
        assert len(result) == 2
        # Results should be sorted by score descending
        assert result[0].drift_score >= result[1].drift_score

    def test_sort_by_score_descending(self):
        """Test that results are sorted by drift_score descending."""
        aggregator = DriftAggregator()
        
        signals = [
            DriftSignal(
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=0.7,
                affected_targets=["python"],
                evidence={},
                confidence=0.8,
            ),
            DriftSignal(
                drift_type=DriftType.TOPIC_ABANDONMENT,
                drift_score=0.9,
                affected_targets=["javascript"],
                evidence={},
                confidence=0.85,
            ),
            DriftSignal(
                drift_type=DriftType.PREFERENCE_REVERSAL,
                drift_score=0.65,
                affected_targets=["react"],
                evidence={},
                confidence=0.7,
            ),
        ]
        
        result = aggregator.aggregate(signals)
        
        assert len(result) == 3
        assert result[0].drift_score == 0.9
        assert result[1].drift_score == 0.7
        assert result[2].drift_score == 0.65

    def test_signal_with_multiple_targets(self):
        """Test handling of signals affecting multiple targets."""
        aggregator = DriftAggregator()
        
        # Signal affecting multiple targets
        signal = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.8,
            affected_targets=["pytorch", "tensorflow", "keras"],
            evidence={"cluster": True},
            confidence=0.9,
        )
        
        result = aggregator.aggregate([signal])
        
        assert len(result) == 1
        assert result[0] == signal
        assert len(result[0].affected_targets) == 3

    def test_deduplicate_complex_scenario(self):
        """Test deduplication with overlapping targets."""
        aggregator = DriftAggregator()
        
        # Multiple signals with overlapping targets
        signal1 = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.8,
            affected_targets=["python", "javascript"],
            evidence={"source": "signal1"},
            confidence=0.9,
        )
        
        signal2 = DriftSignal(
            drift_type=DriftType.INTENSITY_SHIFT,
            drift_score=0.7,
            affected_targets=["python"],  # Overlaps with signal1
            evidence={"source": "signal2"},
            confidence=0.85,
        )
        
        signal3 = DriftSignal(
            drift_type=DriftType.CONTEXT_EXPANSION,
            drift_score=0.9,
            affected_targets=["javascript"],  # Overlaps with signal1
            evidence={"source": "signal3"},
            confidence=0.95,
        )
        
        result = aggregator.aggregate([signal1, signal2, signal3])
        
        # For python: signal1 (0.8) wins over signal2 (0.7)
        # For javascript: signal3 (0.9) wins over signal1 (0.8)
        # So we expect signal1 and signal3
        assert len(result) == 2
        
        # Check that correct signals are kept
        kept_sources = {s.evidence["source"] for s in result}
        assert "signal1" in kept_sources
        assert "signal3" in kept_sources
        assert "signal2" not in kept_sources
