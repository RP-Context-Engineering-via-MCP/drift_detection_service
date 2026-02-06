"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import behaviors, health

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="", tags=["Health"])
api_router.include_router(behaviors.router, prefix="", tags=["Behaviors"])
