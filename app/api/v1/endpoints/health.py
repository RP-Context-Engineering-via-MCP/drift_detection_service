"""Health check endpoints."""

from datetime import datetime

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.schemas import HealthCheckResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthCheckResponse)
def health_check() -> HealthCheckResponse:
    """
    Health check endpoint.
    
    Returns:
        Health status of the service
    """
    settings = get_settings()
    return HealthCheckResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(),
    )


@router.get("/health/ready", response_model=HealthCheckResponse)
def readiness_check() -> HealthCheckResponse:
    """
    Readiness check for Kubernetes/container orchestration.
    
    Returns:
        Readiness status
    """
    settings = get_settings()
    # In production, you might want to check database connectivity here
    return HealthCheckResponse(
        status="ready",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(),
    )
