"""Behavior database model."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.constants import BehaviorState, Intent, Polarity
from app.database.base import Base


class Behavior(Base):
    """
    Represents a user's behavioral pattern with temporal tracking.
    
    This model stores canonicalized user behaviors and tracks their
    credibility, reinforcement, and temporal decay.
    """

    __tablename__ = "behaviors"

    # Primary Key
    behavior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # User Identification
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Canonical Fields
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(String(255), default="general", nullable=False)
    polarity: Mapped[str] = mapped_column(String(20), nullable=False)

    # Credibility and Reinforcement
    credibility: Mapped[float] = mapped_column(Float, nullable=False)
    reinforcement_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # State Management
    state: Mapped[str] = mapped_column(
        String(20),
        default=BehaviorState.ACTIVE.value,
        nullable=False,
    )

    # Temporal Tracking (Critical for Drift Detection)
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Vector Embedding for Semantic Search
    # Dimension configurable via EMBEDDING_DIMENSION env var (default: 1536)
    # Max 2000 for Supabase pgvector with index support
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1536),  # OpenAI text-embedding-ada-002 dimension (or configure via env)
        nullable=True,
    )

    # Indexes
    # Note: Vector index removed due to Supabase 2000-dimension limit
    # For better performance with large datasets, manually create index:
    # CREATE INDEX ix_behaviors_embedding ON behaviors 
    # USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
    # (Only if your embedding dimension <= 2000)
    __table_args__ = (
        Index("ix_behaviors_user_state", "user_id", "state"),
        Index("ix_behaviors_user_intent", "user_id", "intent"),
    )

    def __repr__(self) -> str:
        """String representation of Behavior."""
        return (
            f"<Behavior(id={self.behavior_id}, user={self.user_id}, "
            f"intent={self.intent}, target={self.target}, "
            f"credibility={self.credibility}, state={self.state})>"
        )
