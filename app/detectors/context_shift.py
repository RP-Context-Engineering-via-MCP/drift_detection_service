"""
ContextShiftDetector - Detects changes in behavior context patterns.

Identifies drift when behaviors for the same target shift between specific
contexts and general contexts, indicating:
- EXPANSION: User moves from specific use-case to general application
- CONTRACTION: User narrows from general to specific contexts
"""

import logging
import time
from collections import defaultdict
from typing import Dict, List, Set

from app.detectors.base import BaseDetector
from app.models.drift import DriftSignal, DriftType
from app.models.snapshot import BehaviorSnapshot


logger = logging.getLogger(__name__)


class ContextShiftDetector(BaseDetector):
    """
    Detects context shifts for targets across reference and current windows.
    
    Two types of shifts:
    1. EXPANSION: Specific contexts → "general" (broadening application)
       Example: "python" in "data science" → "python" in "general"
    
    2. CONTRACTION: "general" → Specific contexts (narrowing focus)
       Example: "docker" in "general" → "docker" in "microservices"
    
    Note: Adding contexts without removing is NOT a shift (e.g., general + web).
    """
    
    def __init__(self, settings=None):
        """Initialize detector."""
        super().__init__(settings)
        
        logger.debug("ContextShiftDetector initialized")
    
    def detect(
        self,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> List[DriftSignal]:
        """
        Detect context shifts by comparing context patterns.
        
        Args:
            reference: Historical behavior snapshot
            current: Current behavior snapshot
            
        Returns:
            List of DriftSignal objects for detected context shifts
            
        Note:
            Only detects true shifts (context replacement), not additions.
            Adding new contexts while keeping old ones is not considered drift.
        """
        start_time = time.time()
        signals = []
        
        # Step 1: Build context maps for both snapshots
        ref_contexts = self._build_context_map(reference)
        cur_contexts = self._build_context_map(current)
        
        if not ref_contexts or not cur_contexts:
            logger.debug(
                "Empty context maps, no shifts to detect",
                extra={"user_id": current.user_id}
            )
            return signals
        
        # Step 2: Find common targets
        common_targets = set(ref_contexts.keys()) & set(cur_contexts.keys())
        
        if not common_targets:
            logger.debug(
                "No common targets between windows",
                extra={"user_id": current.user_id}
            )
            return signals
        
        logger.debug(
            f"Analyzing {len(common_targets)} common targets for context shifts",
            extra={"user_id": current.user_id, "common_target_count": len(common_targets)}
        )
        
        # Step 3: Check each target for context shifts
        for target in common_targets:
            ref_context_set = ref_contexts[target]
            cur_context_set = cur_contexts[target]
            
            # Detect expansion: specific → general
            if self._is_expansion(ref_context_set, cur_context_set):
                signal = self._create_context_signal(
                    target,
                    ref_context_set,
                    cur_context_set,
                    shift_type="EXPANSION"
                )
                signals.append(signal)
                logger.info(
                    f"Detected context EXPANSION: '{target}' "
                    f"{ref_context_set} → {cur_context_set}",
                    extra={
                        "user_id": current.user_id,
                        "target": target,
                        "shift_type": "EXPANSION",
                        "ref_contexts": list(ref_context_set),
                        "cur_contexts": list(cur_context_set)
                    }
                )
            
            # Detect contraction: general → specific
            elif self._is_contraction(ref_context_set, cur_context_set):
                signal = self._create_context_signal(
                    target,
                    ref_context_set,
                    cur_context_set,
                    shift_type="CONTRACTION"
                )
                signals.append(signal)
                logger.info(
                    f"Detected context CONTRACTION: '{target}' "
                    f"{ref_context_set} → {cur_context_set}",
                    extra={
                        "user_id": current.user_id,
                        "target": target,
                        "shift_type": "CONTRACTION",
                        "ref_contexts": list(ref_context_set),
                        "cur_contexts": list(cur_context_set)
                    }
                )
        
        elapsed = time.time() - start_time
        logger.info(
            f"ContextShiftDetector completed in {elapsed:.3f}s: {len(signals)} signal(s)",
            extra={
                "user_id": current.user_id,
                "execution_time_seconds": elapsed,
                "signals_found": len(signals),
                "common_targets_analyzed": len(common_targets)
            }
        )
        
        return signals
    
    def _build_context_map(self, snapshot: BehaviorSnapshot) -> Dict[str, Set[str]]:
        """
        Build a map of target → set of contexts.
        
        Args:
            snapshot: BehaviorSnapshot to extract contexts from
            
        Returns:
            Dictionary mapping target to set of contexts
        """
        context_map = defaultdict(set)
        
        for behavior in snapshot.get_active_behaviors():
            context_map[behavior.target].add(behavior.context)
        
        return dict(context_map)
    
    def _is_expansion(self, ref_contexts: Set[str], cur_contexts: Set[str]) -> bool:
        """
        Check if contexts represent an expansion (specific → general).
        
        Expansion occurs when:
        - Reference has specific contexts (no "general")
        - Current has "general" (with or without specifics)
        
        Args:
            ref_contexts: Context set from reference window
            cur_contexts: Context set from current window
            
        Returns:
            True if expansion detected
        """
        has_ref_general = "general" in ref_contexts
        has_cur_general = "general" in cur_contexts
        
        # Expansion: didn't have general before, has it now
        return not has_ref_general and has_cur_general
    
    def _is_contraction(self, ref_contexts: Set[str], cur_contexts: Set[str]) -> bool:
        """
        Check if contexts represent a contraction (general → specific).
        
        Contraction occurs when:
        - Reference has "general"
        - Current has only specific contexts (no "general")
        
        Args:
            ref_contexts: Context set from reference window
            cur_contexts: Context set from current window
            
        Returns:
            True if contraction detected
        """
        has_ref_general = "general" in ref_contexts
        has_cur_general = "general" in cur_contexts
        
        # Contraction: had general before, doesn't have it now
        return has_ref_general and not has_cur_general
    
    def _create_context_signal(
        self,
        target: str,
        ref_contexts: Set[str],
        cur_contexts: Set[str],
        shift_type: str
    ) -> DriftSignal:
        """
        Create a drift signal for a context shift.
        
        Args:
            target: Target that shifted contexts
            ref_contexts: Contexts in reference window
            cur_contexts: Contexts in current window
            shift_type: "EXPANSION" or "CONTRACTION"
            
        Returns:
            DriftSignal object
        """
        # Calculate context diversity change
        ref_diversity = len(ref_contexts)
        cur_diversity = len(cur_contexts)
        
        # Drift score based on magnitude of shift
        # Larger context change = higher score
        diversity_change = abs(cur_diversity - ref_diversity)
        drift_score = min(diversity_change / 5.0, 1.0)  # Normalize (assume 5+ is max)
        
        # Boost score for general ↔ specific shifts (more significant)
        if "general" in ref_contexts or "general" in cur_contexts:
            drift_score = min(drift_score * 1.5, 1.0)
        
        # Confidence based on number of contexts involved
        # More contexts = more data = higher confidence
        avg_contexts = (ref_diversity + cur_diversity) / 2
        confidence = min(avg_contexts / 3.0, 1.0)  # Normalize (assume 3+ is confident)
        
        # Determine the drift type based on shift_type
        if shift_type == "EXPANSION":
            drift_type = DriftType.CONTEXT_EXPANSION
        else:  # "CONTRACTION"
            drift_type = DriftType.CONTEXT_CONTRACTION
        
        # Create evidence dictionary
        evidence = {
            "target": target,
            "shift_type": shift_type,
            "reference_contexts": sorted(list(ref_contexts)),
            "current_contexts": sorted(list(cur_contexts)),
            "reference_context_count": ref_diversity,
            "current_context_count": cur_diversity,
            "contexts_added": sorted(list(cur_contexts - ref_contexts)),
            "contexts_removed": sorted(list(ref_contexts - cur_contexts)),
        }
        
        # Create and return signal
        return self._create_signal(
            drift_type=drift_type,
            drift_score=drift_score,
            affected_targets=[target],
            evidence=evidence,
            confidence=confidence
        )
