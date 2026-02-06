"""Pydantic schemas for API request/response validation."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import BehaviorState, Intent, Polarity, ResolutionAction


# ============= Request Schemas =============


class CanonicalBehaviorInput(BaseModel):
    """Input schema for a single canonical behavior from extraction service."""

    intent: str = Field(..., description="Canonical intent (PREFERENCE, GOAL, etc.)")
    target: str = Field(..., description="The subject of the behavior")
    context: str = Field(default="general", description="Contextual qualifier")
    polarity: str = Field(..., description="Sentiment polarity (POSITIVE, NEGATIVE)")
    extracted_credibility: float = Field(
        ..., ge=0.0, le=1.0, description="Credibility score from extraction"
    )
    embedding: Optional[List[float]] = Field(
        default=None, description="Vector embedding (3072-dim)"
    )

    @field_validator("extracted_credibility")
    @classmethod
    def validate_credibility(cls, v: float) -> float:
        """Ensure credibility is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Credibility must be between 0.0 and 1.0")
        return v


class ProcessBehaviorRequest(BaseModel):
    """Request to process one or more behaviors for a user."""

    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When the behavior was observed",
    )
    candidates: List[CanonicalBehaviorInput] = Field(
        ..., min_length=1, description="List of behaviors to process"
    )


# ============= Response Schemas =============


class BehaviorResponse(BaseModel):
    """Response schema for a behavior record."""

    behavior_id: uuid.UUID
    user_id: str
    intent: str
    target: str
    context: str
    polarity: str
    credibility: float
    reinforcement_count: int
    state: str
    last_seen_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolutionDetail(BaseModel):
    """Details about a resolution action taken."""

    type: ResolutionAction = Field(..., description="Action taken")
    reason: str = Field(..., description="Explanation of why this action was taken")
    details: str = Field(..., description="Additional technical details")
    old_behavior_id: Optional[uuid.UUID] = Field(
        default=None, description="ID of superseded/reinforced behavior"
    )
    new_behavior_id: Optional[uuid.UUID] = Field(
        default=None, description="ID of newly created behavior"
    )
    drift_detected: bool = Field(
        default=False, description="Whether drift was detected"
    )
    effective_credibility: Optional[float] = Field(
        default=None, description="Time-decayed credibility of existing behavior"
    )


class ProcessBehaviorResponse(BaseModel):
    """Response from processing behavior(s)."""

    status: str = Field(default="PROCESSED", description="Overall processing status")
    actions_taken: List[ResolutionDetail] = Field(
        ..., description="List of actions performed"
    )
    processed_count: int = Field(..., description="Number of behaviors processed")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When processing completed",
    )


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy")
    service: str = Field(default="drift_detection_service")
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict] = Field(default=None, description="Additional details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
