"""
BehaviorEventHandler - Processes behavior events from Redis Streams.

Handles:
- behavior.created → upsert behavior_snapshots
- behavior.reinforced → update reinforcement_count, last_seen_at
- behavior.superseded → update state to SUPERSEDED
- behavior.conflict.resolved → insert conflict_snapshots

Enqueues drift scan jobs when appropriate based on configurable gates.
"""

import logging
import json
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone

from app.config import get_settings
from app.db.connection import get_sync_connection
from app.db.repositories import BehaviorRepository, ConflictRepository, ScanJobRepository
from app.utils.time import now

logger = logging.getLogger(__name__)


class BehaviorEventHandler:
    """Handles behavior events and manages drift scan job enqueuing."""

    # Track processed event IDs to ensure idempotency (in-memory)
    # In production, consider Redis-based tracking for multi-instance deployments
    _processed_events: Set[str] = set()
    _max_processed_cache = 10000  # Limit cache size to prevent memory growth

    def __init__(self):
        """Initialize the behavior event handler."""
        self.settings = get_settings()

    def handle_event(self, event_id: str, event_data: Dict[str, Any]) -> None:
        """
        Process a behavior event from the stream.

        Args:
            event_id: Unique event ID from Redis stream
            event_data: Event payload as dictionary

        Raises:
            ValueError: If event type is missing or invalid
        """
        # Idempotency check
        if event_id in self._processed_events:
            logger.debug(f"Skipping duplicate event {event_id}")
            return

        event_type = event_data.get("event_type")
        
        if not event_type:
            logger.warning(f"Event {event_id} missing event_type, skipping")
            return

        # payload may be a nested dict (already parsed by redis_consumer)
        # or the fields may sit at the top level — support both shapes
        payload = event_data.get("payload", event_data)
        if isinstance(payload, str):
            payload = json.loads(payload)

        try:
            # Route to appropriate handler
            if event_type == "behavior.created":
                processed = self._on_behavior_created(payload)
            elif event_type == "behavior.reinforced":
                processed = self._on_behavior_reinforced(payload)
            elif event_type == "behavior.superseded":
                processed = self._on_behavior_superseded(payload)
            elif event_type == "behavior.conflict.resolved":
                processed = self._on_conflict_resolved(payload)
            else:
                logger.warning(f"Unknown event type: {event_type}")
                return

            # Mark as processed
            self._mark_processed(event_id)
            
            if processed:
                logger.info(f"Successfully processed event {event_id} ({event_type})")
            else:
                logger.info(f"Event {event_id} ({event_type}) skipped due to missing required fields")

        except Exception as e:
            logger.error(f"Failed to process event {event_id}: {e}", exc_info=True)
            raise

    def _on_behavior_created(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle behavior.created event.

        Inserts a new behavior snapshot and potentially enqueues a drift scan.

        Returns:
            bool: True if event was processed, False if skipped due to missing fields.

        Expected payload:
        {
            "event_type": "behavior.created",
            "user_id": "user123",
            "behavior_id": "beh_abc",
            "target": "Python",
            "intent": "learn",
            "context": "programming",
            "polarity": "POSITIVE",
            "credibility": 0.8,
            "created_at": 1234567890
        }
        """
        user_id = event_data.get("user_id")
        behavior_id = event_data.get("behavior_id")

        if not user_id or not behavior_id:
            logger.warning("behavior.created event missing user_id or behavior_id")
            return False

        with get_sync_connection() as conn:
            behavior_repo = BehaviorRepository(conn)

            # Upsert behavior snapshot
            # Use payload values when provided, with sensible defaults
            created_at = event_data.get("created_at", now())
            behavior_repo.upsert_behavior(
                user_id=user_id,
                behavior_id=behavior_id,
                target=event_data.get("target", ""),
                intent=event_data.get("intent", ""),
                context=event_data.get("context", ""),
                polarity=event_data.get("polarity", "NEUTRAL"),
                credibility=event_data.get("credibility", 0.5),
                reinforcement_count=event_data.get("reinforcement_count", 1),
                state=event_data.get("state", "ACTIVE"),
                created_at=created_at,
                last_seen_at=event_data.get("last_seen_at", created_at)
            )

            # Maybe enqueue scan
            self._maybe_enqueue_scan(
                conn=conn,
                user_id=user_id,
                trigger_event="behavior.created"
            )

        return True

    def _on_behavior_reinforced(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle behavior.reinforced event.

        Updates reinforcement count and last_seen_at timestamp.

        Expected payload:
        {
            "event_type": "behavior.reinforced",
            "user_id": "user123",
            "behavior_id": "beh_abc",
            "occurred_at": 1234567890
        }
        """
        user_id = event_data.get("user_id")
        behavior_id = event_data.get("behavior_id")

        if not user_id or not behavior_id:
            logger.warning("behavior.reinforced event missing user_id or behavior_id")
            return False

        with get_sync_connection() as conn:
            behavior_repo = BehaviorRepository(conn)

            behavior = behavior_repo.get_behavior(user_id, behavior_id)
            
            if not behavior:
                logger.warning(
                    f"Cannot reinforce behavior {behavior_id} for user {user_id}: "
                    "behavior not found"
                )
                return False

            # Use values from event directly — BRM already computed these
            new_count = event_data.get("new_reinforcement_count", behavior["reinforcement_count"] + 1)
            new_credibility = event_data.get("new_credibility", behavior["credibility"])
            last_seen_at = event_data.get("last_seen_at", now())

            behavior_repo.update_behavior(
                user_id=user_id,
                behavior_id=behavior_id,
                credibility=new_credibility,
                reinforcement_count=new_count,
                last_seen_at=last_seen_at
            )

            # Maybe enqueue scan
            self._maybe_enqueue_scan(
                conn=conn,
                user_id=user_id,
                trigger_event="behavior.reinforced"
            )

        return True

    def _on_behavior_superseded(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle behavior.superseded event.

        Updates behavior state to SUPERSEDED.

        Returns:
            bool: True if event was processed, False if skipped due to missing fields.

        Expected payload:
        {
            "event_type": "behavior.superseded",
            "user_id": "user123",
            "behavior_id": "beh_abc",
            "superseded_by": "beh_def"
        }
        """
        user_id = event_data.get("user_id")
        behavior_id = event_data.get("old_behavior_id")  # correct field from event schema

        if not user_id or not behavior_id:
            logger.warning("behavior.superseded event missing user_id or old_behavior_id")
            return False

        with get_sync_connection() as conn:
            behavior_repo = BehaviorRepository(conn)

            # Update state to SUPERSEDED
            behavior_repo.update_behavior(
                user_id=user_id,
                behavior_id=behavior_id,
                state="SUPERSEDED"
            )

            # Maybe enqueue scan
            self._maybe_enqueue_scan(
                conn=conn,
                user_id=user_id,
                trigger_event="behavior.superseded"
            )

        return True

    def _on_conflict_resolved(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle behavior.conflict.resolved event.

        Inserts a conflict snapshot and potentially enqueues a drift scan.

        Returns:
            bool: True if event was processed, False if skipped due to missing fields.

        Expected payload:
        {
            "event_type": "behavior.conflict.resolved",
            "user_id": "user123",
            "conflict_id": "conf_xyz",
            "behavior_id_1": "beh_abc",
            "behavior_id_2": "beh_def",
            "conflict_type": "TARGET_POLARITY",
            "resolution_status": "USER_RESOLVED",
            "old_polarity": "POSITIVE",
            "new_polarity": "NEGATIVE",
            "created_at": 1234567890
        }
        """
        user_id = event_data.get("user_id")
        conflict_id = event_data.get("conflict_id")

        if not user_id or not conflict_id:
            logger.warning("conflict.resolved event missing user_id or conflict_id")
            return False

        with get_sync_connection() as conn:
            conflict_repo = ConflictRepository(conn)

            # Insert conflict snapshot
            conflict_repo.insert_conflict(
                user_id=user_id,
                conflict_id=conflict_id,
                behavior_id_1=event_data.get("behavior_id_1", ""),
                behavior_id_2=event_data.get("behavior_id_2", ""),
                conflict_type=event_data.get("conflict_type", "UNKNOWN"),
                resolution_status=event_data.get("resolution_status", "UNRESOLVED"),
                old_polarity=event_data.get("old_polarity"),
                new_polarity=event_data.get("new_polarity"),
                old_target=event_data.get("old_target"),
                new_target=event_data.get("new_target"),
                created_at=event_data.get("created_at", now())
            )

            # Maybe enqueue scan (conflicts are important signals)
            self._maybe_enqueue_scan(
                conn=conn,
                user_id=user_id,
                trigger_event="behavior.conflict.resolved",
                priority="HIGH"  # Conflicts get high priority
            )

        return True

    def _maybe_enqueue_scan(
        self,
        conn,
        user_id: str,
        trigger_event: str,
        priority: str = "NORMAL"
    ) -> None:
        """
        Conditionally enqueue a drift scan job for a user.

        Applies gating logic to prevent excessive scanning:
        1. Check if user has pending scan job already (prevent duplicates)
        2. Check cooldown period since last scan
        3. Check if user has minimum data for meaningful drift detection

        Args:
            conn: Database connection
            user_id: User to potentially scan
            trigger_event: Event that triggered this check
            priority: Job priority (NORMAL, HIGH, LOW)
        """
        scan_job_repo = ScanJobRepository(conn)
        behavior_repo = BehaviorRepository(conn)

        # Gate 1: Check for existing pending job
        if scan_job_repo.has_pending_job(user_id):
            logger.debug(
                f"Skipping scan enqueue for {user_id}: pending job already exists"
            )
            return

        # Gate 2: Check cooldown period
        last_scan_time = scan_job_repo.get_last_completed_scan(user_id)
        
        if last_scan_time:
            time_since_last_scan = now() - last_scan_time
            cooldown = self.settings.scan_cooldown_seconds
            
            if time_since_last_scan < cooldown:
                logger.debug(
                    f"Skipping scan enqueue for {user_id}: "
                    f"cooldown not met (last scan: {time_since_last_scan}s ago, "
                    f"cooldown: {cooldown}s)"
                )
                return

        # Gate 3: Check minimum data requirements
        active_behaviors = behavior_repo.get_active_behaviors(user_id)
        
        if len(active_behaviors) < self.settings.min_behaviors_for_drift:
            logger.debug(
                f"Skipping scan enqueue for {user_id}: "
                f"insufficient behaviors ({len(active_behaviors)} < "
                f"{self.settings.min_behaviors_for_drift})"
            )
            return

        # All gates passed - enqueue the scan job
        job_id = scan_job_repo.enqueue(
            user_id=user_id,
            trigger_event=trigger_event,
            priority=priority
        )

        logger.info(
            f"Enqueued drift scan job {job_id} for user {user_id} "
            f"(trigger: {trigger_event}, priority: {priority})"
        )

    def _mark_processed(self, event_id: str) -> None:
        """
        Mark an event as processed for idempotency.

        Args:
            event_id: Event ID to mark as processed
        """
        # Limit cache size to prevent unbounded memory growth
        if len(self._processed_events) >= self._max_processed_cache:
            # Clear old entries (simple approach: clear half the cache)
            # In production, use an LRU cache or Redis-based tracking
            logger.warning(
                f"Processed events cache exceeded {self._max_processed_cache}, "
                "clearing oldest entries"
            )
            self._processed_events = set(
                list(self._processed_events)[self._max_processed_cache // 2:]
            )

        self._processed_events.add(event_id)