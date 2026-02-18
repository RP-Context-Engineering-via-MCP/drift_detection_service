"""
Tests for PreferenceReversalDetector.

Tests detection of polarity reversals (POSITIVE ↔ NEGATIVE) using conflict records.
"""

import pytest
from datetime import datetime, timedelta

from app.detectors.preference_reversal import PreferenceReversalDetector
from app.models.drift import DriftType
from tests.conftest import make_behavior, make_conflict, make_snapshot, days_ago


class TestPreferenceReversalDetector:
    """Test suite for PreferenceReversalDetector."""
    
    def test_polarity_flip_creates_signal(self):
        """Test that POSITIVE → NEGATIVE creates a drift signal."""
        # Create behaviors representing old and new opinions
        old_behavior = make_behavior(
            behavior_id="beh_old",
            target="remote work",
            polarity="POSITIVE",
            credibility=0.8,
            last_seen_at=days_ago(40)
        )
        
        new_behavior = make_behavior(
            behavior_id="beh_new",
            target="remote work",
            polarity="NEGATIVE",
            credibility=0.9,
            last_seen_at=days_ago(5)
        )
        
        # Create conflict linking them
        conflict = make_conflict(
            conflict_id="conf_reversal",
            behavior_id_1="beh_old",
            behavior_id_2="beh_new",
            old_polarity="POSITIVE",
            new_polarity="NEGATIVE",
            old_target="remote work",
            new_target="remote work",
            conflict_type="USER_DECISION_NEEDED",
            resolution_status="PENDING"
        )
        
        # Create snapshots
        reference = make_snapshot(
            behaviors=[old_behavior],
            conflicts=[],
            days_ago_start=60,
            days_ago_end=30
        )
        
        current = make_snapshot(
            behaviors=[new_behavior],
            conflicts=[conflict],
            days_ago_start=30,
            days_ago_end=0
        )
        
        # Run detector
        detector = PreferenceReversalDetector()
        signals = detector.detect(reference, current)
        
        # Assert signal created
        assert len(signals) == 1
        signal = signals[0]
        
        assert signal.drift_type == DriftType.PREFERENCE_REVERSAL
        assert "remote work" in signal.affected_targets
        assert signal.evidence["old_polarity"] == "POSITIVE"
        assert signal.evidence["new_polarity"] == "NEGATIVE"
        assert signal.evidence["conflict_id"] == "conf_reversal"
        
        # Drift score should be average of credibilities
        expected_score = (0.8 + 0.9) / 2
        assert signal.drift_score == pytest.approx(expected_score, rel=0.01)
    
    def test_same_polarity_no_signal(self):
        """Test that same polarity (no reversal) produces no signal."""
        # Both behaviors have POSITIVE polarity
        old_behavior = make_behavior(
            behavior_id="beh_old",
            polarity="POSITIVE"
        )
        
        new_behavior = make_behavior(
            behavior_id="beh_new",
            polarity="POSITIVE"
        )
        
        # Conflict without polarity reversal
        conflict = make_conflict(
            behavior_id_1="beh_old",
            behavior_id_2="beh_new",
            old_polarity="POSITIVE",
            new_polarity="POSITIVE"  # Same!
        )
        
        reference = make_snapshot(behaviors=[old_behavior], conflicts=[])
        current = make_snapshot(behaviors=[new_behavior], conflicts=[conflict])
        
        detector = PreferenceReversalDetector()
        signals = detector.detect(reference, current)
        
        # No reversal = no signal
        assert len(signals) == 0
    
    def test_target_migration_detected(self):
        """Test that target migrations are detected and flagged."""
        # User migrated from vim to vscode
        old_behavior = make_behavior(
            behavior_id="beh_vim",
            target="vim",
            credibility=0.85
        )
        
        new_behavior = make_behavior(
            behavior_id="beh_vscode",
            target="vscode",
            credibility=0.90
        )
        
        conflict = make_conflict(
            behavior_id_1="beh_vim",
            behavior_id_2="beh_vscode",
            old_target="vim",
            new_target="vscode",
            old_polarity="POSITIVE",
            new_polarity="POSITIVE"  # Polarity reversal too
        )
        
        # Wait, the conflict needs a polarity reversal for our detector
        # Let me fix this - migration WITH polarity change
        conflict = make_conflict(
            behavior_id_1="beh_vim",
            behavior_id_2="beh_vscode",
            old_target="vim",
            new_target="vscode",
            old_polarity="POSITIVE",
            new_polarity="NEGATIVE"
        )
        
        reference = make_snapshot(behaviors=[old_behavior], conflicts=[])
        current = make_snapshot(behaviors=[new_behavior], conflicts=[conflict])
        
        detector = PreferenceReversalDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Should flag as target migration
        assert signal.evidence.get("is_target_migration") is True
        assert signal.evidence["old_target"] == "vim"
        assert signal.evidence["new_target"] == "vscode"
    
    def test_high_credibility_high_score(self):
        """Test that high credibility behaviors produce high drift scores."""
        # Both behaviors have very high credibility
        old_behavior = make_behavior(
            behavior_id="beh_old",
            credibility=0.95
        )
        
        new_behavior = make_behavior(
            behavior_id="beh_new",
            credibility=0.92
        )
        
        conflict = make_conflict(
            behavior_id_1="beh_old",
            behavior_id_2="beh_new",
            old_polarity="POSITIVE",
            new_polarity="NEGATIVE"
        )
        
        reference = make_snapshot(behaviors=[old_behavior], conflicts=[])
        current = make_snapshot(behaviors=[new_behavior], conflicts=[conflict])
        
        detector = PreferenceReversalDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # High credibility should result in high score
        expected_score = (0.95 + 0.92) / 2
        assert signal.drift_score == pytest.approx(expected_score, rel=0.01)
        assert signal.drift_score > 0.9
    
    def test_low_credibility_low_score(self):
        """Test that low credibility behaviors produce low drift scores."""
        old_behavior = make_behavior(
            behavior_id="beh_old",
            credibility=0.2
        )
        
        new_behavior = make_behavior(
            behavior_id="beh_new",
            credibility=0.3
        )
        
        conflict = make_conflict(
            behavior_id_1="beh_old",
            behavior_id_2="beh_new",
            old_polarity="POSITIVE",
            new_polarity="NEGATIVE"
        )
        
        reference = make_snapshot(behaviors=[old_behavior], conflicts=[])
        current = make_snapshot(behaviors=[new_behavior], conflicts=[conflict])
        
        detector = PreferenceReversalDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 1
        signal = signals[0]
        
        # Low credibility should result in low score
        expected_score = (0.2 + 0.3) / 2
        assert signal.drift_score == pytest.approx(expected_score, rel=0.01)
        assert signal.drift_score < 0.3
    
    def test_empty_conflicts_no_signals(self):
        """Test that no conflicts produces no signals."""
        reference = make_snapshot(
            behaviors=[make_behavior()],
            conflicts=[]
        )
        
        current = make_snapshot(
            behaviors=[make_behavior()],
            conflicts=[]  # No conflicts!
        )
        
        detector = PreferenceReversalDetector()
        signals = detector.detect(reference, current)
        
        assert len(signals) == 0
    
    def test_multiple_reversals(self):
        """Test detection of multiple preference reversals."""
        # Create multiple reversals
        behaviors = [
            make_behavior(behavior_id="beh_remote_old", target="remote work", polarity="POSITIVE"),
            make_behavior(behavior_id="beh_remote_new", target="remote work", polarity="NEGATIVE"),
            make_behavior(behavior_id="beh_python_old", target="python", polarity="POSITIVE"),
            make_behavior(behavior_id="beh_python_new", target="python", polarity="NEGATIVE"),
        ]
        
        conflicts = [
            make_conflict(
                conflict_id="conf_remote",
                behavior_id_1="beh_remote_old",
                behavior_id_2="beh_remote_new",
                old_polarity="POSITIVE",
                new_polarity="NEGATIVE"
            ),
            make_conflict(
                conflict_id="conf_python",
                behavior_id_1="beh_python_old",
                behavior_id_2="beh_python_new",
                old_polarity="POSITIVE",
                new_polarity="NEGATIVE"
            ),
        ]
        
        reference = make_snapshot(behaviors=behaviors[:2], conflicts=[])
        current = make_snapshot(behaviors=behaviors[2:], conflicts=conflicts)
        
        detector = PreferenceReversalDetector()
        signals = detector.detect(reference, current)
        
        # Should detect both reversals
        assert len(signals) == 2
        
        conflict_ids = [s.evidence["conflict_id"] for s in signals]
        assert "conf_remote" in conflict_ids
        assert "conf_python" in conflict_ids
    
    def test_missing_behavior_handles_gracefully(self):
        """Test that missing behavior IDs are handled gracefully."""
        # Conflict references behaviors that don't exist in snapshots
        conflict = make_conflict(
            behavior_id_1="nonexistent_1",
            behavior_id_2="nonexistent_2",
            old_polarity="POSITIVE",
            new_polarity="NEGATIVE"
        )
        
        reference = make_snapshot(behaviors=[], conflicts=[])
        current = make_snapshot(behaviors=[], conflicts=[conflict])
        
        detector = PreferenceReversalDetector()
        signals = detector.detect(reference, current)
        
        # Should handle gracefully and produce no signal
        assert len(signals) == 0
