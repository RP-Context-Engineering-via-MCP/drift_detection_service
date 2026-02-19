"""
Event consumer package for processing behavior events from Redis Streams.

This package handles:
- Redis stream consumption
- Behavior event processing
- Drift scan job enqueuing
"""

from app.consumer.redis_consumer import RedisConsumer
from app.consumer.behavior_event_handler import BehaviorEventHandler

__all__ = [
    "RedisConsumer",
    "BehaviorEventHandler",
]
