"""
API Request/Response Models

Pydantic models for API endpoints
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class DriftTypeAPI(str, Enum):
    """Drift types for API responses"""
    TOPIC_EMERGENCE = "TOPIC_EMERGENCE"
    TOPIC_ABANDONMENT = "TOPIC_ABANDONMENT"
    PREFERENCE_REVERSAL = "PREFERENCE_REVERSAL"
    INTENSITY_SHIFT = "INTENSITY_SHIFT"
    CONTEXT_EXPANSION = "CONTEXT_EXPANSION"
    CONTEXT_CONTRACTION = "CONTEXT_CONTRACTION"


class DriftSeverityAPI(str, Enum):
    """Drift severity levels for API responses"""
    NO_DRIFT = "NO_DRIFT"
    WEAK_DRIFT = "WEAK_DRIFT"
    MODERATE_DRIFT = "MODERATE_DRIFT"
    STRONG_DRIFT = "STRONG_DRIFT"


# ============================================================================
# Request Models
# ============================================================================

class DetectDriftRequest(BaseModel):
    """Request to detect drift for a user"""
    user_id: str = Field(..., description="User ID to detect drift for")
    force: bool = Field(
        False,
        description="Force detection even if in cooldown period"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "force": False
            }
        }


class GetDriftEventsRequest(BaseModel):
    """Query parameters for getting drift events"""
    drift_type: Optional[DriftTypeAPI] = Field(
        None,
        description="Filter by drift type"
    )
    severity: Optional[DriftSeverityAPI] = Field(
        None,
        description="Filter by severity"
    )
    start_date: Optional[datetime] = Field(
        None,
        description="Filter events detected after this date"
    )
    end_date: Optional[datetime] = Field(
        None,
        description="Filter events detected before this date"
    )
    limit: int = Field(
        50,
        ge=1,
        le=500,
        description="Maximum number of events to return"
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of events to skip"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "drift_type": "TOPIC_EMERGENCE",
                "severity": "STRONG_DRIFT",
                "limit": 10,
                "offset": 0
            }
        }


class AcknowledgeDriftRequest(BaseModel):
    """Request to acknowledge a drift event"""
    drift_event_id: str = Field(..., description="Drift event ID to acknowledge")


# ============================================================================
# Response Models
# ============================================================================

class DriftEventResponse(BaseModel):
    """Response model for a drift event"""
    drift_event_id: str
    user_id: str
    drift_type: DriftTypeAPI
    drift_score: float = Field(..., ge=0.0, le=1.0)
    severity: DriftSeverityAPI
    affected_targets: List[str]
    evidence: Dict[str, Any]
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    # Time windows
    reference_window_start: int
    reference_window_end: int
    current_window_start: int
    current_window_end: int
    
    # Metadata
    detected_at: int
    acknowledged_at: Optional[int] = None
    behavior_ref_ids: List[str]
    conflict_ref_ids: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "drift_event_id": "drift_abc123",
                "user_id": "user_123",
                "drift_type": "TOPIC_EMERGENCE",
                "drift_score": 0.85,
                "severity": "STRONG_DRIFT",
                "affected_targets": ["pytorch", "tensorflow"],
                "evidence": {
                    "cluster": ["pytorch", "tensorflow"],
                    "cluster_size": 2,
                    "is_domain_emergence": True
                },
                "confidence": 0.9,
                "reference_window_start": 1704067200,
                "reference_window_end": 1706745600,
                "current_window_start": 1707350400,
                "current_window_end": 1709942400,
                "detected_at": 1709942400,
                "acknowledged_at": None,
                "behavior_ref_ids": [],
                "conflict_ref_ids": []
            }
        }


class DetectDriftResponse(BaseModel):
    """Response from drift detection"""
    user_id: str
    detected_events: List[DriftEventResponse]
    detection_timestamp: int
    total_events: int
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "detected_events": [],
                "detection_timestamp": 1709942400,
                "total_events": 2,
                "message": "Detected 2 drift event(s)"
            }
        }


class GetDriftEventsResponse(BaseModel):
    """Response for listing drift events"""
    user_id: str
    events: List[DriftEventResponse]
    total: int
    limit: int
    offset: int

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "events": [],
                "total": 5,
                "limit": 50,
                "offset": 0
            }
        }


class AcknowledgeDriftResponse(BaseModel):
    """Response from acknowledging a drift event"""
    drift_event_id: str
    acknowledged_at: int
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "drift_event_id": "drift_abc123",
                "acknowledged_at": 1709942400,
                "message": "Drift event acknowledged successfully"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    database: str
    timestamp: int

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "database": "connected",
                "timestamp": 1709942400
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
    timestamp: int

    class Config:
        json_schema_extra = {
            "example": {
                "error": "User not found",
                "detail": "User user_123 has no data in the system",
                "timestamp": 1709942400
            }
        }
