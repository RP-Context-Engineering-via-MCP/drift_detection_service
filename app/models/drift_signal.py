"""Drift signal database model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class DriftSignal(Base):
    """
    Tracks rejected behavior change attempts that may indicate drift.
    
    When a new behavior loses a conflict (IGNORE action), it's logged here.
    Accumulation of signals for the same behavior indicates user persistence
    and potential drift, which can override credibility-based decisions.
    """

    __tablename__ = "drift_signals"

    # Primary Key
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # User Identification
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Reference to the Existing Behavior being challenged
    existing_behavior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("behaviors.behavior_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The New Behavior that was rejected
    new_intent: Mapped[str] = mapped_column(String(50), nullable=False)
    new_target: Mapped[str] = mapped_column(Text, nullable=False)
    new_polarity: Mapped[str] = mapped_column(String(20), nullable=False)
    new_context: Mapped[str] = mapped_column(String(255), nullable=False)
    new_credibility: Mapped[float] = mapped_column(nullable=False)

    # Temporal Tracking
    attempted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Drift Classification
    drift_type: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )  # POLARITY_SHIFT, TARGET_SHIFT, etc.

    # Indexes for efficient drift detection queries
    __table_args__ = (
        Index(
            "ix_drift_signals_behavior_time",
            "existing_behavior_id",
            "attempted_at",
        ),
        Index("ix_drift_signals_user_time", "user_id", "attempted_at"),
    )

    def __repr__(self) -> str:
        """String representation of DriftSignal."""
        return (
            f"<DriftSignal(id={self.signal_id}, behavior={self.existing_behavior_id}, "
            f"new_target={self.new_target}, attempted_at={self.attempted_at})>"
        )
