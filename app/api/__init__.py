"""API package initialization."""

from app.api.dependencies import get_db

__all__ = ["get_db"]
