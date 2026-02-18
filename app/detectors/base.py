"""
BaseDetector - Abstract base class for all drift detectors.

All detector implementations extend this class and implement the detect() method.
"""

import logging
from abc import ABC, abstractmethod
from typing import List

from app.config import Settings, get_settings
from app.models.drift import DriftSignal, DriftType
from app.models.snapshot import BehaviorSnapshot


logger = logging.getLogger(__name__)


class BaseDetector(ABC):
    """
    Abstract base class for drift detectors.
    
    Each detector analyzes a reference and current BehaviorSnapshot,
    identifies drift signals, and returns a list of DriftSignal objects.
    """
    
    def __init__(self, settings: Settings = None):
        """
        Initialize detector with configuration.
        
        Args:
            settings: Configuration settings (default: get_settings())
        """
        self.settings = settings or get_settings()
        self.drift_score_threshold = self.settings.drift_score_threshold
        
    @abstractmethod
    def detect(
        self,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> List[DriftSignal]:
        """
        Detect drift signals by comparing reference and current snapshots.
        
        Args:
            reference: Historical behavior snapshot (older time window)
            current: Current behavior snapshot (recent time window)
            
        Returns:
            List of DriftSignal objects, empty list if no drift detected
            
        Raises:
            ValueError: If snapshots are invalid or from different users
        """
        pass
    
    def _validate_snapshots(
        self,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> None:
        """
        Validate that snapshots are suitable for comparison.
        
        Args:
            reference: Reference snapshot
            current: Current snapshot
            
        Raises:
            ValueError: If snapshots are invalid
            TypeError: If arguments are not BehaviorSnapshot objects
        """
        # Type validation
        if not isinstance(reference, BehaviorSnapshot):
            raise TypeError(
                f"reference must be BehaviorSnapshot, got {type(reference).__name__}"
            )
        if not isinstance(current, BehaviorSnapshot):
            raise TypeError(
                f"current must be BehaviorSnapshot, got {type(current).__name__}"
            )
        
        # User ID validation
        if reference.user_id != current.user_id:
            raise ValueError(
                f"Snapshot user_id mismatch: reference={reference.user_id}, "
                f"current={current.user_id}"
            )
        
        # Time window validation
        if reference.window_start >= current.window_end:
            logger.warning(
                f"Reference window ({reference.window_start}) overlaps or is after "
                f"current window ({current.window_end})"
            )
    
    def _calculate_score(self, metric: float, threshold: float) -> float:
        """
        Normalize a metric value to a 0-1 score.
        
        Args:
            metric: Raw metric value
            threshold: Threshold for normalization
            
        Returns:
            Normalized score between 0 and 1
        """
        if threshold <= 0:
            return 0.0
        
        score = min(metric / threshold, 1.0)
        return max(score, 0.0)
    
    def _is_above_threshold(self, score: float) -> bool:
        """
        Check if a drift score exceeds the configured threshold.
        
        Args:
            score: Drift score to check
            
        Returns:
            True if score >= threshold, False otherwise
        """
        return score >= self.drift_score_threshold
    
    def _create_signal(
        self,
        drift_type: DriftType,
        drift_score: float,
        affected_targets: List[str],
        evidence: dict,
        confidence: float
    ) -> DriftSignal:
        """
        Create a DriftSignal object with standardized fields.
        
        Args:
            drift_type: Type of drift detected
            drift_score: Drift strength score (0-1)
            affected_targets: List of affected behavior targets
            evidence: Supporting evidence (metadata)
            confidence: Confidence level (0-1)
            
        Returns:
            DriftSignal object
        """
        signal = DriftSignal(
            drift_type=drift_type,
            drift_score=drift_score,
            affected_targets=affected_targets,
            evidence=evidence,
            confidence=confidence
        )
        
        logger.debug(
            f"Created signal: {drift_type} | score={drift_score:.3f} | "
            f"confidence={confidence:.3f} | targets={affected_targets}"
        )
        
        return signal
