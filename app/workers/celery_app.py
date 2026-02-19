"""
Celery Application Configuration.

Configures Celery for background task processing with Redis as broker
and result backend.

Usage:
    # Start a Celery worker
    celery -A app.workers.celery_app worker --loglevel=info
    
    # Start with multiple workers
    celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
    
    # Monitor with Flower
    celery -A app.workers.celery_app flower
"""

import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure

from app.config import get_settings

logger = logging.getLogger(__name__)

# Get application settings
settings = get_settings()

# ─── Create Celery Application ───────────────────────────────────────────

celery_app = Celery(
    "drift_detection_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.scan_worker"]  # Auto-discover tasks
)

# ─── Celery Configuration ────────────────────────────────────────────────

celery_app.conf.update(
    # Serialization
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,
    
    # Task execution
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    
    # Worker settings
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    worker_max_tasks_per_child=settings.celery_worker_max_tasks_per_child,
    
    # Result expiration
    result_expires=3600,  # Results expire after 1 hour
    
    # Task routing (optional - for future scaling)
    task_routes={
        "app.workers.scan_worker.*": {"queue": "drift_scans"},
    },
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Logging
    worker_hijack_root_logger=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

# ─── Task Event Hooks ────────────────────────────────────────────────────

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log when a task starts executing."""
    logger.info(f"Task {task.name}[{task_id}] starting")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, **extra):
    """Log when a task completes successfully."""
    logger.info(f"Task {task.name}[{task_id}] completed successfully")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **extra):
    """Log when a task fails."""
    logger.error(
        f"Task {sender.name}[{task_id}] failed with exception: {exception}",
        exc_info=einfo
    )


# ─── Utility Functions ───────────────────────────────────────────────────

def get_celery_app() -> Celery:
    """
    Get the Celery application instance.
    
    Returns:
        Celery application
    """
    return celery_app


def inspect_workers():
    """
    Inspect active Celery workers.
    
    Returns:
        Dictionary with worker statistics
    """
    inspector = celery_app.control.inspect()
    
    return {
        "active": inspector.active(),
        "scheduled": inspector.scheduled(),
        "reserved": inspector.reserved(),
        "stats": inspector.stats(),
    }


def purge_all_tasks():
    """
    Purge all pending tasks from the queue.
    
    WARNING: This will delete all queued tasks!
    
    Returns:
        Number of tasks purged
    """
    return celery_app.control.purge()


# ─── Health Check ────────────────────────────────────────────────────────

def check_celery_health() -> dict:
    """
    Check Celery broker and workers health.
    
    Returns:
        Dictionary with health status
    """
    try:
        # Check broker connection
        celery_app.connection().ensure_connection(max_retries=3)
        broker_ok = True
    except Exception as e:
        logger.error(f"Celery broker connection failed: {e}")
        broker_ok = False
    
    try:
        # Check workers
        inspector = celery_app.control.inspect()
        active_workers = inspector.active()
        workers_ok = active_workers is not None and len(active_workers) > 0
        worker_count = len(active_workers) if active_workers else 0
    except Exception as e:
        logger.error(f"Failed to inspect workers: {e}")
        workers_ok = False
        worker_count = 0
    
    return {
        "broker_connected": broker_ok,
        "workers_available": workers_ok,
        "worker_count": worker_count,
        "healthy": broker_ok and workers_ok
    }


if __name__ == "__main__":
    """
    Run worker from command line.
    
    Usage:
        python -m app.workers.celery_app
    """
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=2",
    ])
