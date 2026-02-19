"""
RedisConsumer - Consumes events from Redis Streams.

Subscribes to behavior.events stream and processes events using
BehaviorEventHandler. Implements consumer group semantics with
automatic retries and graceful shutdown.

Key features:
- Consumer group management (create if not exists)
- Blocking reads with configurable timeout
- Message acknowledgment after successful processing
- Automatic reconnection on failure
- Graceful shutdown on SIGINT/SIGTERM
"""

import logging
import signal
import time
import redis
import json
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from app.config import get_settings
from app.consumer.behavior_event_handler import BehaviorEventHandler

logger = logging.getLogger(__name__)


class RedisConsumer:
    """Consumes events from Redis Streams and dispatches to event handlers."""

    def __init__(self):
        """Initialize the Redis consumer."""
        self.settings = get_settings()
        self.handler = BehaviorEventHandler()
        
        self.redis_client: Optional[redis.Redis] = None
        self.running = False
        
        # Consumer configuration
        self.stream_name = self.settings.redis_stream_behavior_events
        self.consumer_group = self.settings.redis_consumer_group
        self.consumer_name = self.settings.redis_consumer_name
        self.block_ms = self.settings.redis_block_ms
        self.max_events_per_read = self.settings.redis_max_events_per_read
        
        # Track last processed event ID for resumption
        self.last_id = ">"  # ">" means read only new messages

    def connect(self) -> None:
        """
        Establish connection to Redis.

        Raises:
            redis.ConnectionError: If connection fails
        """
        try:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            
            # Test connection
            self.redis_client.ping()
            
            logger.info(f"Connected to Redis at {self.settings.redis_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def disconnect(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            try:
                self.redis_client.close()
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.warning(f"Error during Redis disconnect: {e}")
            finally:
                self.redis_client = None

    def ensure_consumer_group(self) -> None:
        """
        Create consumer group if it doesn't exist.

        Consumer groups enable multiple consumers to process events in parallel
        while ensuring each event is processed exactly once.
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")

        try:
            # Try to create the consumer group
            # Start reading from the beginning of the stream (id='0')
            self.redis_client.xgroup_create(
                name=self.stream_name,
                groupname=self.consumer_group,
                id="0",
                mkstream=True  # Create stream if it doesn't exist
            )
            
            logger.info(
                f"Created consumer group '{self.consumer_group}' "
                f"for stream '{self.stream_name}'"
            )
            
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists, this is fine
                logger.info(
                    f"Consumer group '{self.consumer_group}' already exists "
                    f"for stream '{self.stream_name}'"
                )
            else:
                logger.error(f"Failed to create consumer group: {e}")
                raise

    def start(self) -> None:
        """
        Start consuming events from Redis Streams.

        Runs in a loop until stopped via SIGINT/SIGTERM or stop() method.
        """
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            # Connect and initialize
            self.connect()
            self.ensure_consumer_group()
            
            self.running = True
            logger.info(
                f"Started consuming from stream '{self.stream_name}' "
                f"as '{self.consumer_name}' in group '{self.consumer_group}'"
            )
            
            # Main consumption loop
            while self.running:
                try:
                    self._consume_batch()
                except redis.ConnectionError as e:
                    logger.error(f"Redis connection error: {e}")
                    self._reconnect()
                except Exception as e:
                    logger.error(f"Error in consumption loop: {e}", exc_info=True)
                    time.sleep(5)  # Back off before retrying
            
            logger.info("Consumer stopped")
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the consumer gracefully."""
        logger.info("Stopping consumer...")
        self.running = False
        self.disconnect()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals (SIGINT, SIGTERM)."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.stop()

    def _reconnect(self) -> None:
        """
        Attempt to reconnect to Redis.

        Implements exponential backoff with max retry limit.
        """
        max_retries = 5
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Reconnection attempt {attempt + 1}/{max_retries}")
                
                self.disconnect()
                time.sleep(retry_delay)
                self.connect()
                self.ensure_consumer_group()
                
                logger.info("Reconnected successfully")
                return
                
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
                retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s
        
        logger.error("Max reconnection attempts reached, stopping consumer")
        self.stop()

    def _consume_batch(self) -> None:
        """
        Read and process a batch of events from the stream.

        Uses XREADGROUP to read events assigned to this consumer.
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")

        try:
            # Read events from the stream using consumer group
            # XREADGROUP syntax: GROUP group consumer [COUNT count] [BLOCK milliseconds] STREAMS key [key ...] ID [ID ...]
            response = self.redis_client.xreadgroup(
                groupname=self.consumer_group,
                consumername=self.consumer_name,
                streams={self.stream_name: self.last_id},
                count=self.max_events_per_read,
                block=self.block_ms,
            )
            
            if not response:
                # No new messages (timeout reached)
                return
            
            # Process events from the response
            # Response format: [(stream_name, [(event_id, event_data), ...])]
            for stream_name, events in response:
                for event_id, event_data in events:
                    self._process_event(event_id, event_data)
            
        except redis.ConnectionError:
            raise  # Let the caller handle reconnection
        except Exception as e:
            logger.error(f"Error consuming batch: {e}", exc_info=True)

    def _process_event(self, event_id: str, event_data: Dict[str, str]) -> None:
        """
        Process a single event.

        Args:
            event_id: Redis stream event ID (e.g., "1234567890123-0")
            event_data: Event payload as dictionary of strings
        """
        try:
            logger.debug(f"Processing event {event_id}: {event_data}")
            
            # Parse event data (Redis Streams stores everything as strings)
            parsed_data = self._parse_event_data(event_data)
            
            # Dispatch to handler
            self.handler.handle_event(event_id, parsed_data)
            
            # Acknowledge successful processing
            self._ack_event(event_id)
            
        except Exception as e:
            logger.error(
                f"Failed to process event {event_id}: {e}",
                exc_info=True
            )
            # Don't ACK failed events - they'll be retried or moved to PEL
            # (Pending Entry List for monitoring/dead letter handling)

    def _parse_event_data(self, event_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Parse event data from Redis Streams format.

        Redis Streams stores all values as strings, so we need to convert
        them to appropriate types.

        Args:
            event_data: Raw event data from Redis (all strings)

        Returns:
            Parsed event data with proper types
        """
        parsed = {}
        
        for key, value in event_data.items():
            # Try to parse JSON values first
            if value.startswith("{") or value.startswith("["):
                try:
                    parsed[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    pass
            
            # Try to parse as numbers
            try:
                if "." in value:
                    parsed[key] = float(value)
                else:
                    parsed[key] = int(value)
                continue
            except ValueError:
                pass
            
            # Keep as string
            parsed[key] = value
        
        return parsed

    def _ack_event(self, event_id: str) -> None:
        """
        Acknowledge successful processing of an event.

        This removes the event from the Pending Entry List (PEL).

        Args:
            event_id: Redis stream event ID to acknowledge
        """
        if not self.redis_client:
            return

        try:
            self.redis_client.xack(
                self.stream_name,
                self.consumer_group,
                event_id
            )
            logger.debug(f"Acknowledged event {event_id}")
            
        except Exception as e:
            logger.warning(f"Failed to acknowledge event {event_id}: {e}")

    def get_pending_events_count(self) -> int:
        """
        Get the count of pending events (not yet acknowledged).

        Returns:
            Number of pending events in the consumer's PEL
        """
        if not self.redis_client:
            return 0

        try:
            # XPENDING returns summary: [lowest_id, highest_id, count, consumers]
            pending_info = self.redis_client.xpending(
                self.stream_name,
                self.consumer_group
            )
            
            if pending_info:
                return pending_info.get("pending", 0)
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to get pending events count: {e}")
            return 0


# ─── Main Entry Point ────────────────────────────────────────────────────

def main():
    """
    Main entry point for running the consumer as a standalone process.
    
    Usage:
        python -m app.consumer.redis_consumer
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    consumer = RedisConsumer()
    consumer.start()


if __name__ == "__main__":
    main()
