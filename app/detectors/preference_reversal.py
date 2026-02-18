"""
PreferenceReversalDetector - Detects when user opinions flip polarity.

Identifies drift by checking conflict_snapshots for polarity reversals
(POSITIVE → NEGATIVE or vice versa) on the same target.
"""

import logging
import time
from typing import List, Optional

from app.detectors.base import BaseDetector
from app.models.behavior import BehaviorRecord, ConflictRecord
from app.models.drift import DriftSignal, DriftType
from app.models.snapshot import BehaviorSnapshot


logger = logging.getLogger(__name__)


class PreferenceReversalDetector(BaseDetector):
    """
    Detects preference reversals (polarity flips) in user behavior.
    
    This is the easiest detector since conflicts are pre-identified in the
    conflict_snapshots table. We simply filter for polarity reversals and
    score them based on behavior credibility.
    """
    
    def detect(
        self,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> List[DriftSignal]:
        """
        Detect preference reversals by analyzing conflict records.
        
        Args:
            reference: Historical behavior snapshot
            current: Current behavior snapshot
            
        Returns:
            List of DriftSignal objects for detected reversals
            
        Examples:
            >>> detector = PreferenceReversalDetector()
            >>> signals = detector.detect(reference_snapshot, current_snapshot)
            >>> len(signals)  # Number of reversals found
        """
        start_time = time.time()
        signals = []
        
        # Validate inputs
        try:
            self._validate_snapshots(reference, current)
        except (ValueError, TypeError) as e:
            logger.error(f"Snapshot validation failed: {e}")
            return signals
        
        # Get all conflicts from current snapshot
        conflicts = current.conflict_records
        
        if not conflicts:
            logger.debug(
                "No conflicts in current snapshot",
                extra={"user_id": current.user_id, "conflict_count": 0}
            )
            return signals
        
        logger.debug(
            f"Analyzing {len(conflicts)} conflicts for polarity reversals",
            extra={"user_id": current.user_id, "conflict_count": len(conflicts)}
        )
        
        # Check each conflict for polarity reversal
        for conflict in conflicts:
            if not conflict.is_polarity_reversal:
                continue
            
            # Calculate drift score based on behavior credibilities
            signal = self._create_reversal_signal(conflict, reference, current)
            
            if signal:
                signals.append(signal)
                logger.info(
                    f"Detected preference reversal: {conflict.old_polarity} → "
                    f"{conflict.new_polarity} for target (conflict_id={conflict.conflict_id})",
                    extra={
                        "user_id": current.user_id,
                        "conflict_id": conflict.conflict_id,
                        "old_polarity": conflict.old_polarity,
                        "new_polarity": conflict.new_polarity,
                        "drift_score": signal.drift_score
                    }
                )
        
        elapsed = time.time() - start_time
        logger.info(
            f"PreferenceReversalDetector completed in {elapsed:.3f}s: {len(signals)} signal(s)",
            extra={
                "user_id": current.user_id,
                "execution_time_seconds": elapsed,
                "signals_found": len(signals),
                "conflicts_analyzed": len(conflicts)
            }
        )
        
        return signals
    
    def _create_reversal_signal(
        self,
        conflict: ConflictRecord,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> Optional[DriftSignal]:
        """
        Create a drift signal for a polarity reversal conflict.
        
        Args:
            conflict: Conflict record with polarity reversal
            reference: Historical snapshot
            current: Current snapshot
            
        Returns:
            DriftSignal or None if behaviors not found
        """
        # Find the old and new behaviors
        old_behavior = self._find_behavior_by_id(
            reference, conflict.behavior_id_1
        ) or self._find_behavior_by_id(current, conflict.behavior_id_1)
        
        new_behavior = self._find_behavior_by_id(
            current, conflict.behavior_id_2
        ) or self._find_behavior_by_id(reference, conflict.behavior_id_2)
        
        if not old_behavior or not new_behavior:
            logger.warning(
                f"Could not find behaviors for conflict {conflict.conflict_id}: "
                f"old={conflict.behavior_id_1}, new={conflict.behavior_id_2}"
            )
            return None
        
        # Calculate drift score: average of credibilities
        # Higher credibility = stronger signal
        drift_score = (old_behavior.credibility + new_behavior.credibility) / 2.0
        
        # Confidence is also based on credibilities
        confidence = drift_score
        
        # Determine the affected target (could be old or new target)
        affected_target = (
            conflict.old_target or conflict.new_target or 
            old_behavior.target or new_behavior.target
        )
        
        # Create evidence dictionary
        evidence = {
            "conflict_id": conflict.conflict_id,
            "old_polarity": conflict.old_polarity,
            "new_polarity": conflict.new_polarity,
            "old_credibility": round(old_behavior.credibility, 3),
            "new_credibility": round(new_behavior.credibility, 3),
            "old_behavior_id": conflict.behavior_id_1,
            "new_behavior_id": conflict.behavior_id_2,
            "target": affected_target,
        }
        
        # Add target migration info if present
        if conflict.is_target_migration:
            evidence["old_target"] = conflict.old_target
            evidence["new_target"] = conflict.new_target
            evidence["is_target_migration"] = True
        
        # Create and return signal
        return self._create_signal(
            drift_type=DriftType.PREFERENCE_REVERSAL,
            drift_score=drift_score,
            affected_targets=[affected_target],
            evidence=evidence,
            confidence=confidence
        )
    
    def _find_behavior_by_id(
        self,
        snapshot: BehaviorSnapshot,
        behavior_id: str
    ) -> Optional[BehaviorRecord]:
        """
        Find a behavior by its ID in a snapshot.
        
        Args:
            snapshot: BehaviorSnapshot to search
            behavior_id: ID of behavior to find
            
        Returns:
            BehaviorRecord or None if not found
        """
        for behavior in snapshot.behaviors:
            if behavior.behavior_id == behavior_id:
                return behavior
        return None
