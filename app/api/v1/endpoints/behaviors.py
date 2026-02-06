"""Behavior processing endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.database import get_db
from app.models.schemas import (
    ErrorResponse,
    ProcessBehaviorRequest,
    ProcessBehaviorResponse,
    ResolutionDetail,
)
from app.services.resolution_engine import ResolutionEngine

logger = get_logger(__name__)

router = APIRouter(tags=["Behaviors"])


@router.post(
    "/behaviors/process",
    response_model=ProcessBehaviorResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def process_behaviors(
    request: ProcessBehaviorRequest,
    db: Session = Depends(get_db),
) -> ProcessBehaviorResponse:
    """
    Process canonical behaviors from the extraction service.
    
    This is the main endpoint that receives behaviors and applies
    drift detection and resolution logic.
    
    **Workflow:**
    1. Receive canonical behaviors with embeddings
    2. For each behavior:
        - Find semantic matches using vector search
        - Calculate temporal decay of existing behaviors
        - Check for drift signal accumulation
        - Resolve conflict (SUPERSEDE/REINFORCE/INSERT/IGNORE)
    3. Return detailed resolution results
    
    Args:
        request: ProcessBehaviorRequest with user_id and behavior candidates
        db: Database session (injected)
    
    Returns:
        ProcessBehaviorResponse with actions taken
    
    Raises:
        HTTPException: 400 for invalid data, 500 for processing errors
    """
    logger.info(
        f"Received behavior processing request for user {request.user_id} "
        f"with {len(request.candidates)} candidate(s)"
    )

    try:
        # Initialize resolution engine
        resolution_engine = ResolutionEngine(db)

        # Process each behavior candidate
        actions: List[ResolutionDetail] = []
        for candidate in request.candidates:
            try:
                action = resolution_engine.process_behavior(
                    user_id=request.user_id, candidate=candidate
                )
                actions.append(action)
            except Exception as e:
                logger.error(
                    f"Error processing candidate {candidate.target}: {str(e)}",
                    exc_info=True,
                )
                # Continue processing other candidates
                actions.append(
                    ResolutionDetail(
                        type="ERROR",
                        reason=f"Processing failed: {str(e)}",
                        details=f"Target: {candidate.target}",
                        drift_detected=False,
                    )
                )

        response = ProcessBehaviorResponse(
            status="PROCESSED",
            actions_taken=actions,
            processed_count=len(request.candidates),
        )

        logger.info(
            f"Successfully processed {len(actions)} behaviors for user {request.user_id}"
        )
        return response

    except Exception as e:
        logger.error(
            f"Fatal error processing behaviors for user {request.user_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process behaviors: {str(e)}",
        )


@router.get("/behaviors/user/{user_id}", response_model=dict)
def get_user_behaviors(
    user_id: str,
    state: str = "ACTIVE",
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict:
    """
    Retrieve behaviors for a specific user.
    
    Useful for debugging and analytics.
    
    Args:
        user_id: User identifier
        state: Filter by state (ACTIVE, SUPERSEDED, FLAGGED)
        limit: Maximum number of behaviors to return
        db: Database session (injected)
    
    Returns:
        Dictionary with user behaviors
    """
    from app.database.repositories import BehaviorRepository

    logger.info(f"Retrieving behaviors for user {user_id} with state {state}")

    try:
        repo = BehaviorRepository(db)
        behaviors = repo.get_active_behaviors(user_id)[:limit]

        return {
            "user_id": user_id,
            "count": len(behaviors),
            "behaviors": [b.to_dict() for b in behaviors],
        }
    except Exception as e:
        logger.error(f"Error retrieving behaviors: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve behaviors: {str(e)}",
        )
