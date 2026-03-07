"""
API Routes

REST API endpoints for drift detection service
"""

from typing import List, Dict, Tuple
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, Query, Path, Body
from psycopg2.extensions import connection as Connection

from api.models import (
    DetectDriftResponse,
    GetDriftEventsResponse,
    DriftEventResponse,
    AcknowledgeDriftResponse,
    HealthResponse,
    DriftTypeAPI,
    DriftSeverityAPI,
    UserDriftDashboardResponse,
    DriftSummary,
    DriftTimelineItem,
    DriftInsight
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
from app.db.connection import check_database_health, now
from app.utils.time import now_ms
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
    detector: DriftDetector = Depends(get_drift_detector)
) -> DetectDriftResponse:
    """
    Detect behavioral drift for a user
    
    This endpoint runs the drift detection pipeline for the specified user.
    It analyzes behavior patterns and returns detected drift events.
    
    - **user_id**: The user to analyze
    - **force**: Skip cooldown period (default: False)
    """
    logger.info(f"Drift detection requested for user: {user_id}, force={force}")
    
    # Run detection (includes pre-flight checks for data and cooldown)
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


# ============================================================================
# User Drift Dashboard (Frontend-Friendly)
# ============================================================================

def _generate_drift_explanation(drift_type: str, evidence: Dict, affected_targets: List[str]) -> Tuple[str, str, List[str]]:
    """
    Generate human-readable title, description, and recommendations for a drift event.
    
    Returns:
        (title, description, recommendations)
    """
    if drift_type == "TOPIC_EMERGENCE":
        topics = ", ".join(affected_targets[:3])
        if len(affected_targets) > 3:
            topics += f" and {len(affected_targets) - 3} more"
        
        title = f"New Interest: {topics}"
        description = (
            f"You've started showing interest in new topics: {topics}. "
            f"This represents a {evidence.get('cluster_size', len(affected_targets))} topic cluster "
            f"that wasn't present in your previous behavior patterns."
        )
        recommendations = [
            f"Explore more content related to {affected_targets[0]}",
            "Consider how these new topics align with your goals",
            "Review if this represents a genuine interest shift"
        ]
    
    elif drift_type == "TOPIC_ABANDONMENT":
        topics = ", ".join(affected_targets[:3])
        if len(affected_targets) > 3:
            topics += f" and {len(affected_targets) - 3} more"
        
        title = f"Decreased Interest: {topics}"
        description = (
            f"You've significantly reduced engagement with: {topics}. "
            f"These topics were previously active but show minimal recent activity."
        )
        recommendations = [
            f"Reflect on why interest in {affected_targets[0]} decreased",
            "Consider if this aligns with your current priorities",
            "Archive or update outdated preferences"
        ]
    
    elif drift_type == "PREFERENCE_REVERSAL":
        topics = ", ".join(affected_targets[:3])
        if len(affected_targets) > 3:
            topics += f" and {len(affected_targets) - 3} more"
        
        polarity_change = evidence.get('polarity_from', '?') + " → " + evidence.get('polarity_to', '?')
        title = f"Opinion Flip: {topics}"
        description = (
            f"Your sentiment about {topics} has reversed ({polarity_change}). "
            f"This indicates a significant change in opinion or preference."
        )
        recommendations = [
            f"Review what changed your perspective on {affected_targets[0]}",
            "Update related preferences to maintain consistency",
            "Acknowledge the shift in your feedback patterns"
        ]
    
    elif drift_type == "INTENSITY_SHIFT":
        topics = ", ".join(affected_targets[:3])
        if len(affected_targets) > 3:
            topics += f" and {len(affected_targets) - 3} more"
        
        direction = evidence.get('direction', 'changed')
        delta = evidence.get('delta_abs', 0)
        
        title = f"Conviction Change: {topics}"
        description = (
            f"The strength of your opinion about {topics} has {direction}d by {delta:.2f}. "
            f"This suggests {'stronger conviction' if direction == 'INCREASE' else 'weakening interest'}."
        )
        recommendations = [
            f"Validate the {'increased' if direction == 'INCREASE' else 'decreased'} certainty about {affected_targets[0]}",
            "Check if external factors influenced this change",
            "Ensure your preferences reflect current beliefs"
        ]
    
    elif drift_type in ["CONTEXT_EXPANSION", "CONTEXT_CONTRACTION"]:
        topics = ", ".join(affected_targets[:3])
        if len(affected_targets) > 3:
            topics += f" and {len(affected_targets) - 3} more"
        
        old_contexts = evidence.get('contexts_before', [])
        new_contexts = evidence.get('contexts_after', [])
        
        if drift_type == "CONTEXT_EXPANSION":
            title = f"Broader Application: {topics}"
            description = (
                f"You're now using {topics} in broader contexts. "
                f"Context evolved from {old_contexts} to {new_contexts}, indicating wider application."
            )
        else:
            title = f"Focused Application: {topics}"
            description = (
                f"Your use of {topics} has become more focused. "
                f"Context narrowed from {old_contexts} to {new_contexts}, indicating specialization."
            )
        
        recommendations = [
            f"Explore further applications of {affected_targets[0]}",
            "Consider if this context shift matches your goals",
            "Update related interest profiles"
        ]
    
    else:
        title = f"Behavioral Change Detected"
        description = f"A change in behavior pattern was detected for: {', '.join(affected_targets[:3])}"
        recommendations = ["Review your recent activity patterns"]
    
    return title, description, recommendations


