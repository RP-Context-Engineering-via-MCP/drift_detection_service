"""
Drift detection result models.

DriftSignal: Output from individual detectors
DriftEvent: What gets written to the database
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
import uuid


class DriftType(str, Enum):
    """Types of behavioral drift that can be detected."""
    
    TOPIC_EMERGENCE = "TOPIC_EMERGENCE"
    TOPIC_ABANDONMENT = "TOPIC_ABANDONMENT"
    PREFERENCE_REVERSAL = "PREFERENCE_REVERSAL"
    INTENSITY_SHIFT = "INTENSITY_SHIFT"
    CONTEXT_EXPANSION = "CONTEXT_EXPANSION"
    CONTEXT_CONTRACTION = "CONTEXT_CONTRACTION"


class DriftSeverity(str, Enum):
    """Severity levels for drift events based on drift_score."""
    
    NO_DRIFT = "NO_DRIFT"          # 0.0 - 0.3
    WEAK_DRIFT = "WEAK_DRIFT"      # 0.3 - 0.6
    MODERATE_DRIFT = "MODERATE_DRIFT"  # 0.6 - 0.8
    STRONG_DRIFT = "STRONG_DRIFT"  # 0.8 - 1.0


@dataclass
class DriftSignal:
    """
    Output from a single detector module.
    
    Represents a detected drift pattern with a normalized score
    and supporting evidence.
    """
    
    drift_type: DriftType
    drift_score: float  # 0.0 (no drift) → 1.0 (strong drift)
    affected_targets: List[str]
    evidence: Dict[str, Any]  # Raw data that triggered this signal
    confidence: float  # How confident we are this is real drift (0.0-1.0)
    
    def __post_init__(self):
        """Validate field values."""
        # Validate drift_score
        if not 0.0 <= self.drift_score <= 1.0:
            raise ValueError(f"drift_score must be between 0.0 and 1.0, got {self.drift_score}")
        
        # Validate confidence
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")
        
        # Ensure affected_targets is a list
        if not isinstance(self.affected_targets, list):
            raise TypeError(f"affected_targets must be a list, got {type(self.affected_targets)}")
        
        # Convert drift_type to enum if it's a string
        if isinstance(self.drift_type, str):
            self.drift_type = DriftType(self.drift_type)
    
    @property
    def severity(self) -> DriftSeverity:
        """
        Calculate severity based on drift_score.
        
        Returns:
            DriftSeverity enum value
        """
        if self.drift_score >= 0.8:
            return DriftSeverity.STRONG_DRIFT
        elif self.drift_score >= 0.6:
            return DriftSeverity.MODERATE_DRIFT
        elif self.drift_score >= 0.3:
            return DriftSeverity.WEAK_DRIFT
        else:
            return DriftSeverity.NO_DRIFT
    
    @property
    def is_actionable(self) -> bool:
        """
        Check if this signal is strong enough to act upon.
        
        Returns:
            True if severity is MODERATE or STRONG
        """
        return self.severity in [DriftSeverity.MODERATE_DRIFT, DriftSeverity.STRONG_DRIFT]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "drift_type": self.drift_type.value,
            "drift_score": self.drift_score,
            "affected_targets": self.affected_targets,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "severity": self.severity.value,
        }
    
    def __repr__(self) -> str:
        targets_str = ", ".join(self.affected_targets[:3])
        if len(self.affected_targets) > 3:
            targets_str += f", ... ({len(self.affected_targets)} total)"
        
        return (
            f"DriftSignal(type={self.drift_type.value}, "
            f"score={self.drift_score:.3f}, "
            f"severity={self.severity.value}, "
            f"targets=[{targets_str}])"
        )


@dataclass
class DriftEvent:
    """
    Drift event that gets written to the database.
    
    Extends DriftSignal with metadata about when and how it was detected.
    """
    
    # Core drift information (from DriftSignal) - all required fields first
    drift_type: DriftType
    drift_score: float
    confidence: float
    severity: DriftSeverity
    affected_targets: List[str]
    evidence: Dict[str, Any]
    
    # User and identification
    user_id: str
    
    # Time windows used for detection - all required
    reference_window_start: int  # unix timestamp
    reference_window_end: int
    current_window_start: int
    current_window_end: int
    
    # Detection metadata - required
    detected_at: int  # unix timestamp when drift was detected
    
    # Optional fields with defaults come last
    drift_event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    acknowledged_at: Optional[int] = None  # unix timestamp when acknowledged
    
    # References to source data (IDs only, no foreign keys)
    behavior_ref_ids: List[str] = field(default_factory=list)
    conflict_ref_ids: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate and convert fields."""
        # Convert string enums to actual enums
        if isinstance(self.drift_type, str):
            self.drift_type = DriftType(self.drift_type)
        
        if isinstance(self.severity, str):
            self.severity = DriftSeverity(self.severity)
        
        # Validate score and confidence
        if not 0.0 <= self.drift_score <= 1.0:
            raise ValueError(f"drift_score must be between 0.0 and 1.0, got {self.drift_score}")
        
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")
    
    @classmethod
    def from_signal(
        cls,
        signal: DriftSignal,
        user_id: str,
        reference_window_start: int,
        reference_window_end: int,
        current_window_start: int,
        current_window_end: int,
        detected_at: int,
        behavior_ref_ids: Optional[List[str]] = None,
        conflict_ref_ids: Optional[List[str]] = None,
    ) -> "DriftEvent":
        """
        Create a DriftEvent from a DriftSignal.
        
        Args:
            signal: The originating drift signal
            user_id: User ID this drift applies to
            reference_window_start: Reference window start timestamp
            reference_window_end: Reference window end timestamp
            current_window_start: Current window start timestamp
            current_window_end: Current window end timestamp
            detected_at: When the drift was detected
            behavior_ref_ids: List of related behavior IDs
            conflict_ref_ids: List of related conflict IDs
            
        Returns:
            DriftEvent instance
        """
        return cls(
            drift_type=signal.drift_type,
            drift_score=signal.drift_score,
            confidence=signal.confidence,
            severity=signal.severity,
            affected_targets=signal.affected_targets.copy(),
            evidence=signal.evidence.copy(),
            user_id=user_id,
            reference_window_start=reference_window_start,
            reference_window_end=reference_window_end,
            current_window_start=current_window_start,
            current_window_end=current_window_end,
            detected_at=detected_at,
            behavior_ref_ids=behavior_ref_ids or [],
            conflict_ref_ids=conflict_ref_ids or [],
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "drift_event_id": self.drift_event_id,
            "user_id": self.user_id,
            "drift_type": self.drift_type.value,
            "drift_score": self.drift_score,
            "confidence": self.confidence,
            "severity": self.severity.value,
            "affected_targets": self.affected_targets,
            "evidence": self.evidence,
            "reference_window_start": self.reference_window_start,
            "reference_window_end": self.reference_window_end,
            "current_window_start": self.current_window_start,
            "current_window_end": self.current_window_end,
            "detected_at": self.detected_at,
            "acknowledged_at": self.acknowledged_at,
            "behavior_ref_ids": self.behavior_ref_ids,
            "conflict_ref_ids": self.conflict_ref_ids,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DriftEvent":
        """Create DriftEvent from dictionary (e.g., database row)."""
        return cls(
            drift_event_id=data["drift_event_id"],
            user_id=data["user_id"],
            drift_type=DriftType(data["drift_type"]),
            drift_score=float(data["drift_score"]),
            confidence=float(data["confidence"]),
            severity=DriftSeverity(data["severity"]),
            affected_targets=data["affected_targets"],
            evidence=data["evidence"],
            reference_window_start=int(data["reference_window_start"]),
            reference_window_end=int(data["reference_window_end"]),
            current_window_start=int(data["current_window_start"]),
            current_window_end=int(data["current_window_end"]),
            detected_at=int(data["detected_at"]),
            acknowledged_at=int(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            behavior_ref_ids=data.get("behavior_ref_ids", []),
            conflict_ref_ids=data.get("conflict_ref_ids", []),
        )
    
    @property
    def detected_datetime(self) -> datetime:
        """Get detected_at as datetime object."""
        return datetime.fromtimestamp(self.detected_at)
    
    @property
    def is_acknowledged(self) -> bool:
        """Check if this drift event has been acknowledged."""
        return self.acknowledged_at is not None
    
    def acknowledge(self, timestamp: Optional[int] = None) -> None:
        """
        Mark this drift event as acknowledged.
        
        Args:
            timestamp: Unix timestamp for acknowledgment (defaults to now)
        """
        if timestamp is None:
            timestamp = int(datetime.now().timestamp())
        self.acknowledged_at = timestamp
    
    def __repr__(self) -> str:
        return (
            f"DriftEvent(id={self.drift_event_id[:8]}..., "
            f"user={self.user_id}, "
            f"type={self.drift_type.value}, "
            f"score={self.drift_score:.3f}, "
            f"severity={self.severity.value})"
        )
