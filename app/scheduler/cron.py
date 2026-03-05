"""
APScheduler configuration for periodic drift detection scans.

This module sets up scheduled jobs for:
- Active user scans (every 24 hours by default)
- Moderate user scans (every 72 hours by default)
- Dead letter queue cleanup (every 10 minutes)

User tiers are determined by last activity:
- Active: Activity within last 7 days
- Moderate: Activity within last 30 days (but not within 7 days)
- Dormant: No activity in 30+ days (not scanned)
"""

import logging
import redis
import time
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.db.connection import get_sync_connection_simple
from app.db.repositories.scan_job_repo import ScanJobRepository
from app.scheduler.dead_letter import reap_dead_letters
from app.utils.time import datetime_to_timestamp_ms
from app.utils.metrics import (
    record_lock_acquisition,
    lock_hold_duration_seconds,
    timer
)

logger = logging.getLogger(__name__)


@contextmanager
def distributed_lock(lock_name: str, timeout: int = 300):
    """
    Context manager for Redis-based distributed lock.
    
    Ensures only one scheduler instance executes a job at a time,
    preventing duplicate job execution across multiple API containers.
    
    Args:
        lock_name: Unique identifier for the lock
        timeout: Lock timeout in seconds (default: 5 minutes)
        
    Yields:
        True if lock acquired, False otherwise
        
    Example:
        >>> with distributed_lock("scan_active_users") as acquired:
        ...     if acquired:
        ...         # Execute job
        ...         pass
    """
    settings = get_settings()
    redis_client = None
    lock_acquired = False
    lock_start_time = time.time()
    
    try:
        # Connect to Redis
        redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5
        )
        
        # Try to acquire lock with SET NX EX (atomic operation)
        lock_key = f"scheduler_lock:{lock_name}"
        lock_acquired = redis_client.set(
            lock_key,
            "locked",
            nx=True,  # Only set if not exists
            ex=timeout  # Expire after timeout
        )
        
        if lock_acquired:
            logger.debug(f"Acquired distributed lock: {lock_name}")
            record_lock_acquisition(lock_name, success=True, blocked=False)
        else:
            logger.debug(f"Lock already held by another instance: {lock_name}")
            record_lock_acquisition(lock_name, success=False, blocked=True)
        
        yield lock_acquired
        
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis for lock: {e}")
        # Fail open: allow job to run if Redis unavailable
        record_lock_acquisition(lock_name, success=True, blocked=False)
        yield True
        
    finally:
        # Record lock hold duration if we acquired it
        if lock_acquired:
            lock_duration = time.time() - lock_start_time
            lock_hold_duration_seconds.labels(lock_name=lock_name).observe(lock_duration)
        
        # Release lock if we acquired it
        if redis_client and lock_acquired:
            try:
                redis_client.delete(f"scheduler_lock:{lock_name}")
                logger.debug(f"Released distributed lock: {lock_name}")
            except Exception as e:
                logger.warning(f"Failed to release lock {lock_name}: {e}")
        
        if redis_client:
            try:
                redis_client.close()
            except Exception:
                pass


def build_scheduler() -> AsyncIOScheduler:
    """
    Build and configure the APScheduler instance with all periodic jobs.

    Returns:
        AsyncIOScheduler: Configured scheduler ready to start
    """
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Add periodic scan jobs
    scheduler.add_job(
        func=scan_active_users,
        trigger=IntervalTrigger(hours=settings.active_user_scan_interval_hours),
        id="scan_active_users",
        name="Scan Active Users",
        replace_existing=True,
        max_instances=1,  # Only one instance at a time
    )
    
    scheduler.add_job(
        func=scan_moderate_users,
        trigger=IntervalTrigger(hours=settings.moderate_user_scan_interval_hours),
        id="scan_moderate_users",
        name="Scan Moderate Users",
        replace_existing=True,
        max_instances=1,
    )
    
    # Add dead letter cleanup job
    scheduler.add_job(
        func=reap_dead_letters,
        trigger=IntervalTrigger(minutes=settings.dead_letter_check_interval_minutes),
        id="reap_dead_letters",
        name="Reap Dead Letters",
        replace_existing=True,
        max_instances=1,
    )
    
    logger.info("APScheduler configured with 3 periodic jobs")
    logger.info(
        f"  - scan_active_users: every {settings.active_user_scan_interval_hours}h"
    )
    logger.info(
        f"  - scan_moderate_users: every {settings.moderate_user_scan_interval_hours}h"
    )
    logger.info(
        f"  - reap_dead_letters: every {settings.dead_letter_check_interval_minutes}min"
    )
    
    return scheduler


