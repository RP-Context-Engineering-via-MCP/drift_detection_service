"""API dependencies for dependency injection."""

from typing import Generator

from sqlalchemy.orm import Session

from app.database import get_db

# Re-export for convenience
__all__ = ["get_db"]
