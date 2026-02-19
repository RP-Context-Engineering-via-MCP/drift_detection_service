"""
BehaviorSnapshot data model.

Represents a user's complete behavior profile within a specific time window.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Set
from collections import defaultdict

from app.models.behavior import BehaviorRecord, ConflictRecord


@dataclass
class BehaviorSnapshot:
    """
    Represents a user's behavior profile within a specific time window.
    
    Contains all behaviors and conflicts in the window, plus computed
    distributions and aggregations for drift analysis.
    
    For reference (historical) windows, set include_superseded=True to include
    behaviors that were active during that window even if now superseded.
    """
    
    user_id: str
    window_start: datetime
    window_end: datetime
    behaviors: List[BehaviorRecord] = field(default_factory=list)
    conflict_records: List[ConflictRecord] = field(default_factory=list)
    include_superseded: bool = False  # True for reference/historical windows
    
    # Computed distributions (lazy-loaded)
    _topic_distribution: Dict[str, float] = field(default_factory=dict, repr=False, init=False)
    _intent_distribution: Dict[str, float] = field(default_factory=dict, repr=False, init=False)
    _polarity_by_target: Dict[str, str] = field(default_factory=dict, repr=False, init=False)
    _computed: bool = field(default=False, repr=False, init=False)
    
    def __post_init__(self):
        """Compute distributions after initialization."""
        self._compute_distributions()
    
    def _compute_distributions(self) -> None:
        """
        Compute topic, intent distributions and polarity mappings.
        Called automatically after initialization.
        """
        if self._computed:
            return
        
        # Use all behaviors if include_superseded, else only ACTIVE
        relevant_behaviors = (
            self.behaviors if self.include_superseded 
            else [b for b in self.behaviors if b.is_active]
        )
        
        if not relevant_behaviors:
            self._computed = True
            return
        
        # ─── Topic Distribution (based on reinforcement_count) ───
        total_reinforcements = sum(b.reinforcement_count for b in relevant_behaviors)
        
        if total_reinforcements > 0:
            target_reinforcements = defaultdict(int)
            for behavior in relevant_behaviors:
                target_reinforcements[behavior.target] += behavior.reinforcement_count
            
            self._topic_distribution = {
                target: count / total_reinforcements
                for target, count in target_reinforcements.items()
            }
        
        # ─── Intent Distribution ───────────────────────────────────
        total_behaviors = len(relevant_behaviors)
        intent_counts = defaultdict(int)
        
        for behavior in relevant_behaviors:
            intent_counts[behavior.intent] += 1
        
        self._intent_distribution = {
            intent: count / total_behaviors
            for intent, count in intent_counts.items()
        }
        
        # ─── Polarity by Target (most recent wins) ────────────────
        target_behaviors = defaultdict(list)
        for behavior in relevant_behaviors:
            target_behaviors[behavior.target].append(behavior)
        
        # For each target, take the polarity of the most recent behavior
        for target, behaviors_list in target_behaviors.items():
            most_recent = max(behaviors_list, key=lambda b: b.last_seen_at)
            self._polarity_by_target[target] = most_recent.polarity
        
        self._computed = True
    
    @property
    def topic_distribution(self) -> Dict[str, float]:
        """
        Get topic distribution (target → share of total reinforcement).
        
        Returns:
            Dictionary mapping target to percentage (0.0-1.0)
        """
        return self._topic_distribution
    
    @property
    def intent_distribution(self) -> Dict[str, float]:
        """
        Get intent distribution (intent → share of behaviors).
        
        Returns:
            Dictionary mapping intent to percentage (0.0-1.0)
        """
        return self._intent_distribution
    
    @property
    def polarity_by_target(self) -> Dict[str, str]:
        """
        Get current polarity for each target.
        
        Returns:
            Dictionary mapping target to polarity (POSITIVE/NEGATIVE)
        """
        return self._polarity_by_target
    
    # ─── Helper Methods ──────────────────────────────────────────────────
    
    def get_behaviors_by_target(self, target: str) -> List[BehaviorRecord]:
        """
        Get all behaviors for a specific target.
        
        Args:
            target: Target to filter by
            
        Returns:
            List of behaviors matching the target
        """
        return [b for b in self.behaviors if b.target == target]
    
    def get_active_behaviors(self) -> List[BehaviorRecord]:
        """
        Get only active behaviors (excluding superseded).
        
        Returns:
            List of active BehaviorRecords
        """
        return [b for b in self.behaviors if b.is_active]
    
    def _get_relevant_behaviors(self) -> List[BehaviorRecord]:
        """
        Get behaviors relevant for this snapshot's analysis.
        
        For reference/historical windows (include_superseded=True), returns all behaviors.
        For current windows (include_superseded=False), returns only ACTIVE behaviors.
        
        Returns:
            List of relevant BehaviorRecords
        """
        if self.include_superseded:
            return self.behaviors
        return [b for b in self.behaviors if b.is_active]
    
    def get_reinforcement_count(self, target: str) -> int:
        """
        Get total reinforcement count for a target.
        
        Args:
            target: Target to sum reinforcements for
            
        Returns:
            Total reinforcement count
        """
        return sum(
            b.reinforcement_count 
            for b in self._get_relevant_behaviors()
            if b.target == target
        )
    
    def get_targets(self) -> Set[str]:
        """
        Get set of all unique targets in this snapshot.
        
        Returns:
            Set of target strings
        """
        return {b.target for b in self._get_relevant_behaviors()}
    
    def get_contexts_for_target(self, target: str) -> Set[str]:
        """
        Get all contexts associated with a target.
        
        Args:
            target: Target to get contexts for
            
        Returns:
            Set of context strings
        """
        return {
            b.context 
            for b in self._get_relevant_behaviors()
            if b.target == target
        }
    
    def get_average_credibility(self, target: str) -> float:
        """
        Get average credibility for a target.
        
        Args:
            target: Target to calculate average for
            
        Returns:
            Average credibility (0.0-1.0) or 0.0 if no behaviors
        """
        target_behaviors = [
            b for b in self._get_relevant_behaviors()
            if b.target == target
        ]
        
        if not target_behaviors:
            return 0.0
        
        return sum(b.credibility for b in target_behaviors) / len(target_behaviors)
    
    def has_target(self, target: str) -> bool:
        """
        Check if target exists in this snapshot.
        
        Args:
            target: Target to check
            
        Returns:
            True if target exists
        """
        return any(b.target == target for b in self._get_relevant_behaviors())
    
    def get_polarity_reversals(self) -> List[ConflictRecord]:
        """
        Get all conflicts that represent polarity reversals.
        
        Returns:
            List of ConflictRecords with polarity reversals
        """
        return [c for c in self.conflict_records if c.is_polarity_reversal]
    
    def get_target_migrations(self) -> List[ConflictRecord]:
        """
        Get all conflicts that represent target migrations.
        
        Returns:
            List of ConflictRecords with target migrations
        """
        return [c for c in self.conflict_records if c.is_target_migration]
    
    @property
    def total_behaviors(self) -> int:
        """Get total number of behaviors (all states)."""
        return len(self.behaviors)
    
    @property
    def active_behavior_count(self) -> int:
        """Get count of active behaviors."""
        return len([b for b in self.behaviors if b.is_active])
    
    @property
    def conflict_count(self) -> int:
        """Get total number of conflicts."""
        return len(self.conflict_records)
    
    @property
    def window_days(self) -> int:
        """Get window size in days."""
        return (self.window_end - self.window_start).days
    
    def __repr__(self) -> str:
        return (
            f"BehaviorSnapshot(user_id={self.user_id!r}, "
            f"window={self.window_start.date()}→{self.window_end.date()}, "
            f"behaviors={self.active_behavior_count}/{self.total_behaviors}, "
            f"conflicts={self.conflict_count}, "
            f"topics={len(self.get_targets())})"
        )