@router.get(
    "/dashboard/{user_id}",
    response_model=UserDriftDashboardResponse,
    summary="Get user drift dashboard",
    description="Get a comprehensive, frontend-friendly view of all drift events for a user"
)
async def get_user_drift_dashboard(
    user_id: str = Path(..., description="User ID to get dashboard for"),
    days: int = Query(90, ge=1, le=365, description="Number of days of history to include"),
    db: Connection = Depends(get_db_connection)
) -> UserDriftDashboardResponse:
    """
    Get a comprehensive drift dashboard for frontend display
    
    This endpoint provides drift data wrapped in a meaningful, user-friendly format
    that helps users understand how and why their behavioral drift happened.
    
    Features:
    - Summary statistics (total drifts, breakdown by type/severity)
    - Timeline view of drift events
    - Human-readable insights with explanations
    - Actionable recommendations
    - Raw event data for detailed inspection
    
    - **user_id**: User to get dashboard for
    - **days**: Number of days of history (default: 90)
    """
    logger.info(f"Getting drift dashboard for user: {user_id}, days={days}")
    
    drift_event_repo = DriftEventRepository(db)
    
    # Calculate time range in milliseconds (drift events use ms timestamps)
    end_time = now_ms()
    start_time = end_time - (days * 24 * 60 * 60 * 1000)  # Convert days to milliseconds
    
    # Get all drift events for the user in the time range
    try:
        events = drift_event_repo.get_by_user(
            user_id=user_id,
            start_date=start_time,
            end_date=end_time,
            limit=1000,
            offset=0
        )
    except Exception as e:
        logger.error(f"Failed to get drift events for dashboard: {e}", exc_info=True)
        raise DatabaseError(str(e))
    
    # Build summary statistics
    severity_counts = {}
    type_counts = {}
    earliest_timestamp = end_time
    latest_timestamp = start_time
    
    for event in events:
        # Count by severity
        severity_key = event.severity.value
        severity_counts[severity_key] = severity_counts.get(severity_key, 0) + 1
        
        # Count by type
        type_key = event.drift_type.value
        type_counts[type_key] = type_counts.get(type_key, 0) + 1
        
        # Track date range
        if event.detected_at < earliest_timestamp:
            earliest_timestamp = event.detected_at
        if event.detected_at > latest_timestamp:
            latest_timestamp = event.detected_at
    
    # Determine most common type and highest severity
    most_common_type = max(type_counts, key=type_counts.get) if type_counts else None
    highest_severity = None
    if "STRONG_DRIFT" in severity_counts:
        highest_severity = "STRONG_DRIFT"
    elif "MODERATE_DRIFT" in severity_counts:
        highest_severity = "MODERATE_DRIFT"
    elif "WEAK_DRIFT" in severity_counts:
        highest_severity = "WEAK_DRIFT"
    
    # Create summary
    summary = DriftSummary(
        total_drifts=len(events),
        by_severity=severity_counts,
        by_type=type_counts,
        most_common_type=most_common_type,
        highest_severity=highest_severity,
        date_range={
            "from": datetime.fromtimestamp(earliest_timestamp / 1000).strftime("%Y-%m-%d") if events else "",
            "to": datetime.fromtimestamp(latest_timestamp / 1000).strftime("%Y-%m-%d") if events else ""
        }
    )
    
    # Build timeline
    timeline = []
    for event in sorted(events, key=lambda e: e.detected_at, reverse=True):
        date_label = datetime.fromtimestamp(event.detected_at / 1000).strftime("%b %d, %Y")
        
        # Generate short description
        targets_preview = ", ".join(event.affected_targets[:2])
        if len(event.affected_targets) > 2:
            targets_preview += "..."
        
        short_desc = f"{event.drift_type.value.replace('_', ' ').title()}: {targets_preview}"
        
        timeline.append(DriftTimelineItem(
            drift_event_id=event.drift_event_id,
            drift_type=event.drift_type.value,
            severity=event.severity.value,
            timestamp=event.detected_at,
            date_label=date_label,
            short_description=short_desc
        ))
    
    # Build insights with explanations
    insights = []
    for event in events:
        # Determine impact level
        if event.severity == DriftSeverity.STRONG_DRIFT:
            impact_level = "high"
        elif event.severity == DriftSeverity.MODERATE_DRIFT:
            impact_level = "medium"
        else:
            impact_level = "low"
        
        # Generate explanation
        title, description, recommendations = _generate_drift_explanation(
            event.drift_type.value,
            event.evidence,
            event.affected_targets
        )
        
        # Format time period (timestamps are in milliseconds)
        ref_start = datetime.fromtimestamp(event.reference_window_start / 1000).strftime("%Y-%m-%d")
        ref_end = datetime.fromtimestamp(event.reference_window_end / 1000).strftime("%Y-%m-%d")
        curr_start = datetime.fromtimestamp(event.current_window_start / 1000).strftime("%Y-%m-%d")
        curr_end = datetime.fromtimestamp(event.current_window_end / 1000).strftime("%Y-%m-%d")
        time_period = f"Reference: {ref_start} to {ref_end} | Current: {curr_start} to {curr_end}"
        
        insights.append(DriftInsight(
            drift_event_id=event.drift_event_id,
            title=title,
            description=description,
            impact_level=impact_level,
            affected_items=event.affected_targets,
            time_period=time_period,
            recommendations=recommendations
        ))
    
    # Convert events to API response format
    raw_events = [
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
    
    logger.info(f"Generated dashboard for user {user_id}: {len(events)} events")
    
    return UserDriftDashboardResponse(
        user_id=user_id,
        summary=summary,
        timeline=timeline,
        insights=insights,
        raw_events=raw_events,
        generated_at=now_ms()
    )
