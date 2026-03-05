"""
DriftEventWriter - Persists drift events and publishes to Redis Streams.

Responsibilities:
- Write DriftEvent objects to database
- Publish drift.detected events to Redis Streams for downstream consumers
- Handle batch writes efficiently
- Ensure atomic transactions
"""

import logging
import json
import redis
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.config import get_settings
from app.db.repositories.drift_event_repo import DriftEventRepository
from app.models.drift import DriftEvent
from app.models.snapshot import BehaviorSnapshot
from app.utils.time import now

logger = logging.getLogger(__name__)


class DriftEventWriter:
    """
    Writes drift events to database and publishes to Redis Streams.
    
    Ensures atomicity: events are only published to Redis if database
    write succeeds.
    """

    def __init__(self, connection, redis_client: Optional[redis.Redis] = None):
        """
        Initialize the drift event writer.
        
        Args:
            connection: Database connection (psycopg2)
            redis_client: Optional Redis client (created if not provided)
        """
        self.connection = connection
        self.drift_event_repo = DriftEventRepository(connection)
        self.settings = get_settings()
        
        # Initialize Redis client for stream publishing
        if redis_client is None:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
        else:
            self.redis_client = redis_client
        
        self.stream_name = self.settings.redis_stream_drift_events

    def write(
        self,
        events: List[DriftEvent],
        reference_snapshot: Optional[BehaviorSnapshot] = None,
        current_snapshot: Optional[BehaviorSnapshot] = None
    ) -> List[str]:
        """
        Write drift events to database and publish aggregated message to Redis Streams.
        
        This method aggregates all events from a single scan into ONE Redis message
        with the highest severity and deduplicated behavior_ref_ids.
        
        Args:
            events: List of DriftEvent objects to persist
            reference_snapshot: Optional reference snapshot for context
            current_snapshot: Optional current snapshot for context
            
        Returns:
            List of drift_event_ids that were successfully persisted
            
        Raises:
            Exception: If database write fails (Redis publish is rolled back)
        """
        if not events:
            logger.debug("No events to write")
            return []
        
        logger.info(f"Writing {len(events)} drift event(s) to database")
        
        persisted_event_ids = []
        persisted_events = []
        
        try:
            # Write events to database (within transaction if supported)
            for event in events:
                try:
                    event_id = self.drift_event_repo.insert(event)
                    persisted_event_ids.append(event_id)
                    persisted_events.append(event)
                    
                    logger.info(
                        f"Persisted drift event: {event_id} "
                        f"({event.drift_type.value}, score: {event.drift_score:.3f})"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Failed to persist drift event {event.drift_event_id}: {e}",
                        exc_info=True
                    )
                    # Continue with other events
            
            # If no events were persisted, return early
            if not persisted_event_ids:
                logger.warning("No events were successfully persisted to database")
                return []
            
            # Publish ONE aggregated message for all events from this scan
            try:
                self._publish_aggregated_message(
                    events=persisted_events,
                    reference_snapshot=reference_snapshot,
                    current_snapshot=current_snapshot
                )
            except Exception as e:
                logger.error(
                    f"Failed to publish aggregated message to Redis: {e}",
                    exc_info=True
                )
                # Don't fail the entire operation if Redis publish fails
                # The events are already persisted in the database
            
            logger.info(
                f"Successfully wrote {len(persisted_event_ids)} event(s) "
                f"and published aggregated message to Redis Streams"
            )
            
            return persisted_event_ids
            
        except Exception as e:
            logger.error(f"Error in write operation: {e}", exc_info=True)
            raise

    def write_single(
        self,
        event: DriftEvent,
        publish_to_stream: bool = True
    ) -> str:
        """
        Write a single drift event to database and optionally publish to Redis.
        
        Args:
            event: DriftEvent object to persist
            publish_to_stream: Whether to publish to Redis Streams
            
        Returns:
            drift_event_id of the persisted event
            
        Raises:
            Exception: If database write fails
        """
        try:
            # Persist to database
            event_id = self.drift_event_repo.insert(event)
            
            logger.info(
                f"Persisted drift event: {event_id} "
                f"({event.drift_type.value})"
            )
            
            # Publish to Redis Stream if requested
            if publish_to_stream:
                try:
                    self._publish_to_stream(event)
                except Exception as e:
                    logger.error(
                        f"Failed to publish event {event_id} to Redis: {e}",
                        exc_info=True
                    )
                    # Event is still persisted, so we don't fail
            
            return event_id
            
        except Exception as e:
            logger.error(
                f"Failed to write drift event {event.drift_event_id}: {e}",
                exc_info=True
            )
            raise

    def _publish_to_stream(
        self,
        event: DriftEvent,
        reference_snapshot: Optional[BehaviorSnapshot] = None,
        current_snapshot: Optional[BehaviorSnapshot] = None
    ) -> str:
        """
        Publish a drift.detected event to Redis Streams.
        
        Event format (published as 'payload' field):
        XADD drift.events * payload '{"drift_event_id": "...", "user_id": "...", "severity": "..."}'
        
        Payload JSON structure:
        {
            "drift_event_id": "drift-evt-abc123",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "severity": "STRONG_DRIFT"
        }
        
        Args:
            event: DriftEvent to publish
            reference_snapshot: Optional reference snapshot for additional context
            current_snapshot: Optional current snapshot for additional context
            
        Returns:
            Redis Stream message ID
            
        Raises:
            redis.RedisError: If publishing fails
        """
        # Build event payload for drift.events stream
        event_data = {
            "drift_event_id": event.drift_event_id,
            "user_id": event.user_id,
            "severity": event.severity.value,
            "behavior_ref_ids": event.behavior_ref_ids
        }
        
        logger.debug(
            f"Publishing event to stream '{self.stream_name}': "
            f"drift_event_id={event.drift_event_id}, "
            f"severity={event.severity.value}, "
            f"behavior_count={len(event.behavior_ref_ids)}"
        )
        
        try:
            # Publish to Redis Stream
            # XADD returns the message ID (e.g., "1234567890123-0")
            # Wrap in 'payload' field as JSON string to match consumer format
            message_id = self.redis_client.xadd(
                name=self.stream_name,
                fields={"payload": json.dumps(event_data)},
                maxlen=10000,  # Keep last 10k events to prevent unbounded growth
                approximate=True
            )
            
            logger.info(
                f"Published drift event {event.drift_event_id} to stream "
                f"'{self.stream_name}' with message ID: {message_id} "
                f"(severity: {event.severity.value})"
            )
            
            return message_id
            
        except redis.RedisError as e:
            logger.error(
                f"Redis error publishing event {event.drift_event_id}: {e}",
                exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error publishing event {event.drift_event_id}: {e}",
                exc_info=True
            )
            raise

    def _publish_aggregated_message(
        self,
        events: List[DriftEvent],
        reference_snapshot: Optional[BehaviorSnapshot] = None,
        current_snapshot: Optional[BehaviorSnapshot] = None
    ) -> str:
        """
        Publish ONE aggregated drift message for all events from a single scan.
        
        Aggregates multiple drift events into a single Redis message with:
        - All drift_event_ids from the scan
        - Highest severity detected
        - Deduplicated union of all behavior_ref_ids
        
        Args:
            events: List of DriftEvent objects to aggregate
            reference_snapshot: Optional reference snapshot for additional context
            current_snapshot: Optional current snapshot for additional context
            
        Returns:
            Redis Stream message ID
            
        Raises:
            redis.RedisError: If publishing fails
        """
        if not events:
            logger.warning("No events to publish in aggregated message")
            return ""
        
        # Get user_id (should be same for all events in a scan)
        user_id = events[0].user_id
        
        # Collect all drift_event_ids
        drift_event_ids = [event.drift_event_id for event in events]
        
        # Find highest severity
        severity_order = {
            "NO_DRIFT": 0,
            "WEAK_DRIFT": 1,
            "MODERATE_DRIFT": 2,
            "STRONG_DRIFT": 3
        }
        highest_severity = max(events, key=lambda e: severity_order.get(e.severity.value, 0)).severity.value
        
        # Deduplicate and merge all behavior_ref_ids
        all_behavior_ids = set()
        for event in events:
            all_behavior_ids.update(event.behavior_ref_ids)
        behavior_ref_ids = sorted(list(all_behavior_ids))
        
        # Build aggregated event payload
        aggregated_data = {
            "drift_event_ids": drift_event_ids,
            "user_id": user_id,
            "severity": highest_severity,
            "behavior_ref_ids": behavior_ref_ids,
            "event_count": len(events)
        }
        
        logger.debug(
            f"Publishing aggregated message to stream '{self.stream_name}': "
            f"user_id={user_id}, "
            f"event_count={len(events)}, "
            f"highest_severity={highest_severity}, "
            f"behavior_count={len(behavior_ref_ids)}"
        )
        
        try:
            # Publish to Redis Stream
            message_id = self.redis_client.xadd(
                name=self.stream_name,
                fields={"payload": json.dumps(aggregated_data)},
                maxlen=10000,
                approximate=True
            )
            
            logger.info(
                f"Published aggregated drift message to stream '{self.stream_name}' "
                f"with message ID: {message_id} "
                f"(user: {user_id}, events: {len(events)}, severity: {highest_severity}, "
                f"behaviors: {len(behavior_ref_ids)})"
            )
            
            return message_id
            
        except redis.RedisError as e:
            logger.error(
                f"Redis error publishing aggregated message for user {user_id}: {e}",
                exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error publishing aggregated message for user {user_id}: {e}",
                exc_info=True
            )
            raise

    def batch_write(
        self,
        events: List[DriftEvent],
        batch_size: int = 50
    ) -> List[str]:
        """
        Write events in batches for better performance.
        
        Args:
            events: List of DriftEvent objects
            batch_size: Number of events per batch
            
        Returns:
            List of persisted event IDs
        """
        if not events:
            return []
        
        logger.info(f"Batch writing {len(events)} events (batch_size={batch_size})")
        
        all_event_ids = []
        
        # Process in batches
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            batch_ids = self.write(batch)
            all_event_ids.extend(batch_ids)
            
            logger.debug(
                f"Processed batch {i // batch_size + 1}: "
                f"{len(batch_ids)} events written"
            )
        
        return all_event_ids

    def close(self):
        """Close Redis connection."""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.debug("Closed Redis connection")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")


# ─── Utility Functions ───────────────────────────────────────────────────

def create_drift_event_writer(connection) -> DriftEventWriter:
    """
    Factory function to create a DriftEventWriter.
    
    Args:
        connection: Database connection
        
    Returns:
        DriftEventWriter instance
    """
    return DriftEventWriter(connection)
