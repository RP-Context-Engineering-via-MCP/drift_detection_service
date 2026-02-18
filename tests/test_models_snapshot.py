"""
Tests for BehaviorSnapshot data model.
"""

import pytest
from datetime import datetime, timedelta

from app.models.snapshot import BehaviorSnapshot
from tests.conftest import make_behavior, make_conflict, make_snapshot


class TestBehaviorSnapshot:
    """Tests for BehaviorSnapshot data model."""
    
    def test_create_empty_snapshot(self):
        """Test creating a snapshot with no behaviors."""
        snapshot = make_snapshot(behaviors=[], conflicts=[])
        
        assert snapshot.user_id == "test_user"
        assert snapshot.total_behaviors == 0
        assert snapshot.active_behavior_count == 0
        assert snapshot.conflict_count == 0
        assert len(snapshot.get_targets()) == 0
    
    def test_create_snapshot_with_behaviors(self):
        """Test creating a snapshot with multiple behaviors."""
        behaviors = [
            make_behavior(target="python", reinforcement_count=5),
            make_behavior(target="javascript", reinforcement_count=3),
            make_behavior(target="typescript", reinforcement_count=2),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        
        assert snapshot.total_behaviors == 3
        assert snapshot.active_behavior_count == 3
        assert len(snapshot.get_targets()) == 3
    
    def test_topic_distribution_calculation(self):
        """Test that topic distribution is calculated correctly."""
        behaviors = [
            make_behavior(target="python", reinforcement_count=6),
            make_behavior(target="javascript", reinforcement_count=3),
            make_behavior(target="rust", reinforcement_count=1),
        ]
        # Total reinforcements = 10
        
        snapshot = make_snapshot(behaviors=behaviors)
        dist = snapshot.topic_distribution
        
        assert dist["python"] == 0.6  # 6/10
        assert dist["javascript"] == 0.3  # 3/10
        assert dist["rust"] == 0.1  # 1/10
        assert sum(dist.values()) == pytest.approx(1.0)
    
    def test_intent_distribution_calculation(self):
        """Test that intent distribution is calculated correctly."""
        behaviors = [
            make_behavior(intent="PREFERENCE"),
            make_behavior(intent="PREFERENCE"),
            make_behavior(intent="SKILL"),
            make_behavior(intent="HABIT"),
        ]
        # Total: 4 behaviors
        
        snapshot = make_snapshot(behaviors=behaviors)
        dist = snapshot.intent_distribution
        
        assert dist["PREFERENCE"] == 0.5  # 2/4
        assert dist["SKILL"] == 0.25  # 1/4
        assert dist["HABIT"] == 0.25  # 1/4
        assert sum(dist.values()) == pytest.approx(1.0)
    
    def test_polarity_by_target_most_recent(self):
        """Test that polarity_by_target uses most recent behavior."""
        now_ts = int(datetime.now().timestamp())
        
        behaviors = [
            make_behavior(
                target="python",
                polarity="POSITIVE",
                last_seen_at=now_ts - 10000,  # Older
            ),
            make_behavior(
                target="python",
                polarity="NEGATIVE",
                last_seen_at=now_ts - 1000,  # More recent
            ),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        polarity = snapshot.polarity_by_target
        
        # Should use the more recent NEGATIVE polarity
        assert polarity["python"] == "NEGATIVE"
    
    def test_get_behaviors_by_target(self):
        """Test filtering behaviors by target."""
        behaviors = [
            make_behavior(target="python"),
            make_behavior(target="python"),
            make_behavior(target="javascript"),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        python_behaviors = snapshot.get_behaviors_by_target("python")
        
        assert len(python_behaviors) == 2
        assert all(b.target == "python" for b in python_behaviors)
    
    def test_get_active_behaviors(self):
        """Test filtering to only active behaviors."""
        behaviors = [
            make_behavior(target="python", state="ACTIVE"),
            make_behavior(target="javascript", state="ACTIVE"),
            make_behavior(target="rust", state="SUPERSEDED"),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        active = snapshot.get_active_behaviors()
        
        assert len(active) == 2
        assert all(b.state == "ACTIVE" for b in active)
    
    def test_get_reinforcement_count(self):
        """Test summing reinforcement counts for a target."""
        behaviors = [
            make_behavior(target="python", reinforcement_count=3),
            make_behavior(target="python", reinforcement_count=5),
            make_behavior(target="javascript", reinforcement_count=2),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        
        python_count = snapshot.get_reinforcement_count("python")
        javascript_count = snapshot.get_reinforcement_count("javascript")
        
        assert python_count == 8  # 3 + 5
        assert javascript_count == 2
    
    def test_get_targets(self):
        """Test getting unique set of targets."""
        behaviors = [
            make_behavior(target="python"),
            make_behavior(target="python"),
            make_behavior(target="javascript"),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        targets = snapshot.get_targets()
        
        assert targets == {"python", "javascript"}
        assert len(targets) == 2
    
    def test_get_contexts_for_target(self):
        """Test getting contexts associated with a target."""
        behaviors = [
            make_behavior(target="python", context="backend"),
            make_behavior(target="python", context="data science"),
            make_behavior(target="javascript", context="frontend"),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        python_contexts = snapshot.get_contexts_for_target("python")
        
        assert python_contexts == {"backend", "data science"}
    
    def test_get_average_credibility(self):
        """Test calculating average credibility for a target."""
        behaviors = [
            make_behavior(target="python", credibility=0.8),
            make_behavior(target="python", credibility=0.6),
            make_behavior(target="javascript", credibility=0.9),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        
        python_avg = snapshot.get_average_credibility("python")
        javascript_avg = snapshot.get_average_credibility("javascript")
        
        assert python_avg == 0.7  # (0.8 + 0.6) / 2
        assert javascript_avg == 0.9
    
    def test_has_target(self):
        """Test checking if target exists."""
        behaviors = [
            make_behavior(target="python"),
            make_behavior(target="javascript"),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        
        assert snapshot.has_target("python") is True
        assert snapshot.has_target("javascript") is True
        assert snapshot.has_target("rust") is False
    
    def test_get_polarity_reversals(self):
        """Test filtering conflicts to polarity reversals."""
        conflicts = [
            make_conflict(
                old_polarity="POSITIVE",
                new_polarity="NEGATIVE",
            ),
            make_conflict(
                old_polarity="POSITIVE",
                new_polarity="POSITIVE",
            ),
            make_conflict(
                old_target="vim",
                new_target="vscode",
            ),
        ]
        
        snapshot = make_snapshot(conflicts=conflicts)
        reversals = snapshot.get_polarity_reversals()
        
        assert len(reversals) == 1
        assert reversals[0].is_polarity_reversal is True
    
    def test_get_target_migrations(self):
        """Test filtering conflicts to target migrations."""
        conflicts = [
            make_conflict(
                old_target="vim",
                new_target="vscode",
            ),
            make_conflict(
                old_polarity="POSITIVE",
                new_polarity="NEGATIVE",
            ),
        ]
        
        snapshot = make_snapshot(conflicts=conflicts)
        migrations = snapshot.get_target_migrations()
        
        assert len(migrations) == 1
        assert migrations[0].is_target_migration is True
    
    def test_window_days_property(self):
        """Test calculating window size in days."""
        snapshot = make_snapshot(days_ago_start=30, days_ago_end=0)
        
        # Should be approximately 30 days
        assert 29 <= snapshot.window_days <= 31
    
    def test_superseded_behaviors_excluded_from_distributions(self):
        """Test that SUPERSEDED behaviors don't affect distributions."""
        behaviors = [
            make_behavior(target="python", reinforcement_count=5, state="ACTIVE"),
            make_behavior(target="python", reinforcement_count=10, state="SUPERSEDED"),
        ]
        
        snapshot = make_snapshot(behaviors=behaviors)
        
        # Only ACTIVE behavior should count
        assert snapshot.active_behavior_count == 1
        assert snapshot.get_reinforcement_count("python") == 5  # Not 15
