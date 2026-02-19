"""
Unit tests for DriftAggregator.

Tests for signal aggregation, deduplication, and filtering.
"""

import pytest
from app.core.drift_aggregator import DriftAggregator
from app.models.drift import DriftSignal, DriftType


class TestDriftAggregator:
    """Tests for DriftAggregator."""
    
    def test_aggregate_empty_signals(self, test_settings):
        """Test aggregating empty signal list."""
        aggregator = DriftAggregator()
        result = aggregator.aggregate([])
        assert result == []
    
    def test_aggregate_single_signal(self, sample_drift_signal, test_settings):
        """Test aggregating a single signal."""
        aggregator = DriftAggregator()
        result = aggregator.aggregate([sample_drift_signal])
        
        # High score signal should pass through
        assert len(result) == 1
        assert result[0] == sample_drift_signal
    
    def test_deduplication_by_target(self, drift_signal_factory, test_settings):
        """Test that signals are deduplicated by target, keeping highest score."""
        signals = [
            drift_signal_factory(
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=0.6,
                affected_targets=["python"],
            ),
            drift_signal_factory(
                drift_type=DriftType.INTENSITY_SHIFT,
                drift_score=0.9,  # Higher score
                affected_targets=["python"],
            ),
        ]
        
        aggregator = DriftAggregator()
        result = aggregator.aggregate(signals)
        
        # Should keep only the higher scoring signal
        assert len(result) == 1
        assert result[0].drift_score == 0.9
    
    def test_filter_below_threshold(self, drift_signal_factory, test_settings):
        """Test that signals below threshold are filtered out."""
        signals = [
            drift_signal_factory(drift_score=0.3, affected_targets=["low_score"]),  # Below 0.6
        ]
        
        aggregator = DriftAggregator()
        result = aggregator.aggregate(signals)
        
        # Should be filtered out
        assert len(result) == 0
    
    def test_multiple_targets_different_signals(self, drift_signal_factory, test_settings):
        """Test aggregating signals for different targets."""
        signals = [
            drift_signal_factory(
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=0.8,
                affected_targets=["python"],
            ),
            drift_signal_factory(
                drift_type=DriftType.TOPIC_EMERGENCE,
                drift_score=0.7,
                affected_targets=["rust"],
            ),
        ]
        
        aggregator = DriftAggregator()
        result = aggregator.aggregate(signals)
        
        # Both should pass through (different targets)
        assert len(result) == 2
    
    def test_sorting_by_score(self, drift_signal_factory, test_settings):
        """Test that results are sorted by drift score descending."""
        signals = [
            drift_signal_factory(drift_score=0.7, affected_targets=["target1"]),
            drift_signal_factory(drift_score=0.9, affected_targets=["target2"]),
            drift_signal_factory(drift_score=0.8, affected_targets=["target3"]),
        ]
        
        aggregator = DriftAggregator()
        result = aggregator.aggregate(signals)
        
        # Should be sorted by score descending
        scores = [s.drift_score for s in result]
        assert scores == sorted(scores, reverse=True)
    
    def test_invalid_signal_type_handling(self, test_settings):
        """Test handling of invalid signal types in list."""
        signals = [
            "not a signal",  # Invalid type
            None,  # None
        ]
        
        aggregator = DriftAggregator()
        
        # Should handle gracefully
        result = aggregator.aggregate(signals)
        assert result == []
    
    def test_signal_with_no_affected_targets(self, test_settings):
        """Test handling signal with empty affected_targets."""
        signal = DriftSignal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=0.8,
            affected_targets=[],  # Empty
            evidence={},
            confidence=0.9,
        )
        
        aggregator = DriftAggregator()
        result = aggregator.aggregate([signal])
        
        # Should be filtered out (no targets)
        assert len(result) == 0
