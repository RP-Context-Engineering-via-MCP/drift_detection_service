"""
Dead Letter Queue handler for Redis Streams.

This module handles messages that fail processing repeatedly. Messages that:
- Have been idle in the Pending Entries List (PEL) for > 5 minutes
- Have been delivered 3+ times without acknowledgment

These messages are moved to a dead letter stream for manual inspection
and debugging.
"""

import logging
import asyncio
from datetime import datetime, timezone

import redis
import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)


async def reap_dead_letters() -> int:
    """
    Reap messages stuck in the Pending Entries List (PEL).

    Messages are considered "dead" if:
    1. They've been idle for more than 5 minutes (configurable)
    2. They've been delivered 3+ times (configurable)

    Dead messages are:
    1. Moved to a dead-letter stream for inspection
    2. Acknowledged in the original stream
    3. Logged for alerting/monitoring

    Returns:
        Number of messages moved to dead letter queue
    """
    settings = get_settings()
    redis_client = None
    
    try:
        # Connect to Redis
        redis_client = await asyncio.wait_for(
            aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2
            ),
            timeout=3.0
        )
        
        # Get pending entries from the behavior events stream
        pending_entries = await redis_client.xpending_range(
            name=settings.redis_stream_behavior_events,
            groupname=settings.redis_consumer_group,
            min="-",
            max="+",
            count=100  # Process up to 100 at a time
        )
        
        if not pending_entries:
            logger.debug("No pending entries in PEL")
            return 0
        
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        dead_count = 0
        
        for entry in pending_entries:
            message_id = entry["message_id"]
            idle_ms = entry["time_since_delivered"]
            delivery_count = entry["times_delivered"]
            
            # Check if message is dead
            is_dead = (
                idle_ms > settings.dead_letter_idle_threshold_ms
                and delivery_count >= settings.dead_letter_max_delivery_attempts
            )
            
            if not is_dead:
                continue
            
            logger.warning(
                f"Found dead letter: {message_id} "
                f"(idle: {idle_ms}ms, attempts: {delivery_count})"
            )
            
            try:
                # Claim the message
                claimed = await redis_client.xautoclaim(
                    name=settings.redis_stream_behavior_events,
                    groupname=settings.redis_consumer_group,
                    consumername=settings.redis_consumer_name,
                    min_idle_time=settings.dead_letter_idle_threshold_ms,
                    start_id=message_id,
                    count=1
                )
                
                # Extract message data
                # xautoclaim returns: (next_id, [(message_id, data)], deleted_ids)
                messages = claimed[1] if len(claimed) > 1 else []
                
                if not messages:
                    logger.warning(f"Could not claim message {message_id}")
                    continue
                
                msg_id, msg_data = messages[0]
                
                # Add metadata about the failure
                dead_letter_data = {
                    **msg_data,
                    "failed_at": str(now_ms),
                    "delivery_attempts": str(delivery_count),
                    "idle_time_ms": str(idle_ms),
                    "original_stream": settings.redis_stream_behavior_events,
                }
                
                # Move to dead letter stream
                dead_letter_stream = f"{settings.redis_stream_behavior_events}.deadletter"
                await redis_client.xadd(
                    name=dead_letter_stream,
                    fields=dead_letter_data,
                    maxlen=1000  # Keep last 1000 dead letters
                )
                
                # Acknowledge the message in the original stream
                await redis_client.xack(
                    settings.redis_stream_behavior_events,
                    settings.redis_consumer_group,
                    msg_id
                )
                
                dead_count += 1
                
                logger.info(
                    f"Moved message {msg_id} to dead letter queue "
                    f"(stream: {dead_letter_stream})"
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to process dead letter {message_id}: {e}",
                    exc_info=True
                )
                continue
        
        if dead_count > 0:
            logger.warning(
                f"Moved {dead_count} messages to dead letter queue. "
                f"Manual inspection required!"
            )
        
        return dead_count
    
    except (redis.exceptions.ConnectionError, AttributeError) as e:
        logger.error(f"Redis connection error in dead letter handler: {e}")
        # Don't raise - scheduler should continue
        return 0
    
    except Exception as e:
        logger.error(f"Unexpected error in dead letter handler: {e}", exc_info=True)
        # Don't raise - scheduler should continue
        return 0
    
    finally:
        if redis_client:
            try:
                await redis_client.close()
            except:
                pass  # Ignore errors during cleanup


async def get_dead_letter_count() -> int:
    """
    Get the count of messages in the dead letter queue.

    Returns:
        Number of messages in the dead letter stream
    """
    settings = get_settings()
    redis_client = None
    
    try:
        redis_client = await asyncio.wait_for(
            aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2
            ),
            timeout=3.0
        )
        
        dead_letter_stream = f"{settings.redis_stream_behavior_events}.deadletter"
        info = await redis_client.xinfo_stream(dead_letter_stream)
        return info.get("length", 0)
    
    except redis.exceptions.ResponseError:
        # Stream doesn't exist yet
        return 0
    
    except Exception as e:
        logger.error(f"Failed to get dead letter count: {e}")
        return 0
    
    finally:
        if redis_client:
            try:
                await redis_client.close()
            except:
                pass  # Ignore errors during cleanup


async def inspect_dead_letters(limit: int = 10) -> list:
    """
    Inspect recent dead letter messages for debugging.

    Args:
        limit: Maximum number of messages to retrieve

    Returns:
        List of dead letter message dictionaries
    """
    settings = get_settings()
    redis_client = None
    
    try:
        redis_client = await asyncio.wait_for(
            aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2
            ),
            timeout=3.0
        )
        
        dead_letter_stream = f"{settings.redis_stream_behavior_events}.deadletter"
        messages = await redis_client.xrevrange(
            name=dead_letter_stream,
            count=limit
        )
        
        result = []
        for msg_id, msg_data in messages:
            result.append({
                "message_id": msg_id,
                "data": msg_data
            })
        
        return result
    
    except redis.exceptions.ResponseError:
        # Stream doesn't exist yet
        return []
    
    except Exception as e:
        logger.error(f"Failed to inspect dead letters: {e}")
        return []
    
    finally:
        if redis_client:
            try:
                await redis_client.close()
            except:
                pass  # Ignore errors during cleanup
