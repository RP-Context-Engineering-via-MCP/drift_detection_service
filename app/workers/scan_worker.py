"""
Scan Worker - Celery tasks for drift detection.

This module contains Celery tasks that:
1. Process drift scan jobs from the queue
2. Run the drift detection pipeline
3. Update job status and handle failures
4. Publish results to Redis Streams

Usage:
    # Start worker
    celery -A app.workers.celery_app worker --loglevel=info
    
    # Enqueue a scan manually (for testing)
    from app.workers.scan_worker import run_drift_scan
    result = run_drift_scan.delay(job_id="uuid-here")
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.workers.celery_app import celery_app
from app.db.connection import get_sync_connection
from app.db.repositories.scan_job_repo import ScanJobRepository
from app.core.drift_detector import DriftDetector
from app.pipeline.drift_event_writer import DriftEventWriter
from app.utils.time import now

logger = logging.getLogger(__name__)


class ScanTask(Task):
    """
    Custom Celery task class for drift scans.
    
    Provides retry logic and error handling.
    """
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True


@celery_app.task(
    bind=True,
    base=ScanTask,
    name="app.workers.scan_worker.run_drift_scan",
    acks_late=True,  # Only acknowledge after task completion
    reject_on_worker_lost=True,
)
def run_drift_scan(self, job_id: str) -> Dict[str, Any]:
    """
    Execute drift detection for a specific scan job.
    
    This is the main Celery task that processes drift scan jobs from
    the drift_scan_jobs table.
    
    Workflow:
    1. Retrieve job from database
    2. Validate job status (must be PENDING)
    3. Update status to RUNNING
    4. Execute drift detection pipeline
    5. Write events to database and publish to Redis
    6. Update job status to DONE
    7. Handle failures and update status to FAILED
    
    Args:
        job_id: UUID of the scan job to process
        
    Returns:
        Dictionary with scan results:
        {
            "job_id": "uuid",
            "user_id": "user_123",
            "status": "DONE",
            "events_detected": 3,
            "execution_time_seconds": 12.5
        }
        
    Raises:
        ValueError: If job_id is invalid or job not found
        RuntimeError: If drift detection fails
    """
    start_time = now()
    
    logger.info(f"Starting drift scan for job {job_id}")
    
    try:
        # Connect to database
        with get_sync_connection() as conn:
            scan_repo = ScanJobRepository(conn)
            
            # Retrieve job
            job = scan_repo.get_job_by_id(job_id)
            
            if not job:
                error_msg = f"Job {job_id} not found"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            user_id = job["user_id"]
            trigger_event = job["trigger_event"]
            
            # Validate job status
            if job["status"] != "PENDING":
                logger.warning(
                    f"Job {job_id} has status {job['status']}, expected PENDING. "
                    "Skipping."
                )
                return {
                    "job_id": job_id,
                    "user_id": user_id,
                    "status": job["status"],
                    "skipped": True
                }
            
            # Update status to RUNNING
            scan_repo.update_status(job_id, "RUNNING")
            logger.info(f"Job {job_id} status updated to RUNNING")
            
        # Execute drift detection pipeline (outside transaction for performance)
        try:
            logger.info(f"Running drift detection for user {user_id}")
            
            # Initialize drift detector
            detector = DriftDetector()
            
            # Run detection
            events = detector.detect_drift(user_id)
            
            logger.info(
                f"Drift detection completed for user {user_id}: "
                f"{len(events)} event(s) detected"
            )
            
            # Update job status to DONE
            with get_sync_connection() as conn:
                scan_repo = ScanJobRepository(conn)
                scan_repo.update_status(job_id, "DONE")
            
            end_time = now()
            execution_time = end_time - start_time
            
            logger.info(
                f"Job {job_id} completed successfully in {execution_time}s "
                f"({len(events)} events)"
            )
            
            return {
                "job_id": job_id,
                "user_id": user_id,
                "status": "DONE",
                "trigger_event": trigger_event,
                "events_detected": len(events),
                "execution_time_seconds": execution_time,
                "completed_at": end_time
            }
            
        except SoftTimeLimitExceeded:
            error_msg = f"Task exceeded soft time limit for job {job_id}"
            logger.error(error_msg)
            
            with get_sync_connection() as conn:
                scan_repo = ScanJobRepository(conn)
                scan_repo.update_status(job_id, "FAILED", error_message=error_msg)
            
            raise
            
        except Exception as e:
            error_msg = f"Drift detection failed for user {user_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Update job status to FAILED
            with get_sync_connection() as conn:
                scan_repo = ScanJobRepository(conn)
                scan_repo.update_status(
                    job_id,
                    "FAILED",
                    error_message=error_msg[:500]  # Truncate long errors
                )
            
            # Reraise to trigger Celery retry
            raise RuntimeError(error_msg) from e
    
    except Exception as e:
        logger.error(f"Fatal error processing job {job_id}: {e}", exc_info=True)
        
        # Try to update job status
        try:
            with get_sync_connection() as conn:
                scan_repo = ScanJobRepository(conn)
                scan_repo.update_status(
                    job_id,
                    "FAILED",
                    error_message=str(e)[:500]
                )
        except Exception as db_error:
            logger.error(f"Failed to update job status: {db_error}")
        
        raise


@celery_app.task(name="app.workers.scan_worker.process_pending_jobs")
def process_pending_jobs(limit: int = 10) -> Dict[str, Any]:
    """
    Process multiple pending scan jobs from the queue.
    
    This task fetches pending jobs and enqueues individual run_drift_scan
    tasks for each job. Useful for batch processing or scheduled execution.
    
    Args:
        limit: Maximum number of jobs to process
        
    Returns:
        Dictionary with processing statistics
    """
    logger.info(f"Processing up to {limit} pending scan jobs")
    
    with get_sync_connection() as conn:
        scan_repo = ScanJobRepository(conn)
        
        # Get pending jobs
        pending_jobs = scan_repo.get_pending_jobs(limit=limit)
        
        if not pending_jobs:
            logger.info("No pending jobs found")
            return {
                "jobs_found": 0,
                "jobs_enqueued": 0
            }
        
        logger.info(f"Found {len(pending_jobs)} pending job(s)")
        
        # Enqueue individual scan tasks
        enqueued_count = 0
        for job in pending_jobs:
            try:
                run_drift_scan.delay(job["job_id"])
                enqueued_count += 1
                logger.debug(f"Enqueued scan task for job {job['job_id']}")
            except Exception as e:
                logger.error(
                    f"Failed to enqueue job {job['job_id']}: {e}",
                    exc_info=True
                )
        
        logger.info(f"Enqueued {enqueued_count} scan task(s)")
        
        return {
            "jobs_found": len(pending_jobs),
            "jobs_enqueued": enqueued_count,
            "timestamp": now()
        }


@celery_app.task(name="app.workers.scan_worker.scan_user")
def scan_user(user_id: str, priority: str = "NORMAL") -> Dict[str, Any]:
    """
    Enqueue a drift scan for a specific user.
    
    This is a convenience task for manually triggering scans or for
    use by scheduled jobs.
    
    Args:
        user_id: User ID to scan
        priority: Job priority (NORMAL, HIGH, LOW)
        
    Returns:
        Dictionary with job information
    """
    logger.info(f"Enqueuing drift scan for user {user_id} (priority: {priority})")
    
    with get_sync_connection() as conn:
        scan_repo = ScanJobRepository(conn)
        
        # Check if user already has a pending job
        if scan_repo.has_pending_job(user_id):
            logger.info(f"User {user_id} already has a pending scan job, skipping")
            return {
                "user_id": user_id,
                "status": "skipped",
                "reason": "pending_job_exists"
            }
        
        # Enqueue new job
        job_id = scan_repo.enqueue(
            user_id=user_id,
            trigger_event="manual_trigger",
            priority=priority
        )
        
        # Trigger the scan task
        run_drift_scan.delay(job_id)
        
        logger.info(f"Enqueued scan job {job_id} for user {user_id}")
        
        return {
            "user_id": user_id,
            "job_id": job_id,
            "priority": priority,
            "status": "enqueued",
            "timestamp": now()
        }


@celery_app.task(name="app.workers.scan_worker.get_scan_statistics")
def get_scan_statistics() -> Dict[str, Any]:
    """
    Get statistics about scan jobs.
    
    Returns:
        Dictionary with job statistics by status
    """
    with get_sync_connection() as conn:
        scan_repo = ScanJobRepository(conn)
        stats = scan_repo.count_jobs_by_status()
        
        logger.info(f"Scan job statistics: {stats}")
        
        return {
            "statistics": stats,
            "timestamp": now()
        }


# ─── Task Monitoring Utilities ──────────────────────────────────────────

def inspect_running_scans() -> Dict[str, Any]:
    """
    Inspect currently running scan tasks.
    
    Returns:
        Dictionary with information about active scan tasks
    """
    from app.workers.celery_app import celery_app
    
    inspector = celery_app.control.inspect()
    active_tasks = inspector.active()
    
    if not active_tasks:
        return {"active_scans": 0, "tasks": []}
    
    scan_tasks = []
    for worker, tasks in active_tasks.items():
        for task in tasks:
            if task["name"] == "app.workers.scan_worker.run_drift_scan":
                scan_tasks.append({
                    "worker": worker,
                    "task_id": task["id"],
                    "job_id": task["args"][0] if task["args"] else None,
                    "time_start": task.get("time_start")
                })
    
    return {
        "active_scans": len(scan_tasks),
        "tasks": scan_tasks
    }
