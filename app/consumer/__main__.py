"""
Entry point for running the Redis consumer as a module.

Usage:
    python -m app.consumer
"""

from app.consumer.redis_consumer import main

if __name__ == "__main__":
    main()
