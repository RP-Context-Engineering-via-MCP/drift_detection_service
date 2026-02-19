"""Builds BehaviorSnapshots from database records."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import get_settings
from app.db.connection import get_sync_connection_simple
from app.db.repositories.behavior_repo import BehaviorRepository
from app.db.repositories.conflict_repo import ConflictRepository
from app.models.snapshot import BehaviorSnapshot

logger = logging.getLogger(__name__)


class SnapshotBuilder:
    """Constructs BehaviorSnapshot objects from database queries."""

    def __init__(self):
        """Initialize with repository connections."""
        self.connection = get_sync_connection_simple()
        self.behavior_repo = BehaviorRepository(self.connection)
        self.conflict_repo = ConflictRepository(self.connection)
        self.settings = get_settings()
        logger.info("SnapshotBuilder initialized")

    def build_snapshot(
        self,
        user_id: str,
        window_start: datetime,
        window_end: datetime,
        active_only: bool = True,
    ) -> BehaviorSnapshot:
        """
        Build a snapshot for a specific time window.

        Args:
            user_id: User identifier
            window_start: Start of the time window
            window_end: End of the time window
            active_only: If True, only include currently ACTIVE behaviors.
                        If False, include behaviors that were active during the window
                        (even if now SUPERSEDED). Use False for reference windows.

        Returns:
            BehaviorSnapshot with behaviors and conflicts from the window
            
        Raises:
            ValueError: If window_start >= window_end or invalid user_id
            RuntimeError: If database query fails
        """
        # Validate inputs
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        if window_start >= window_end:
            raise ValueError(
                f"Invalid time window: start ({window_start}) must be before end ({window_end})"
            )
        
        # Check for unreasonably large windows (> 1 year)
        window_days = (window_end - window_start).days
        if window_days > 365:
            logger.warning(
                f"Large time window detected: {window_days} days. "
                f"This may impact performance."
            )
        
        start_ts = int(window_start.timestamp())
        end_ts = int(window_end.timestamp())

        logger.debug(
            f"Building snapshot for {user_id}: {window_start} to {window_end}",
            extra={"user_id": user_id, "window_days": window_days}
        )

        try:
            # Query behaviors in window
            behaviors = self.behavior_repo.get_behaviors_in_window(
                user_id, start_ts, end_ts, active_only=active_only
            )
            logger.debug(
                f"Found {len(behaviors)} behaviors in window (active_only={active_only})",
                extra={"user_id": user_id, "behavior_count": len(behaviors)}
            )

            # Query conflicts in window
            conflicts = self.conflict_repo.get_conflicts_in_window(
                user_id, start_ts, end_ts
            )
            logger.debug(
                f"Found {len(conflicts)} conflicts in window",
                extra={"user_id": user_id, "conflict_count": len(conflicts)}
            )
        except Exception as e:
            logger.error(
                f"Database query failed for user {user_id}: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Failed to query behavior data: {e}") from e

        # Create snapshot (distributions computed automatically)
        # For reference windows (active_only=False), include superseded behaviors
        try:
            snapshot = BehaviorSnapshot(
                user_id=user_id,
                window_start=window_start,
                window_end=window_end,
                behaviors=behaviors,
                conflict_records=conflicts,
                include_superseded=not active_only,  # True for reference windows
            )
        except Exception as e:
            logger.error(
                f"Failed to create snapshot for user {user_id}: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Snapshot creation failed: {e}") from e

        logger.info(
            f"Snapshot built: {len(behaviors)} behaviors, "
            f"{len(conflicts)} conflicts, "
            f"{len(snapshot.get_targets())} unique targets",
            extra={
                "user_id": user_id,
                "behavior_count": len(behaviors),
                "conflict_count": len(conflicts),
                "unique_targets": len(snapshot.get_targets())
            }
        )

        return snapshot

    def build_reference_and_current(
        self, user_id: str
    ) -> tuple[BehaviorSnapshot, BehaviorSnapshot]:
        """
        Build reference and current snapshots based on configuration.

        Reference window: [now - reference_window_start_days, now - reference_window_end_days]
        Current window: [now - current_window_days, now]

        Args:
            user_id: User identifier

        Returns:
            Tuple of (reference_snapshot, current_snapshot)
        """
        now = datetime.now(timezone.utc)

        # Current window: last N days
        current_start = now - timedelta(days=self.settings.current_window_days)
        current_end = now
        logger.info(
            f"Current window: {current_start.date()} to {current_end.date()}"
        )

        # Reference window: M to N days ago
        ref_end = now - timedelta(days=self.settings.reference_window_end_days)
        ref_start = now - timedelta(
            days=self.settings.reference_window_start_days
        )
        logger.info(
            f"Reference window: {ref_start.date()} to {ref_end.date()}"
        )

        # Build both snapshots
        # Reference: include behaviors that were active during that historical period
        # (even if now superseded)
        reference = self.build_snapshot(user_id, ref_start, ref_end, active_only=False)
        # Current: only currently active behaviors
        current = self.build_snapshot(user_id, current_start, current_end, active_only=True)

        return reference, current

    def validate_sufficient_data(self, user_id: str) -> bool:
        """
        Check if user has enough data for meaningful drift detection.

        Args:
            user_id: User identifier

        Returns:
            True if sufficient data exists, False otherwise
        """
        # Check minimum behavior count
        count = self.behavior_repo.count_active_behaviors(user_id)
        if count < self.settings.min_behaviors_for_drift:
            logger.warning(
                f"User {user_id} has only {count} behaviors "
                f"(minimum: {self.settings.min_behaviors_for_drift})"
            )
            return False

        # Check minimum history duration
        earliest = self.behavior_repo.get_earliest_behavior_date(user_id)
        if earliest is None:
            logger.warning(f"User {user_id} has no behavior data")
            return False

        now_ts = int(datetime.now(timezone.utc).timestamp())
        days_of_history = (now_ts - earliest) / 86400

        if days_of_history < self.settings.min_days_of_history:
            logger.warning(
                f"User {user_id} has only {days_of_history:.1f} days of history "
                f"(minimum: {self.settings.min_days_of_history})"
            )
            return False

        logger.info(
            f"User {user_id} has sufficient data: "
            f"{count} behaviors, {days_of_history:.1f} days of history"
        )
        return True
