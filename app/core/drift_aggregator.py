"""Aggregates and deduplicates drift signals."""

import logging
from collections import defaultdict
from typing import List

from app.config import get_settings
from app.models.drift import DriftSignal

logger = logging.getLogger(__name__)


class DriftAggregator:
    """Deduplicates and filters drift signals."""

    def __init__(self):
        """Initialize aggregator with settings."""
        self.settings = get_settings()
        logger.info("DriftAggregator initialized")

    def aggregate(self, signals: List[DriftSignal]) -> List[DriftSignal]:
        """
        Deduplicate and filter signals.

        Strategy:
        1. Group signals by affected targets
        2. Keep only the highest-scoring signal per target
        3. Filter out signals below threshold
        4. Sort by drift_score descending

        Args:
            signals: Raw signals from all detectors

        Returns:
            Deduplicated and filtered signals, sorted by score
            
        Raises:
            TypeError: If signals is not a list or contains invalid elements
        """
        # Validate input
        if not isinstance(signals, list):
            raise TypeError(f"signals must be a list, got {type(signals).__name__}")
        
        if not signals:
            logger.info("No signals to aggregate")
            return []
        
        # Validate all signals are DriftSignal objects
        invalid_signals = [s for s in signals if not isinstance(s, DriftSignal)]
        if invalid_signals:
            logger.error(
                f"Found {len(invalid_signals)} invalid signal objects",
                extra={"invalid_count": len(invalid_signals)}
            )
            # Filter out invalid signals and continue
            signals = [s for s in signals if isinstance(s, DriftSignal)]
            if not signals:
                logger.warning("No valid signals after filtering")
                return []

        logger.info(
            f"Aggregating {len(signals)} raw signals",
            extra={"raw_signal_count": len(signals)}
        )

        try:
            # Step 1: Group by affected targets
            target_groups = defaultdict(list)
            for signal in signals:
                # Handle edge case: signal with no affected targets
                if not signal.affected_targets:
                    logger.warning(
                        f"Signal {signal.drift_type.value} has no affected targets, skipping"
                    )
                    continue
                
                for target in signal.affected_targets:
                    target_groups[target].append(signal)

            if not target_groups:
                logger.warning("No valid target groups after grouping")
                return []

            logger.debug(
                f"Grouped into {len(target_groups)} target groups",
                extra={"target_group_count": len(target_groups)}
            )

            # Step 2: Deduplicate - keep highest score per target
            deduplicated = []
            processed_signals = set()

            for target, target_signals in target_groups.items():
                # Sort by drift_score descending
                try:
                    target_signals.sort(key=lambda s: s.drift_score, reverse=True)
                except Exception as e:
                    logger.error(
                        f"Error sorting signals for target '{target}': {e}",
                        exc_info=True
                    )
                    continue
                
                best_signal = target_signals[0]

                # Avoid adding the same signal object twice
                signal_id = id(best_signal)
                if signal_id not in processed_signals:
                    deduplicated.append(best_signal)
                    processed_signals.add(signal_id)
                    logger.debug(
                        f"Target '{target}': kept signal with score {best_signal.drift_score:.3f}",
                        extra={"target": target, "drift_score": best_signal.drift_score}
                    )

            logger.info(
                f"After deduplication: {len(deduplicated)} signals",
                extra={"deduplicated_count": len(deduplicated)}
            )

            # Step 3: Filter by threshold
            threshold = self.settings.drift_score_threshold
            actionable = [
                s for s in deduplicated 
                if s.drift_score >= threshold and s.is_actionable
            ]

            logger.info(
                f"After threshold filter ({threshold}): {len(actionable)} actionable signals",
                extra={
                    "threshold": threshold,
                    "actionable_count": len(actionable),
                    "filtered_out": len(deduplicated) - len(actionable)
                }
            )

            # Step 4: Sort by score
            actionable.sort(key=lambda s: s.drift_score, reverse=True)

            return actionable
            
        except Exception as e:
            logger.error(
                f"Unexpected error during signal aggregation: {e}",
                exc_info=True
            )
            # Return empty list rather than crashing
            return []
