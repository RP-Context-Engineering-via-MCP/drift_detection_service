"""
TopicEmergenceDetector - Detects new topics appearing in user behavior.

Identifies drift when topics that were absent in the reference window
appear with significant activity in the current window, indicating new
interests or focus areas.
"""

import logging
import time
from datetime import datetime
from typing import List, Set

from app.detectors.base import BaseDetector
from app.detectors.utils import cluster_topics
from app.models.drift import DriftSignal, DriftType
from app.models.snapshot import BehaviorSnapshot
from app.utils.time import now_ms


logger = logging.getLogger(__name__)


class TopicEmergenceDetector(BaseDetector):
    """
    Detects topic emergence by identifying new topics with significant activity.
    
    A topic is considered emerging if:
    1. It appears in the current window but not in the reference window
    2. It has sufficient reinforcement (mentions/engagement)
    3. It represents genuine new interest (not just casual mention)
    
    The detector calculates drift scores based on:
    - Relative importance (reinforcement vs total activity)
    - Recency (more recent mentions = stronger signal)
    """
    
    def __init__(self, settings=None):
        """Initialize detector with emergence-specific configuration."""
        super().__init__(settings)
        self.min_reinforcement = self.settings.emergence_min_reinforcement
        self.recency_weight_days = self.settings.recency_weight_days
        
        logger.debug(
            f"TopicEmergenceDetector initialized: "
            f"min_reinforcement={self.min_reinforcement}, "
            f"recency_weight_days={self.recency_weight_days}"
        )
    
    def detect(
        self,
        reference: BehaviorSnapshot,
        current: BehaviorSnapshot
    ) -> List[DriftSignal]:
        """
        Detect topic emergence by comparing reference and current snapshots.
        
        Args:
            reference: Historical behavior snapshot
            current: Current behavior snapshot
            
        Returns:
            List of DriftSignal objects for emerging topics
            
        Note:
            Emerging topics must have minimum reinforcement to avoid
            false positives from casual mentions.
        """
        start_time = time.time()
        signals = []
        
        # Step 1: Find new topics (present in current but not in reference)
        reference_targets = reference.get_targets()
        current_targets = current.get_targets()
        new_targets = current_targets - reference_targets
        
        if not new_targets:
            logger.debug(
                "No new topics detected in current window",
                extra={"user_id": current.user_id}
            )
            return signals
        
        logger.debug(
            f"Found {len(new_targets)} potential new topics",
            extra={"user_id": current.user_id, "new_target_count": len(new_targets)}
        )
        
        # Step 2: Filter by reinforcement threshold
        emerging_topics = []
        for target in new_targets:
            reinforcement = current.get_reinforcement_count(target)
            
            if reinforcement >= self.min_reinforcement:
                emerging_topics.append(target)
                logger.debug(
                    f"Topic '{target}' qualifies: "
                    f"reinforcement={reinforcement} >= {self.min_reinforcement}"
                )
            else:
                logger.debug(
                    f"Topic '{target}' filtered out: "
                    f"reinforcement={reinforcement} < {self.min_reinforcement}"
                )
        
        if not emerging_topics:
            logger.debug("No topics meet reinforcement threshold")
            return signals
        
        # Step 3: Apply semantic clustering to detect domain emergence
        emerging_topics_set = set(emerging_topics)
        clusters = cluster_topics(emerging_topics_set)
        
        # Track which topics are in clusters (for domain emergence)
        clustered_topics = set()
        for cluster in clusters:
            clustered_topics.update(cluster)
        
        # Create signals for domain emergence (clusters)
        if clusters:
            logger.info(
                f"Detected {len(clusters)} semantic cluster(s) indicating domain emergence",
                extra={
                    "user_id": current.user_id,
                    "cluster_count": len(clusters),
                    "clusters": [list(c) for c in clusters]
                }
            )
            
            for cluster in clusters:
                signal = self._create_domain_emergence_signal(cluster, current)
                signals.append(signal)
                
                logger.info(
                    f"Detected domain emergence: {list(cluster)} "
                    f"(score={signal.drift_score:.3f})",
                    extra={
                        "user_id": current.user_id,
                        "emerging_domain": list(cluster),
                        "drift_score": signal.drift_score,
                        "cluster_size": len(cluster)
                    }
                )
        
        # Step 4: Calculate drift scores for individual emerging topics (not in clusters)
        unclustered_topics = emerging_topics_set - clustered_topics
        for target in unclustered_topics:
            signal = self._create_emergence_signal(target, current)
            signals.append(signal)
            
            logger.info(
                f"Detected topic emergence: '{target}' "
                f"(score={signal.drift_score:.3f}, "
                f"reinforcement={current.get_reinforcement_count(target)})",
                extra={
                    "user_id": current.user_id,
                    "emerging_target": target,
                    "drift_score": signal.drift_score,
                    "reinforcement_count": current.get_reinforcement_count(target)
                }
            )
        
        elapsed = time.time() - start_time
        logger.info(
            f"TopicEmergenceDetector completed in {elapsed:.3f}s: {len(signals)} signal(s)",
            extra={
                "user_id": current.user_id,
                "execution_time_seconds": elapsed,
                "signals_found": len(signals),
                "new_targets_analyzed": len(new_targets),
                "emerging_targets": len(emerging_topics) if 'emerging_topics' in locals() else 0
            }
        )
        
        return signals
    
    def _create_emergence_signal(
        self,
        target: str,
        current: BehaviorSnapshot
    ) -> DriftSignal:
        """
        Create a drift signal for an emerging topic.
        
        Args:
            target: Emerging target/topic
            current: Current behavior snapshot
            
        Returns:
            DriftSignal object
        """
        # Get behaviors for this target
        behaviors = current.get_behaviors_by_target(target)
        reinforcement = sum(b.reinforcement_count for b in behaviors)
        
        # Calculate average credibility for this target
        avg_credibility = sum(b.credibility for b in behaviors) / len(behaviors)
        
        # Calculate recency weight: more recent = stronger signal
        # Use milliseconds to match database timestamp format
        now_ts = now_ms()
        avg_days_ago = sum(
            (now_ts - b.last_seen_at) / (86400 * 1000) for b in behaviors
        ) / len(behaviors)
        
        # Recency weight: decays linearly over recency_weight_days
        # 0 days ago = 1.0, recency_weight_days ago = 0.1
        recency_weight = max(0.1, 1.0 - (avg_days_ago / self.recency_weight_days))
        
        # Calculate reinforcement weight: 4+ reinforcements = max score
        # This rewards topics with stronger engagement
        reinforcement_weight = min(reinforcement / 4.0, 1.0)
        
        # Final drift score combines reinforcement strength, credibility, and recency
        # This approach avoids the "dilution" problem where many emerging topics
        # each get tiny scores when using relative importance
        drift_score = reinforcement_weight * avg_credibility * recency_weight
        
        # Confidence based on reinforcement strength
        # More reinforcement = more confident it's a real trend
        confidence = min(reinforcement / 5.0, 1.0)  # Normalize (5+ is high confidence)
        
        # Create evidence dictionary
        evidence = {
            "emerging_target": target,
            "reinforcement_count": reinforcement,
            "behavior_count": len(behaviors),
            "avg_credibility": round(avg_credibility, 3),
            "avg_days_since_mention": round(avg_days_ago, 1),
            "recency_weight": round(recency_weight, 3),
            "reinforcement_weight": round(reinforcement_weight, 3),
            "contexts": sorted(list(current.get_contexts_for_target(target))),
        }
        
        # Create and return signal
        return self._create_signal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=drift_score,
            affected_targets=[target],
            evidence=evidence,
            confidence=confidence
        )
    
    def _create_domain_emergence_signal(
        self,
        cluster: Set[str],
        current: BehaviorSnapshot
    ) -> DriftSignal:
        """
        Create a drift signal for an emerging domain (cluster of related topics).
        
        Args:
            cluster: Set of semantically related emerging topics
            current: Current behavior snapshot
            
        Returns:
            DriftSignal object with is_domain_emergence flag
        """
        cluster_list = list(cluster)
        
        # Aggregate metrics across all topics in the cluster
        total_reinforcement = 0
        total_behaviors = 0
        credibility_sum = 0
        all_contexts = set()
        days_ago_sum = 0
        
        now_ts = now_ms()
        
        for target in cluster:
            behaviors = current.get_behaviors_by_target(target)
            total_behaviors += len(behaviors)
            total_reinforcement += sum(b.reinforcement_count for b in behaviors)
            credibility_sum += sum(b.credibility for b in behaviors)
            all_contexts.update(current.get_contexts_for_target(target))
            
            # Calculate average days ago for this target
            if behaviors:
                target_days_ago = sum(
                    (now_ts - b.last_seen_at) / (86400 * 1000) for b in behaviors
                ) / len(behaviors)
                days_ago_sum += target_days_ago
        
        # Calculate cluster-level metrics
        avg_credibility = credibility_sum / total_behaviors if total_behaviors > 0 else 0.5
        avg_days_ago = days_ago_sum / len(cluster)
        
        # Recency weight
        recency_weight = max(0.1, 1.0 - (avg_days_ago / self.recency_weight_days))
        
        # Reinforcement weight (domain emergence should have stronger signal)
        reinforcement_weight = min(total_reinforcement / (len(cluster) * 3.0), 1.0)
        
        # Cluster size bonus: larger clusters = stronger domain signal
        cluster_bonus = min(1.0 + (len(cluster) - 2) * 0.1, 1.3)
        
        # Domain emergence gets boosted score (stronger signal than individual topics)
        drift_score = reinforcement_weight * avg_credibility * recency_weight * cluster_bonus
        
        # Higher confidence for domain emergence (semantic coherence)
        confidence = min(0.7 + (len(cluster) * 0.1), 0.95)
        
        # Create evidence dictionary
        evidence = {
            "is_domain_emergence": True,
            "emerging_topics": sorted(cluster_list),
            "cluster_size": len(cluster),
            "total_reinforcement_count": total_reinforcement,
            "total_behavior_count": total_behaviors,
            "avg_credibility": round(avg_credibility, 3),
            "avg_days_since_mention": round(avg_days_ago, 1),
            "recency_weight": round(recency_weight, 3),
            "reinforcement_weight": round(reinforcement_weight, 3),
            "cluster_bonus": round(cluster_bonus, 3),
            "contexts": sorted(list(all_contexts)),
        }
        
        # Create and return signal
        return self._create_signal(
            drift_type=DriftType.TOPIC_EMERGENCE,
            drift_score=drift_score,
            affected_targets=cluster_list,
            evidence=evidence,
            confidence=confidence
        )
