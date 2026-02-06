"""Repository for drift signal data access."""

import uuid
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.drift_signal import DriftSignal
from app.utils.datetime_helpers import now_utc

logger = get_logger(__name__)


class DriftSignalRepository:
    """Data access layer for DriftSignal entities."""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self, drift_signal: DriftSignal) -> DriftSignal:
        """
        Log a new drift signal.
        
        Args:
            drift_signal: DriftSignal instance to create
        
        Returns:
            Created drift signal
        """
        self.db.add(drift_signal)
        self.db.commit()
        self.db.refresh(drift_signal)
        logger.info(
            f"Logged drift signal {drift_signal.signal_id} for "
            f"behavior {drift_signal.existing_behavior_id}"
        )
        return drift_signal

    def count_recent_signals(
        self, behavior_id: uuid.UUID, window_days: int
    ) -> int:
        """
        Count drift signals for a behavior within a time window.
        
        This is the core "accumulation detection" query.
        
        Args:
            behavior_id: Behavior being challenged
            window_days: Time window in days (e.g., 30)
        
        Returns:
            Count of drift signals in the window
        """
        cutoff_time = now_utc() - timedelta(days=window_days)

        count = (
            self.db.query(func.count(DriftSignal.signal_id))
            .filter(
                and_(
                    DriftSignal.existing_behavior_id == behavior_id,
                    DriftSignal.attempted_at >= cutoff_time,
                )
            )
            .scalar()
        )

        logger.debug(
            f"Found {count} drift signals for behavior {behavior_id} "
            f"in last {window_days} days"
        )
        return count or 0

    def get_recent_signals(
        self, behavior_id: uuid.UUID, window_days: int, limit: int = 10
    ) -> List[DriftSignal]:
        """
        Get recent drift signals for a behavior.
        
        Args:
            behavior_id: Behavior being challenged
            window_days: Time window in days
            limit: Maximum signals to return
        
        Returns:
            List of recent drift signals
        """
        cutoff_time = now_utc() - timedelta(days=window_days)

        return (
            self.db.query(DriftSignal)
            .filter(
                and_(
                    DriftSignal.existing_behavior_id == behavior_id,
                    DriftSignal.attempted_at >= cutoff_time,
                )
            )
            .order_by(desc(DriftSignal.attempted_at))
            .limit(limit)
            .all()
        )

    def get_user_signals(
        self, user_id: str, window_days: int, limit: int = 50
    ) -> List[DriftSignal]:
        """
        Get all drift signals for a user.
        
        Args:
            user_id: User identifier
            window_days: Time window in days
            limit: Maximum signals to return
        
        Returns:
            List of user's drift signals
        """
        cutoff_time = now_utc() - timedelta(days=window_days)

        return (
            self.db.query(DriftSignal)
            .filter(
                and_(
                    DriftSignal.user_id == user_id,
                    DriftSignal.attempted_at >= cutoff_time,
                )
            )
            .order_by(desc(DriftSignal.attempted_at))
            .limit(limit)
            .all()
        )
