"""Core drift detection service implementing temporal decay and accumulation logic."""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.config import get_settings
from app.core.constants import DriftType
from app.core.logging_config import get_logger
from app.models.behavior import Behavior
from app.utils.datetime_helpers import days_between, now_utc

logger = get_logger(__name__)


@dataclass
class DriftAnalysis:
    """Results of drift analysis for a behavior."""

    effective_credibility: float
    days_inactive: int
    decay_factor: float
    drift_detected: bool
    drift_signal_count: int
    drift_type: Optional[DriftType] = None
    reason: str = ""


class DriftDetector:
    """
    Implements temporal decay and drift accumulation detection.
    
    This service calculates time-adjusted credibility scores and detects
    persistent patterns of behavior change attempts.
    """

    def __init__(self):
        """Initialize drift detector with configuration."""
        self.settings = get_settings()
        self.decay_half_life_days = self.settings.decay_half_life_days
        self.drift_threshold = self.settings.drift_signal_threshold

    def calculate_effective_credibility(
        self, stored_credibility: float, last_seen_at: datetime
    ) -> tuple[float, float, int]:
        """
        Calculate time-decayed effective credibility.
        
        Uses exponential decay formula: N(t) = N0 * (0.5)^(t/half_life)
        
        Args:
            stored_credibility: Original credibility score (0.0-1.0)
            last_seen_at: When the behavior was last reinforced
        
        Returns:
            Tuple of (effective_credibility, decay_factor, days_inactive)
        """
        current_time = now_utc()
        days_passed = days_between(last_seen_at, current_time)

        # Exponential decay: half-life formula
        decay_factor = math.pow(0.5, days_passed / self.decay_half_life_days)
        effective_credibility = stored_credibility * decay_factor

        logger.debug(
            f"Credibility decay: {stored_credibility:.3f} -> {effective_credibility:.3f} "
            f"(days: {days_passed}, factor: {decay_factor:.3f})"
        )

        return effective_credibility, decay_factor, days_passed

    def analyze_behavior_drift(
        self,
        existing_behavior: Behavior,
        drift_signal_count: int,
    ) -> DriftAnalysis:
        """
        Analyze a behavior for temporal drift.
        
        Args:
            existing_behavior: The current behavior record
            drift_signal_count: Number of recent drift signals for this behavior
        
        Returns:
            DriftAnalysis with decay and accumulation results
        """
        # Calculate temporal decay
        effective_cred, decay_factor, days_inactive = (
            self.calculate_effective_credibility(
                existing_behavior.credibility, existing_behavior.last_seen_at
            )
        )

        # Check for drift accumulation
        drift_detected = drift_signal_count >= self.drift_threshold

        # Determine reason
        if drift_detected:
            reason = (
                f"User persistence detected: {drift_signal_count} attempts "
                f"in last {self.settings.drift_signal_window_days} days exceeds "
                f"threshold of {self.drift_threshold}"
            )
        elif days_inactive > self.decay_half_life_days:
            reason = (
                f"Behavior is stale: last seen {days_inactive} days ago, "
                f"credibility decayed from {existing_behavior.credibility:.2f} "
                f"to {effective_cred:.2f}"
            )
        else:
            reason = "Behavior is still fresh and credible"

        return DriftAnalysis(
            effective_credibility=effective_cred,
            days_inactive=days_inactive,
            decay_factor=decay_factor,
            drift_detected=drift_detected,
            drift_signal_count=drift_signal_count,
            reason=reason,
        )

    def classify_drift_type(
        self,
        existing_behavior: Behavior,
        new_intent: str,
        new_target: str,
        new_polarity: str,
        new_context: str,
    ) -> DriftType:
        """
        Classify the type of drift occurring.
        
        Args:
            existing_behavior: Current behavior
            new_intent: Intent of new behavior
            new_target: Target of new behavior
            new_polarity: Polarity of new behavior
            new_context: Context of new behavior
        
        Returns:
            DriftType classification
        """
        # Same target, opposite polarity = POLARITY_SHIFT
        # e.g., "I love Python" -> "I hate Python"
        if (
            existing_behavior.target.lower() == new_target.lower()
            and existing_behavior.intent == new_intent
            and existing_behavior.polarity != new_polarity
        ):
            return DriftType.POLARITY_SHIFT

        # Same intent + context, different target = TARGET_SHIFT
        # e.g., "Prefer Python for backend" -> "Prefer Go for backend"
        if (
            existing_behavior.intent == new_intent
            and existing_behavior.context == new_context
            and existing_behavior.target.lower() != new_target.lower()
        ):
            return DriftType.TARGET_SHIFT

        # Otherwise, it's likely a refinement
        return DriftType.REFINEMENT

    def should_force_supersede(
        self, drift_analysis: DriftAnalysis, new_credibility: float
    ) -> bool:
        """
        Determine if drift signals should force a supersede despite lower credibility.
        
        This is the "persistent nag" logic: if a user keeps trying to change
        a behavior, eventually we should respect that intent even if the
        individual signals are weak.
        
        Args:
            drift_analysis: Results of drift analysis
            new_credibility: Credibility of the new behavior
        
        Returns:
            True if accumulation forces a supersede
        """
        if not drift_analysis.drift_detected:
            return False

        # Even if new credibility is lower, the persistence indicates
        # a genuine shift in user preference
        logger.info(
            f"Forcing supersede due to drift accumulation: "
            f"{drift_analysis.drift_signal_count} signals detected"
        )
        return True
