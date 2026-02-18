"""
API Routes

REST API endpoints for drift detection service
"""

from typing import List
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, Query, Path, Body
from psycopg2.extensions import connection as Connection

from api.models import (
    DetectDriftRequest,
    DetectDriftResponse,
    GetDriftEventsResponse,
    DriftEventResponse,
    AcknowledgeDriftResponse,
    HealthResponse,
    DriftTypeAPI,
    DriftSeverityAPI
)
from api.dependencies import get_drift_detector, get_db_connection, get_api_settings
from api.errors import (
    InsufficientDataError,
    UserNotFoundError,
    DriftEventNotFoundError,
    DatabaseError
)
from app.core.drift_detector import DriftDetector
from app.db.repositories.drift_event_repo import DriftEventRepository
from app.db.repositories.behavior_repo import BehaviorRepository
from app.db.connection import check_database_health, now
from app.config import Settings
from app.models.drift import DriftType, DriftSeverity

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Health Check
# ============================================================================

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API and database are healthy"
)
async def health_check(
    settings: Settings = Depends(get_api_settings)
) -> HealthResponse:
    """Health check endpoint"""
    try:
        db_status = "connected" if check_database_health() else "disconnected"
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_status = "error"
    
    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        version="1.0.0",
        database=db_status,
        timestamp=now()
    )


# ============================================================================
# Drift Detection
# ============================================================================

@router.post(
    "/detect/{user_id}",
    response_model=DetectDriftResponse,
    summary="Detect drift for user",
    description="Run drift detection for a specific user",
    status_code=200
)
async def detect_drift(
    user_id: str = Path(..., description="User ID to detect drift for"),
    force: bool = Query(False, description="Force detection even if in cooldown"),
    detector: DriftDetector = Depends(get_drift_detector),
    db: Connection = Depends(get_db_connection)
) -> DetectDriftResponse:
    """
    Detect behavioral drift for a user
    
    This endpoint runs the drift detection pipeline for the specified user.
    It analyzes behavior patterns and returns detected drift events.
    
    - **user_id**: The user to analyze
    - **force**: Skip cooldown period (default: False)
    """
    logger.info(f"Drift detection requested for user: {user_id}, force={force}")
    
    # Check if user has data
    behavior_repo = BehaviorRepository(db)
    behavior_count = behavior_repo.count_active_behaviors(user_id)
    
    if behavior_count == 0:
        raise UserNotFoundError(user_id)
    
    # Run detection
    try:
        # Note: force parameter would need to be implemented in DriftDetector
        # For now, it always respects cooldown
        events = detector.detect_drift(user_id)
    except ValueError as e:
        if "insufficient data" in str(e).lower():
            raise InsufficientDataError(user_id)
        raise
    except Exception as e:
        logger.error(f"Drift detection failed for user {user_id}: {e}", exc_info=True)
        raise DatabaseError(str(e))
    
    # Convert to API response models
    event_responses = [
        DriftEventResponse(
            drift_event_id=event.drift_event_id,
            user_id=event.user_id,
            drift_type=DriftTypeAPI(event.drift_type.value),
            drift_score=event.drift_score,
            severity=DriftSeverityAPI(event.severity.value),
            affected_targets=event.affected_targets,
            evidence=event.evidence,
            confidence=event.confidence,
            reference_window_start=event.reference_window_start,
            reference_window_end=event.reference_window_end,
            current_window_start=event.current_window_start,
            current_window_end=event.current_window_end,
            detected_at=event.detected_at,
            acknowledged_at=event.acknowledged_at,
            behavior_ref_ids=event.behavior_ref_ids,
            conflict_ref_ids=event.conflict_ref_ids
        )
        for event in events
    ]
    
    message = (
        f"No drift detected for user {user_id}"
        if len(events) == 0
        else f"Detected {len(events)} drift event(s) for user {user_id}"
    )
    
    logger.info(message)
    
    return DetectDriftResponse(
        user_id=user_id,
        detected_events=event_responses,
        detection_timestamp=now(),
        total_events=len(events),
        message=message
    )


# ============================================================================
# Get Drift Events
# ============================================================================

