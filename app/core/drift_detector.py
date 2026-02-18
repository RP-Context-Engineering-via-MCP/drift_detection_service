"""Main drift detection orchestrator."""

import logging
from datetime import datetime, timezone
from typing import List

from app.config import get_settings
from app.core.drift_aggregator import DriftAggregator
from app.core.snapshot_builder import SnapshotBuilder
from app.db.connection import get_sync_connection_simple
from app.db.repositories.drift_event_repo import DriftEventRepository
from app.detectors.context_shift import ContextShiftDetector
from app.detectors.intensity_shift import IntensityShiftDetector
from app.detectors.preference_reversal import PreferenceReversalDetector
from app.detectors.topic_abandonment import TopicAbandonmentDetector
from app.detectors.topic_emergence import TopicEmergenceDetector
from app.models.drift import DriftEvent

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Main orchestrator for drift detection pipeline.

    Coordinates snapshot building, detector execution, signal aggregation,
    and event persistence.
    """

    def __init__(self):
        """Initialize orchestrator with all components."""
        self.snapshot_builder = SnapshotBuilder()
        self.aggregator = DriftAggregator()
        self.connection = get_sync_connection_simple()
        self.drift_event_repo = DriftEventRepository(self.connection)
        self.settings = get_settings()

        # Initialize all detectors
        self.detectors = [
            TopicEmergenceDetector(),
            TopicAbandonmentDetector(),
            PreferenceReversalDetector(),
            IntensityShiftDetector(),
            ContextShiftDetector(),
        ]

        logger.info(
            f"DriftDetector initialized with {len(self.detectors)} detectors"
        )

    def detect_drift(self, user_id: str) -> List[DriftEvent]:
        """
        Run full drift detection pipeline for a user.

        Pipeline:
        1. Pre-flight checks (sufficient data, cooldown period)
        2. Build reference and current snapshots
        3. Run all detectors
        4. Aggregate and deduplicate signals
        5. Convert to events
        6. Persist to database

        Args:
            user_id: User identifier

        Returns:
            List of detected DriftEvents (empty if no drift or checks fail)
            
        Raises:
            ValueError: If user_id is invalid
        """
        # Validate input
        if not user_id or not user_id.strip():
            logger.error("Invalid user_id: cannot be empty")
            raise ValueError("user_id cannot be empty")
        
        user_id = user_id.strip()
        logger.info(
            f"Starting drift detection for user: {user_id}",
            extra={"user_id": user_id}
        )

        # Step 1: Pre-flight checks
        if not self._preflight_checks(user_id):
            return []

        # Step 2: Build snapshots
        try:
            reference, current = self.snapshot_builder.build_reference_and_current(
                user_id
            )
            logger.info(
                f"Snapshots built successfully",
                extra={
                    "user_id": user_id,
                    "reference_behaviors": len(reference.behaviors),
                    "current_behaviors": len(current.behaviors)
                }
            )
        except ValueError as e:
            logger.error(f"Invalid snapshot parameters for {user_id}: {e}")
            return []
        except RuntimeError as e:
            logger.error(f"Failed to build snapshots for {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error building snapshots for {user_id}: {e}",
                exc_info=True
            )
            return []

        # Step 3: Run all detectors
        all_signals = []
        for detector in self.detectors:
            detector_name = detector.__class__.__name__
            try:
                signals = detector.detect(reference, current)
                all_signals.extend(signals)
                logger.info(
                    f"{detector_name} found {len(signals)} signal(s)"
                )
            except Exception as e:
                logger.error(f"{detector_name} failed: {e}", exc_info=True)
                # Continue with other detectors

        logger.info(f"Total raw signals from all detectors: {len(all_signals)}")

        if not all_signals:
            logger.info(f"No drift signals detected for user {user_id}")
            return []

        # Step 4: Aggregate signals
        actionable_signals = self.aggregator.aggregate(all_signals)

        if not actionable_signals:
            logger.info(
                f"No actionable signals after aggregation for user {user_id}"
            )
            return []

        # Step 5: Convert to events
        events = self._create_events(
            user_id=user_id,
            signals=actionable_signals,
            reference=reference,
            current=current,
        )

        # Step 6: Persist events
        self._persist_events(events)

        logger.info(
            f"Drift detection complete for {user_id}: {len(events)} event(s)"
        )
        return events

    def _preflight_checks(self, user_id: str) -> bool:
        """
        Run pre-flight checks before detection.

        Checks:
        1. User has sufficient data (behaviors and history)
        2. Cooldown period has elapsed since last detection

        Args:
            user_id: User identifier

        Returns:
            True if checks pass, False otherwise
        """
        # Check sufficient data
        if not self.snapshot_builder.validate_sufficient_data(user_id):
            logger.info(
                f"User {user_id} has insufficient data for drift detection"
            )
            return False

        # Check cooldown period
        last_detection = self.drift_event_repo.get_latest_detection_time(
            user_id
        )
        if last_detection:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            time_since = now_ts - last_detection
            cooldown = self.settings.scan_cooldown_seconds

            if time_since < cooldown:
                remaining = cooldown - time_since
                logger.info(
                    f"User {user_id} is in cooldown period "
                    f"({remaining}s remaining)"
                )
                return False

        logger.info(f"Pre-flight checks passed for user {user_id}")
        return True

    def _create_events(
        self, user_id, signals, reference, current
    ) -> List[DriftEvent]:
        """
        Convert drift signals to drift events.

        Args:
            user_id: User identifier
            signals: Aggregated drift signals
            reference: Reference snapshot
            current: Current snapshot

        Returns:
            List of DriftEvent objects
        """
        events = []
        detected_at = int(datetime.now(timezone.utc).timestamp())

        for signal in signals:
            event = DriftEvent.from_signal(
                signal=signal,
                user_id=user_id,
                reference_window_start=int(reference.window_start.timestamp()),
                reference_window_end=int(reference.window_end.timestamp()),
                current_window_start=int(current.window_start.timestamp()),
                current_window_end=int(current.window_end.timestamp()),
                detected_at=detected_at,
                behavior_ref_ids=[],  # Can be populated if needed
                conflict_ref_ids=[],
            )
            events.append(event)
            logger.debug(
                f"Created event: {event.drift_type.value} "
                f"(score: {event.drift_score:.3f})"
            )

        return events

    def _persist_events(self, events: List[DriftEvent]) -> None:
        """
        Persist drift events to database.

        Args:
            events: DriftEvent objects to persist
        """
        for event in events:
            try:
                event_id = self.drift_event_repo.insert(event)
                logger.info(
                    f"Persisted drift event: {event_id} "
                    f"({event.drift_type.value})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist drift event "
                    f"{event.drift_event_id}: {e}",
                    exc_info=True,
                )
