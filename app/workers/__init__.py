"""
Workers package for background task processing.

This package contains:
- Celery application configuration
- Worker tasks for drift detection
"""

from app.workers.celery_app import celery_app

__all__ = [
    "celery_app",
]
