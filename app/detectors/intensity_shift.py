"""
IntensityShiftDetector - Detects changes in behavior credibility/conviction.

Identifies drift by comparing average credibility for the same target across
reference and current windows. Significant increases or decreases in credibility
indicate a shift in conviction strength.
"""

import logging
import time
from typing import List

from app.detectors.base import BaseDetector
from app.models.drift import DriftSignal, DriftType
from app.models.snapshot import BehaviorSnapshot


logger = logging.getLogger(__name__)


class IntensityShiftDetector(BaseDetector):
    """
    Detects intensity shifts by comparing behavior credibility scores.
    
    An intensity shift occurs when:
    1. A target appears in both reference and current windows
    2. The average credibility changes significantly
    3. The change (delta) exceeds the configured threshold
    
    Direction can be INCREASE (stronger conviction) or DECREASE (weaker conviction).
    """
    
    def __init__(self, settings=None):
        """Initialize detector with intensity-specific configuration."""
        super().__init__(settings)
        self.delta_threshold = self.settings.intensity_delta_threshold
        
        logger.debug(
            f"IntensityShiftDetector initialized: "
            f"delta_threshold={self.delta_threshold}"
        )
    
    def detect(
        self,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> List[DriftSignal]:
        """
        Detect intensity shifts by comparing credibility across windows.
        
        Args:
            reference: Historical behavior snapshot
            current: Current behavior snapshot
            
        Returns:
            List of DriftSignal objects for detected intensity shifts
            
        Note:
            Both increases and decreases in credibility are detected.
            The direction is captured in the evidence field.
        """
        start_time = time.time()
        signals = []
        
        # Step 1: Find common targets (in both windows)
        reference_targets = reference.get_targets()
        current_targets = current.get_targets()
        common_targets = reference_targets & current_targets
        
        if not common_targets:
            logger.debug(
                "No common targets between reference and current windows",
                extra={"user_id": current.user_id}
            )
            return signals
        
        logger.debug(
            f"Analyzing {len(common_targets)} common targets for intensity shifts",
            extra={"user_id": current.user_id, "common_target_count": len(common_targets)}
        )
        
        # Step 2: For each common target, calculate credibility delta
        for target in common_targets:
            ref_cred = reference.get_average_credibility(target)
            cur_cred = current.get_average_credibility(target)
            
            # Calculate absolute change
            delta = abs(cur_cred - ref_cred)
            
            # Check if delta exceeds threshold
            if delta < self.delta_threshold:
                logger.debug(
                    f"Target '{target}': delta={delta:.3f} below threshold "
                    f"{self.delta_threshold}"
                )
                continue
            
            # Determine direction
            direction = "INCREASE" if cur_cred > ref_cred else "DECREASE"
            
            # Create signal
            signal = self._create_intensity_signal(
                target, ref_cred, cur_cred, delta, direction
            )
            signals.append(signal)
            
            logger.info(
                f"Detected intensity shift: '{target}' credibility "
                f"{direction} ({ref_cred:.3f} → {cur_cred:.3f}, delta={delta:.3f})",
                extra={
                    "user_id": current.user_id,
                    "target": target,
                    "direction": direction,
                    "ref_credibility": ref_cred,
                    "cur_credibility": cur_cred,
                    "delta": delta,
                    "drift_score": signal.drift_score
                }
            )
        
        elapsed = time.time() - start_time
        logger.info(
            f"IntensityShiftDetector completed in {elapsed:.3f}s: {len(signals)} signal(s)",
            extra={
                "user_id": current.user_id,
                "execution_time_seconds": elapsed,
                "signals_found": len(signals),
                "common_targets_analyzed": len(common_targets)
            }
        )
        
        return signals
    
    def _create_intensity_signal(
        self,
        target: str,
        ref_credibility: float,
        cur_credibility: float,
        delta: float,
        direction: str
    ) -> DriftSignal:
        """
        Create a drift signal for an intensity shift.
        
        Args:
            target: Target that shifted intensity
            ref_credibility: Average credibility in reference window
            cur_credibility: Average credibility in current window
            delta: Absolute change in credibility
            direction: "INCREASE" or "DECREASE"
            
        Returns:
            DriftSignal object
        """
        # Drift score is the delta itself (already 0-1 scale)
        drift_score = delta
        
        # Confidence is based on the lower of the two credibilities
        # If both credibilities are high, we're more confident in the shift
        confidence = min(ref_credibility, cur_credibility)
        
        # Create evidence dictionary
        evidence = {
            "target": target,
            "direction": direction,
            "reference_credibility": round(ref_credibility, 3),
            "current_credibility": round(cur_credibility, 3),
            "credibility_delta": round(delta, 3),
            "relative_change_pct": round(
                ((cur_credibility - ref_credibility) / ref_credibility * 100)
                if ref_credibility > 0 else 0,
                1
            ),
        }
        
        # Create and return signal
        return self._create_signal(
            drift_type=DriftType.INTENSITY_SHIFT,
            drift_score=drift_score,
            affected_targets=[target],
            evidence=evidence,
            confidence=confidence
        )
