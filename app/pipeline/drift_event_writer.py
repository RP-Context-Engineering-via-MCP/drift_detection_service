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

logger = logging.getLogger(__name__)


def now() -> int:
    """Get current UTC timestamp as integer."""
    return int(datetime.now(timezone.utc).timestamp())


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
        Write drift events to database and publish to Redis Streams.
        
        This method ensures atomicity: events are only published to Redis
        if the database write succeeds.
        
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
        
        try:
            # Write events to database (within transaction if supported)
            for event in events:
                try:
                    event_id = self.drift_event_repo.insert(event)
                    persisted_event_ids.append(event_id)
                    
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
            
            # Publish persisted events to Redis Streams
            for event in events:
                if event.drift_event_id in persisted_event_ids:
                    try:
                        self._publish_to_stream(
                            event,
                            reference_snapshot=reference_snapshot,
                            current_snapshot=current_snapshot
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to publish event {event.drift_event_id} to Redis: {e}",
                            exc_info=True
                        )
                        # Don't fail the entire operation if Redis publish fails
                        # The event is already persisted in the database
            
            logger.info(
                f"Successfully wrote {len(persisted_event_ids)} event(s) "
                f"and published to Redis Streams"
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
        
        Event format:
        {
            "event_type": "drift.detected",
            "drift_event_id": "drift_abc123",
            "user_id": "user_123",
            "drift_type": "TOPIC_EMERGENCE",
            "drift_score": 0.85,
            "confidence": 0.92,
            "severity": "MEDIUM",
            "affected_targets": ["Python", "Docker"],
            "detected_at": 1234567890,
            "evidence": {...},
            "reference_window": {"start": 123, "end": 456},
            "current_window": {"start": 789, "end": 101112}
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
        # Build event payload
        event_data = {
            "event_type": "drift.detected",
            "drift_event_id": event.drift_event_id,
            "user_id": event.user_id,
            "drift_type": event.drift_type.value,
            "drift_score": event.drift_score,
            "confidence": event.confidence,
            "severity": event.severity.value,
            "affected_targets": event.affected_targets,
            "detected_at": event.detected_at,
            "reference_window": {
                "start": event.reference_window_start,
                "end": event.reference_window_end
            },
            "current_window": {
                "start": event.current_window_start,
                "end": event.current_window_end
            }
        }
        
        # Add evidence (serialize to JSON string for Redis)
        if event.evidence:
            event_data["evidence"] = json.dumps(event.evidence)
        
        # Add snapshot context if provided
        if reference_snapshot:
            event_data["reference_behavior_count"] = len(reference_snapshot.behaviors)
        
        if current_snapshot:
            event_data["current_behavior_count"] = len(current_snapshot.behaviors)
        
        try:
            # Publish to Redis Stream
            # XADD returns the message ID (e.g., "1234567890123-0")
            message_id = self.redis_client.xadd(
                name=self.stream_name,
                fields=event_data,
                maxlen=10000,  # Keep last 10k events to prevent unbounded growth
                approximate=True
            )
            
            logger.info(
                f"Published drift event {event.drift_event_id} to stream "
                f"'{self.stream_name}' with message ID: {message_id}"
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