async def scan_active_users() -> None:
    """
    Scheduled job: Enqueue drift scans for active users.

    Active users are those with behavior activity within the last N days
    (configured via active_user_days_threshold, default 7 days).
    
    Uses distributed lock to prevent duplicate execution across multiple containers.
    """
    with distributed_lock("scan_active_users", timeout=300) as acquired:
        if not acquired:
            logger.info("Lock not acquired - another instance is scanning active users")
            return
        
        try:
            logger.info("Starting scheduled scan for active users")
            count = await _enqueue_for_tier(tier="active")
            logger.info(f"Enqueued {count} active user scans")
        except Exception as e:
            logger.error(f"Failed to scan active users: {e}", exc_info=True)


async def scan_moderate_users() -> None:
    """
    Scheduled job: Enqueue drift scans for moderate users.

    Moderate users are those with behavior activity within the last N days
    (configured via moderate_user_days_threshold, default 30 days)
    but not within the active threshold.
    
    Uses distributed lock to prevent duplicate execution across multiple containers.
    """
    with distributed_lock("scan_moderate_users", timeout=600) as acquired:
        if not acquired:
            logger.info("Lock not acquired - another instance is scanning moderate users")
            return
        
        try:
            logger.info("Starting scheduled scan for moderate users")
            count = await _enqueue_for_tier(tier="moderate")
            logger.info(f"Enqueued {count} moderate user scans")
        except Exception as e:
            logger.error(f"Failed to scan moderate users: {e}", exc_info=True)


async def _enqueue_for_tier(tier: str) -> int:
    """
    Enqueue scan jobs for users in a specific activity tier.

    Args:
        tier: Either "active" or "moderate"

    Returns:
        Number of jobs enqueued
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    
    # Calculate timestamp thresholds in milliseconds (to match behavior_snapshots table)
    active_since = datetime_to_timestamp_ms(
        now - timedelta(days=settings.active_user_days_threshold)
    )
    moderate_since = datetime_to_timestamp_ms(
        now - timedelta(days=settings.moderate_user_days_threshold)
    )
    
    # Get database connection and repository
    connection = get_sync_connection_simple()
    repo = ScanJobRepository(connection)
    
    try:
        # Get scannable users grouped by tier
        users = repo.get_all_scannable_users(active_since, moderate_since)
        
        # Get users for this tier
        user_ids = users.get(tier, [])
        
        if not user_ids:
            logger.debug(f"No {tier} users to scan")
            return 0
        
        # Enqueue jobs for each user
        enqueued = 0
        for user_id in user_ids:
            # Check if already has pending job
            if repo.has_pending_job(user_id):
                logger.debug(f"Skipping {user_id} - already has pending job")
                continue
            
            # Check cooldown
            last_scan = repo.get_last_completed_scan(user_id)
            if last_scan:
                elapsed = int(now.timestamp()) - last_scan
                if elapsed < settings.scan_cooldown_seconds:
                    logger.debug(
                        f"Skipping {user_id} - cooldown active "
                        f"({elapsed}s < {settings.scan_cooldown_seconds}s)"
                    )
                    continue
            
            # Enqueue the job
            job_id = repo.enqueue(
                user_id=user_id,
                trigger_event=f"scheduled_{tier}",
                priority="NORMAL"
            )
            enqueued += 1
            logger.debug(f"Enqueued {tier} scan for {user_id}: {job_id}")
        
        # Commit transaction
        connection.commit()
        
        return enqueued
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Failed to enqueue {tier} users: {e}", exc_info=True)
        raise
    finally:
        connection.close()
