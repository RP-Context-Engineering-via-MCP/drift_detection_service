"""
Drift Detection Modules

This package contains individual detector implementations for each drift type:
- PreferenceReversalDetector
- TopicAbandonmentDetector
- TopicEmergenceDetector
- IntensityShiftDetector
- ContextShiftDetector

Each detector extends BaseDetector and operates on BehaviorSnapshot pairs.
"""

from app.detectors.base import BaseDetector

__all__ = ["BaseDetector"]
