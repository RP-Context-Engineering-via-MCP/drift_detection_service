"""
Pipeline package for drift detection data flow.

Contains components for processing and publishing drift detection results.
"""

from app.pipeline.drift_event_writer import DriftEventWriter

__all__ = [
    "DriftEventWriter",
]
