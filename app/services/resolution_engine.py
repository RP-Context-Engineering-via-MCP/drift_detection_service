"""
Behavior Resolution Engine.

This service orchestrates the conflict resolution logic, integrating
drift detection with credibility-based decision making.
"""

import uuid
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.constants import BehaviorState, ResolutionAction
from app.core.logging_config import get_logger
from app.database.repositories import BehaviorRepository, DriftSignalRepository
from app.models.behavior import Behavior
from app.models.drift_signal import DriftSignal
from app.models.schemas import CanonicalBehaviorInput, ResolutionDetail
from app.services.drift_detector import DriftAnalysis, DriftDetector
from app.utils.datetime_helpers import now_utc

logger = get_logger(__name__)


class ResolutionEngine:
    """
    Orchestrates behavior conflict resolution with drift awareness.
    
    This engine combines:
    1. Semantic retrieval (finding related behaviors)
    2. Drift analysis (temporal decay + accumulation)
    3. Resolution logic (SUPERSEDE/REINFORCE/INSERT/IGNORE)
    """

    def __init__(self, db: Session):
        """
        Initialize resolution engine.
        
        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
        self.behavior_repo = BehaviorRepository(db)
        self.drift_repo = DriftSignalRepository(db)
        self.drift_detector = DriftDetector()

    def process_behavior(
        self, user_id: str, candidate: CanonicalBehaviorInput
    ) -> ResolutionDetail:
        """
        Process a single behavior candidate through the resolution pipeline.
        
        Pipeline:
        1. Semantic Retrieval: Find related behaviors
        2. For each candidate:
           a. Calculate effective credibility (drift)
           b. Check drift signals (accumulation)
           c. Decide resolution action
        3. Execute action and log results
        
        Args:
            user_id: User identifier
            candidate: Canonical behavior from extraction service
        
        Returns:
            ResolutionDetail describing the action taken
        """
        logger.info(
            f"Processing behavior for user {user_id}: "
            f"{candidate.intent} - {candidate.target}"
        )

        # Step 1: Semantic Retrieval
        semantic_candidates = self._find_semantic_matches(user_id, candidate)

        if not semantic_candidates:
            # No conflict - simple insert
            return self._insert_new_behavior(user_id, candidate)

        # Step 2: Analyze each candidate for drift and conflict
        best_match, distance = semantic_candidates[0]
        
        # Get drift signal count for accumulation detection
        drift_signal_count = self.drift_repo.count_recent_signals(
            best_match.behavior_id, self.settings.drift_signal_window_days
        )

        # Perform drift analysis
        drift_analysis = self.drift_detector.analyze_behavior_drift(
            best_match, drift_signal_count
        )

        # Step 3: Resolution Decision
        return self._resolve_conflict(
            user_id=user_id,
            candidate=candidate,
            existing=best_match,
            drift_analysis=drift_analysis,
            semantic_distance=distance,
        )

    def _find_semantic_matches(
        self, user_id: str, candidate: CanonicalBehaviorInput
    ) -> List[Tuple[Behavior, float]]:
        """
        Find semantically similar behaviors using vector search.
        
        Args:
            user_id: User identifier
            candidate: Behavior to match
        
        Returns:
            List of (Behavior, distance) tuples
        """
        if not candidate.embedding:
            logger.warning("No embedding provided, skipping semantic search")
            return []

        return self.behavior_repo.find_semantic_candidates(
            user_id=user_id,
            embedding=candidate.embedding,
            distance_threshold=self.settings.semantic_gate_threshold,
            limit=self.settings.max_semantic_candidates,
        )

    def _resolve_conflict(
        self,
        user_id: str,
        candidate: CanonicalBehaviorInput,
        existing: Behavior,
        drift_analysis: DriftAnalysis,
        semantic_distance: float,
    ) -> ResolutionDetail:
        """
        Execute resolution logic based on drift analysis and credibility.
        
        Decision Tree:
        1. If drift accumulation detected → FORCE SUPERSEDE
        2. If new_credibility > effective_existing_credibility → SUPERSEDE
        3. If behaviors are identical (reinforcement) → REINFORCE
        4. If new_credibility <= effective_credibility → IGNORE (log signal)
        
        Args:
            user_id: User identifier
            candidate: New behavior
            existing: Existing behavior
            drift_analysis: Drift analysis results
            semantic_distance: Semantic similarity distance
        
        Returns:
            ResolutionDetail with action taken
        """
        new_credibility = candidate.extracted_credibility
        effective_credibility = drift_analysis.effective_credibility

        # CASE 1: Drift Accumulation Forces Supersede
        if self.drift_detector.should_force_supersede(drift_analysis, new_credibility):
            return self._supersede_behavior(
                user_id, candidate, existing, drift_analysis, forced_by_drift=True
            )

        # CASE 2: New credibility beats decayed existing credibility
        if new_credibility > effective_credibility:
            return self._supersede_behavior(
                user_id, candidate, existing, drift_analysis, forced_by_drift=False
            )

        # CASE 3: Reinforcement (same behavior, update credibility)
        if self._is_reinforcement(candidate, existing):
            return self._reinforce_behavior(candidate, existing, drift_analysis)

        # CASE 4: New signal is weaker - IGNORE but log drift signal
        return self._ignore_and_log(user_id, candidate, existing, drift_analysis)

    def _supersede_behavior(
        self,
        user_id: str,
        candidate: CanonicalBehaviorInput,
        existing: Behavior,
        drift_analysis: DriftAnalysis,
        forced_by_drift: bool,
    ) -> ResolutionDetail:
        """Execute SUPERSEDE action."""
        new_behavior = Behavior(
            user_id=user_id,
            intent=candidate.intent,
            target=candidate.target,
            context=candidate.context,
            polarity=candidate.polarity,
            credibility=candidate.extracted_credibility,
            reinforcement_count=1,
            state=BehaviorState.ACTIVE.value,
            embedding=candidate.embedding,
            last_seen_at=now_utc(),
        )

        old_behavior, created_behavior = self.behavior_repo.supersede_behavior(
            existing.behavior_id, new_behavior
        )

        reason = (
            "Drift accumulation forced update"
            if forced_by_drift
            else f"New credibility ({candidate.extracted_credibility:.2f}) "
            f"exceeded decayed existing ({drift_analysis.effective_credibility:.2f})"
        )

        drift_type = self.drift_detector.classify_drift_type(
            existing,
            candidate.intent,
            candidate.target,
            candidate.polarity,
            candidate.context,
        )

        logger.info(
            f"SUPERSEDE: {existing.behavior_id} -> {created_behavior.behavior_id} "
            f"({drift_type.value})"
        )

        return ResolutionDetail(
            type=ResolutionAction.SUPERSEDE,
            reason=reason,
            details=f"Drift type: {drift_type.value}. {drift_analysis.reason}",
            old_behavior_id=existing.behavior_id,
            new_behavior_id=created_behavior.behavior_id,
            drift_detected=forced_by_drift or drift_analysis.drift_detected,
            effective_credibility=drift_analysis.effective_credibility,
        )

    def _reinforce_behavior(
        self,
        candidate: CanonicalBehaviorInput,
        existing: Behavior,
        drift_analysis: DriftAnalysis,
    ) -> ResolutionDetail:
        """Execute REINFORCE action."""
        # Average the credibilities or take max
        updated_credibility = max(
            existing.credibility, candidate.extracted_credibility
        )

        updated = self.behavior_repo.update_credibility(
            existing.behavior_id, updated_credibility, increment_count=True
        )

        logger.info(
            f"REINFORCE: {existing.behavior_id} "
            f"(count: {updated.reinforcement_count}, cred: {updated_credibility:.2f})"
        )

        return ResolutionDetail(
            type=ResolutionAction.REINFORCE,
            reason=f"Behavior reinforced (occurrence #{updated.reinforcement_count})",
            details=f"Credibility updated from {existing.credibility:.2f} to {updated_credibility:.2f}",
            old_behavior_id=existing.behavior_id,
            new_behavior_id=existing.behavior_id,
            drift_detected=False,
            effective_credibility=drift_analysis.effective_credibility,
        )

    def _insert_new_behavior(
        self, user_id: str, candidate: CanonicalBehaviorInput
    ) -> ResolutionDetail:
        """Execute INSERT action (no conflict found)."""
        new_behavior = Behavior(
            user_id=user_id,
            intent=candidate.intent,
            target=candidate.target,
            context=candidate.context,
            polarity=candidate.polarity,
            credibility=candidate.extracted_credibility,
            reinforcement_count=1,
            state=BehaviorState.ACTIVE.value,
            embedding=candidate.embedding,
            last_seen_at=now_utc(),
        )

        created = self.behavior_repo.create(new_behavior)

        logger.info(f"INSERT: New behavior {created.behavior_id}")

        return ResolutionDetail(
            type=ResolutionAction.INSERT,
            reason="No conflicting behavior found",
            details=f"Created new behavior for: {candidate.target}",
            old_behavior_id=None,
            new_behavior_id=created.behavior_id,
            drift_detected=False,
            effective_credibility=None,
        )

    def _ignore_and_log(
        self,
        user_id: str,
        candidate: CanonicalBehaviorInput,
        existing: Behavior,
        drift_analysis: DriftAnalysis,
    ) -> ResolutionDetail:
        """Execute IGNORE action and log drift signal."""
        # Log this attempt for future drift detection
        drift_signal = DriftSignal(
            user_id=user_id,
            existing_behavior_id=existing.behavior_id,
            new_intent=candidate.intent,
            new_target=candidate.target,
            new_polarity=candidate.polarity,
            new_context=candidate.context,
            new_credibility=candidate.extracted_credibility,
            drift_type=self.drift_detector.classify_drift_type(
                existing,
                candidate.intent,
                candidate.target,
                candidate.polarity,
                candidate.context,
            ).value,
        )

        self.drift_repo.create(drift_signal)

        logger.info(
            f"IGNORE: Weak signal for {existing.behavior_id} "
            f"(new: {candidate.extracted_credibility:.2f} vs "
            f"effective: {drift_analysis.effective_credibility:.2f})"
        )

        return ResolutionDetail(
            type=ResolutionAction.IGNORE,
            reason=(
                f"New credibility ({candidate.extracted_credibility:.2f}) "
                f"below existing ({drift_analysis.effective_credibility:.2f})"
            ),
            details=f"Drift signal logged. Count: {drift_analysis.drift_signal_count + 1}",
            old_behavior_id=existing.behavior_id,
            new_behavior_id=None,
            drift_detected=drift_analysis.drift_detected,
            effective_credibility=drift_analysis.effective_credibility,
        )

    def _is_reinforcement(
        self, candidate: CanonicalBehaviorInput, existing: Behavior
    ) -> bool:
        """
        Check if candidate is a reinforcement of existing behavior.
        
        Args:
            candidate: New behavior
            existing: Existing behavior
        
        Returns:
            True if this is a reinforcement (same behavior)
        """
        return (
            candidate.intent == existing.intent
            and candidate.target.lower() == existing.target.lower()
            and candidate.polarity == existing.polarity
            and candidate.context == existing.context
        )
