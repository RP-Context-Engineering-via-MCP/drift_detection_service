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
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.db.connection import get_sync_connection_simple
from app.db.repositories.scan_job_repo import ScanJobRepository
from app.scheduler.dead_letter import reap_dead_letters

logger = logging.getLogger(__name__)


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
    """
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
    """
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
    
    # Calculate timestamp thresholds
    active_since = int(
        (now - timedelta(days=settings.active_user_days_threshold)).timestamp()
    )
    moderate_since = int(
        (now - timedelta(days=settings.moderate_user_days_threshold)).timestamp()
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