@router.get(
    "/events/{user_id}",
    response_model=GetDriftEventsResponse,
    summary="Get drift events",
    description="Get historical drift events for a user with optional filtering"
)
async def get_drift_events(
    user_id: str = Path(..., description="User ID to get events for"),
    drift_type: DriftTypeAPI | None = Query(None, description="Filter by drift type"),
    severity: DriftSeverityAPI | None = Query(None, description="Filter by severity"),
    start_date: datetime | None = Query(None, description="Filter events after this date"),
    end_date: datetime | None = Query(None, description="Filter events before this date"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of events"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    db: Connection = Depends(get_db_connection)
) -> GetDriftEventsResponse:
    """
    Get drift events for a user
    
    Retrieve historical drift detection events with optional filtering.
    
    - **user_id**: User to get events for
    - **drift_type**: Filter by drift type (optional)
    - **severity**: Filter by severity level (optional)
    - **start_date**: Only events detected after this date (optional)
    - **end_date**: Only events detected before this date (optional)
    - **limit**: Maximum number of events to return
    - **offset**: Pagination offset
    """
    logger.info(f"Getting drift events for user: {user_id}")
    
    drift_event_repo = DriftEventRepository(db)
    
    # Convert API enums to model enums
    model_drift_type = DriftType(drift_type.value) if drift_type else None
    model_severity = DriftSeverity(severity.value) if severity else None
    
    # Get events with filters
    try:
        events = drift_event_repo.get_by_user(
            user_id=user_id,
            drift_type=model_drift_type,
            severity=model_severity,
            start_date=int(start_date.timestamp()) if start_date else None,
            end_date=int(end_date.timestamp()) if end_date else None,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Failed to get drift events for user {user_id}: {e}", exc_info=True)
        raise DatabaseError(str(e))
    
    # Convert to API response models
    event_responses = [
        DriftEventResponse(
            drift_event_id=event.drift_event_id,
            user_id=event.user_id,
            drift_type=DriftTypeAPI(event.drift_type.value),
            drift_score=event.drift_score,
            severity=DriftSeverityAPI(event.severity.value),
            affected_targets=event.affected_targets,
            evidence=event.evidence,
            confidence=event.confidence,
            reference_window_start=event.reference_window_start,
            reference_window_end=event.reference_window_end,
            current_window_start=event.current_window_start,
            current_window_end=event.current_window_end,
            detected_at=event.detected_at,
            acknowledged_at=event.acknowledged_at,
            behavior_ref_ids=event.behavior_ref_ids,
            conflict_ref_ids=event.conflict_ref_ids
        )
        for event in events
    ]
    
    return GetDriftEventsResponse(
        user_id=user_id,
        events=event_responses,
        total=len(event_responses),
        limit=limit,
        offset=offset
    )


# ============================================================================
# Get Single Drift Event
# ============================================================================

@router.get(
    "/events/{user_id}/{drift_event_id}",
    response_model=DriftEventResponse,
    summary="Get drift event by ID",
    description="Get a specific drift event by its ID"
)
async def get_drift_event(
    user_id: str = Path(..., description="User ID"),
    drift_event_id: str = Path(..., description="Drift event ID"),
    db: Connection = Depends(get_db_connection)
) -> DriftEventResponse:
    """
    Get a specific drift event
    
    Retrieve details of a single drift event by its ID.
    
    - **user_id**: User ID (for validation)
    - **drift_event_id**: Drift event ID to retrieve
    """
    logger.info(f"Getting drift event: {drift_event_id}")
    
    drift_event_repo = DriftEventRepository(db)
    
    try:
        event = drift_event_repo.get_by_id(drift_event_id)
    except Exception as e:
        logger.error(f"Failed to get drift event {drift_event_id}: {e}", exc_info=True)
        raise DatabaseError(str(e))
    
    if not event:
        raise DriftEventNotFoundError(drift_event_id)
    
    if event.user_id != user_id:
        raise DriftEventNotFoundError(drift_event_id)
    
    return DriftEventResponse(
        drift_event_id=event.drift_event_id,
        user_id=event.user_id,
        drift_type=DriftTypeAPI(event.drift_type.value),
        drift_score=event.drift_score,
        severity=DriftSeverityAPI(event.severity.value),
        affected_targets=event.affected_targets,
        evidence=event.evidence,
        confidence=event.confidence,
        reference_window_start=event.reference_window_start,
        reference_window_end=event.reference_window_end,
        current_window_start=event.current_window_start,
        current_window_end=event.current_window_end,
        detected_at=event.detected_at,
        acknowledged_at=event.acknowledged_at,
        behavior_ref_ids=event.behavior_ref_ids,
        conflict_ref_ids=event.conflict_ref_ids
    )


# ============================================================================
# Acknowledge Drift Event
# ============================================================================

@router.post(
    "/events/{user_id}/{drift_event_id}/acknowledge",
    response_model=AcknowledgeDriftResponse,
    summary="Acknowledge drift event",
    description="Mark a drift event as acknowledged"
)
async def acknowledge_drift_event(
    user_id: str = Path(..., description="User ID"),
    drift_event_id: str = Path(..., description="Drift event ID to acknowledge"),
    db: Connection = Depends(get_db_connection)
) -> AcknowledgeDriftResponse:
    """
    Acknowledge a drift event
    
    Mark a drift event as acknowledged/read. This updates the acknowledged_at timestamp.
    
    - **user_id**: User ID (for validation)
    - **drift_event_id**: Drift event ID to acknowledge
    """
    logger.info(f"Acknowledging drift event: {drift_event_id}")
    
    drift_event_repo = DriftEventRepository(db)
    
    # Check if event exists
    try:
        event = drift_event_repo.get_by_id(drift_event_id)
    except Exception as e:
        logger.error(f"Failed to get drift event {drift_event_id}: {e}", exc_info=True)
        raise DatabaseError(str(e))
    
    if not event:
        raise DriftEventNotFoundError(drift_event_id)
    
    if event.user_id != user_id:
        raise DriftEventNotFoundError(drift_event_id)
    
    # Acknowledge the event
    acknowledged_at = now()
    try:
        drift_event_repo.update_acknowledged(drift_event_id, acknowledged_at)
    except Exception as e:
        logger.error(f"Failed to acknowledge drift event {drift_event_id}: {e}", exc_info=True)
        raise DatabaseError(str(e))
    
    return AcknowledgeDriftResponse(
        drift_event_id=drift_event_id,
        acknowledged_at=acknowledged_at,
        message=f"Drift event {drift_event_id} acknowledged successfully"
    )
