"""
Scheduler package for periodic drift detection tasks.

This package implements APScheduler jobs for:
- Periodic scans of active users (every 24 hours)
- Periodic scans of moderate users (every 72 hours)
- Dead letter queue handling (every 10 minutes)
"""

from app.scheduler.cron import build_scheduler

__all__ = ["build_scheduler"]
