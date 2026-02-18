"""
API Error Handlers

Custom exception handlers for the API
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime
import logging

from api.models import ErrorResponse

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================

class DriftDetectionError(Exception):
    """Base exception for drift detection errors"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InsufficientDataError(DriftDetectionError):
    """Raised when user has insufficient data for drift detection"""
    def __init__(self, user_id: str):
        super().__init__(
            f"User {user_id} has insufficient data for drift detection",
            status_code=400
        )


class UserNotFoundError(DriftDetectionError):
    """Raised when user is not found"""
    def __init__(self, user_id: str):
        super().__init__(
            f"User {user_id} not found",
            status_code=404
        )


class CooldownError(DriftDetectionError):
    """Raised when detection is in cooldown period"""
    def __init__(self, user_id: str, seconds_remaining: int):
        super().__init__(
            f"User {user_id} is in cooldown period. Try again in {seconds_remaining} seconds",
            status_code=429
        )


class DriftEventNotFoundError(DriftDetectionError):
    """Raised when drift event is not found"""
    def __init__(self, drift_event_id: str):
        super().__init__(
            f"Drift event {drift_event_id} not found",
            status_code=404
        )


class DatabaseError(DriftDetectionError):
    """Raised when database operation fails"""
    def __init__(self, detail: str):
        super().__init__(
            "Database operation failed",
            status_code=500
        )
        self.detail = detail


# ============================================================================
# Exception Handlers
# ============================================================================

async def drift_detection_error_handler(
    request: Request,
    exc: DriftDetectionError
) -> JSONResponse:
    """Handle DriftDetectionError and subclasses"""
    error_response = ErrorResponse(
        error=exc.message,
        detail=getattr(exc, 'detail', None),
        timestamp=int(datetime.now().timestamp())
    )
    
    logger.warning(
        f"DriftDetectionError: {exc.message}",
        extra={
            "path": request.url.path,
            "status_code": exc.status_code
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors"""
    error_response = ErrorResponse(
        error="Validation error",
        detail=str(exc),
        timestamp=int(datetime.now().timestamp())
    )
    
    logger.warning(
        f"Validation error: {exc}",
        extra={"path": request.url.path}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump()
    )


async def generic_error_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle unexpected errors"""
    error_response = ErrorResponse(
        error="Internal server error",
        detail=str(exc) if logger.level <= logging.DEBUG else None,
        timestamp=int(datetime.now().timestamp())
    )
    
    logger.error(
        f"Unexpected error: {exc}",
        exc_info=True,
        extra={"path": request.url.path}
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()
    )
