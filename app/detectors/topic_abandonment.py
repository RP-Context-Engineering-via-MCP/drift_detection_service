"""
TopicAbandonmentDetector - Detects when previously active topics go silent.

Identifies drift by comparing topic activity in reference window vs current window.
Topics that had significant historical reinforcement but are now absent trigger
abandonment signals.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Tuple

from app.detectors.base import BaseDetector
from app.models.drift import DriftSignal, DriftType
from app.models.snapshot import BehaviorSnapshot


logger = logging.getLogger(__name__)


class TopicAbandonmentDetector(BaseDetector):
    """
    Detects topic abandonment by identifying previously active topics
    that have gone silent in the current window.
    
    A topic is considered abandoned if:
    1. It had significant reinforcement in the reference window
    2. It is absent or silent in the current window
    3. The silence period exceeds the configured threshold
    """
    
    def __init__(self, settings=None):
        """Initialize detector with abandonment-specific configuration."""
        super().__init__(settings)
        self.silence_threshold = self.settings.abandonment_silence_days
        self.min_reinforcement = self.settings.min_reinforcement_for_abandonment
        
        logger.debug(
            f"TopicAbandonmentDetector initialized: "
            f"silence_threshold={self.silence_threshold}d, "
            f"min_reinforcement={self.min_reinforcement}"
        )
    
    def detect(
        self,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> List[DriftSignal]:
        """
        Detect topic abandonment by comparing reference and current snapshots.
        
        Args:
            reference: Historical behavior snapshot
            current: Current behavior snapshot
            
        Returns:
            List of DriftSignal objects for abandoned topics
            
        Raises:
            ValueError: If snapshots are invalid or from different users
        """
        start_time = time.time()
        signals = []
        
        # Validate inputs
        try:
            self._validate_snapshots(reference, current)
        except (ValueError, TypeError) as e:
            logger.error(f"Snapshot validation failed: {e}")
            return signals
        
        # Step 1: Get topics from reference with sufficient activity
        active_topics = self._get_active_topics_from_reference(reference)
        
        if not active_topics:
            logger.debug(
                "No sufficiently reinforced topics in reference window",
                extra={"user_id": current.user_id}
            )
            return signals
        
        logger.debug(
            f"Found {len(active_topics)} active topics in reference window",
            extra={"user_id": current.user_id, "active_topic_count": len(active_topics)}
        )
        
        # Step 2: Check which topics are abandoned in current window
        now_ts = int(datetime.now().timestamp())
        silence_threshold_ts = now_ts - (self.silence_threshold * 86400)
        
        for target, data in active_topics.items():
            # Check if target is still active in current snapshot
            if current.has_target(target):
                logger.debug(f"Target '{target}' still active in current window")
                continue
            
            # Check if last_seen_at is beyond silence threshold
            if data["last_seen_at"] >= silence_threshold_ts:
                logger.debug(
                    f"Target '{target}' silent but not beyond threshold "
                    f"(last_seen={data['last_seen_at']})"
                )
                continue
            
            # Topic is abandoned - create signal
            signal = self._create_abandonment_signal(
                target, data, now_ts, silence_threshold_ts
            )
            signals.append(signal)
            
            days_silent = (now_ts - data["last_seen_at"]) / 86400
            logger.info(
                f"Detected topic abandonment: '{target}' "
                f"(silent for {days_silent:.1f} days, "
                f"historical reinforcement={data['reinforcement_count']})",
                extra={
                    "user_id": current.user_id,
                    "abandoned_target": target,
                    "days_silent": days_silent,
                    "historical_reinforcement": data["reinforcement_count"],
                    "drift_score": signal.drift_score
                }
            )
        
        elapsed = time.time() - start_time
        logger.info(
            f"TopicAbandonmentDetector completed in {elapsed:.3f}s: {len(signals)} signal(s)",
            extra={
                "user_id": current.user_id,
                "execution_time_seconds": elapsed,
                "signals_found": len(signals),
                "active_topics_analyzed": len(active_topics)
            }
        )
        
        return signals
        
        return signals
    
    def _get_active_topics_from_reference(
        self,
        reference: BehaviorSnapshot
    ) -> Dict[str, Dict]:
        """
        Extract topics with sufficient activity from reference snapshot.
        
        Args:
            reference: Historical behavior snapshot
            
        Returns:
            Dictionary mapping target to activity data
            Format: {target: {"reinforcement_count": int, "last_seen_at": int}}
        """
        reference_topics = {}
        
        # Use _get_relevant_behaviors() to include superseded behaviors
        # in reference/historical windows
        for behavior in reference._get_relevant_behaviors():
            if behavior.target not in reference_topics:
                reference_topics[behavior.target] = {
                    "reinforcement_count": 0,
                    "last_seen_at": 0,
                }
            
            # Accumulate reinforcement count
            reference_topics[behavior.target]["reinforcement_count"] += (
                behavior.reinforcement_count
            )
            
            # Track most recent activity
            reference_topics[behavior.target]["last_seen_at"] = max(
                reference_topics[behavior.target]["last_seen_at"],
                behavior.last_seen_at
            )
        
        # Filter to topics with sufficient reinforcement
        active_topics = {
            target: data
            for target, data in reference_topics.items()
            if data["reinforcement_count"] >= self.min_reinforcement
        }
        
        return active_topics
    
    def _create_abandonment_signal(
        self,
        target: str,
        data: Dict,
        now_ts: int,
        silence_threshold_ts: int
    ) -> DriftSignal:
        """
        Create a drift signal for an abandoned topic.
        
        Args:
            target: Target that was abandoned
            data: Activity data from reference window
            now_ts: Current timestamp
            silence_threshold_ts: Threshold timestamp for silence
            
        Returns:
            DriftSignal object
        """
        # Calculate silence duration
        days_silent = (now_ts - data["last_seen_at"]) / 86400
        
        # Historical weight: higher reinforcement = stronger signal
        # Cap at 1.0 (normalize by assuming 5+ reinforcements is "strong")
        historical_weight = min(data["reinforcement_count"] / 5.0, 1.0)
        
        # Silence weight: longer silence = stronger signal
        # Normalize by dividing by threshold (1.0 = exactly at threshold)
        silence_weight = min(days_silent / self.silence_threshold, 1.0)
        
        # Drift score is product of both factors
        drift_score = historical_weight * silence_weight
        
        # Confidence is based on historical strength
        # (more reinforcement = more confident it's a real abandonment)
        confidence = historical_weight
        
        # Create evidence dictionary
        evidence = {
            "abandoned_target": target,
            "last_seen_at": data["last_seen_at"],
            "days_silent": int(days_silent),
            "historical_reinforcement_count": data["reinforcement_count"],
            "silence_threshold_days": self.silence_threshold,
            "historical_weight": round(historical_weight, 3),
            "silence_weight": round(silence_weight, 3),
        }
        
        # Create and return signal
        return self._create_signal(
            drift_type=DriftType.TOPIC_ABANDONMENT,
            drift_score=drift_score,
            affected_targets=[target],
            evidence=evidence,
            confidence=confidence
        )
