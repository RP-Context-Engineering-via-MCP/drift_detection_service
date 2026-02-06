"""Repository for behavior data access."""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import BehaviorState
from app.core.logging_config import get_logger
from app.models.behavior import Behavior
from app.utils.datetime_helpers import now_utc

logger = get_logger(__name__)


class BehaviorRepository:
    """Data access layer for Behavior entities."""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def create(self, behavior: Behavior) -> Behavior:
        """
        Create a new behavior record.
        
        Args:
            behavior: Behavior instance to create
        
        Returns:
            Created behavior with generated ID
        """
        self.db.add(behavior)
        self.db.commit()
        self.db.refresh(behavior)
        logger.info(f"Created behavior {behavior.behavior_id} for user {behavior.user_id}")
        return behavior

    def get_by_id(self, behavior_id: uuid.UUID) -> Optional[Behavior]:
        """
        Get behavior by ID.
        
        Args:
            behavior_id: Behavior UUID
        
        Returns:
            Behavior if found, None otherwise
        """
        return self.db.query(Behavior).filter(Behavior.behavior_id == behavior_id).first()

    def find_semantic_candidates(
        self,
        user_id: str,
        embedding: List[float],
        distance_threshold: float,
        limit: int = 5,
    ) -> List[tuple[Behavior, float]]:
        """
        Find semantically similar behaviors using vector search.
        
        Args:
            user_id: User identifier
            embedding: Query vector
            distance_threshold: Maximum cosine distance (e.g., 0.55)
            limit: Maximum number of results
        
        Returns:
            List of (Behavior, distance) tuples, ordered by similarity
        """
        # pgvector cosine distance operator: <=>
        stmt = (
            select(
                Behavior,
                Behavior.embedding.cosine_distance(embedding).label("distance"),
            )
            .where(
                and_(
                    Behavior.user_id == user_id,
                    Behavior.state == BehaviorState.ACTIVE.value,
                    Behavior.embedding.isnot(None),
                    Behavior.embedding.cosine_distance(embedding) < distance_threshold,
                )
            )
            .order_by("distance")
            .limit(limit)
        )

        results = self.db.execute(stmt).all()
        logger.debug(
            f"Found {len(results)} semantic candidates within distance {distance_threshold}"
        )
        return [(row.Behavior, row.distance) for row in results]

    def update_credibility(
        self, behavior_id: uuid.UUID, new_credibility: float, increment_count: bool = True
    ) -> Optional[Behavior]:
        """
        Update behavior credibility and last_seen timestamp (reinforcement).
        
        Args:
            behavior_id: Behavior to update
            new_credibility: Updated credibility score
            increment_count: Whether to increment reinforcement_count
        
        Returns:
            Updated behavior
        """
        behavior = self.get_by_id(behavior_id)
        if not behavior:
            return None

        behavior.credibility = new_credibility
        behavior.last_seen_at = now_utc()
        if increment_count:
            behavior.reinforcement_count += 1

        self.db.commit()
        self.db.refresh(behavior)
        logger.info(
            f"Reinforced behavior {behavior_id}: credibility={new_credibility:.2f}, "
            f"count={behavior.reinforcement_count}"
        )
        return behavior

    def supersede_behavior(
        self, old_behavior_id: uuid.UUID, new_behavior: Behavior
    ) -> tuple[Behavior, Behavior]:
        """
        Mark an old behavior as SUPERSEDED and create a new one.
        
        Args:
            old_behavior_id: Behavior to supersede
            new_behavior: New behavior to create
        
        Returns:
            Tuple of (old_behavior, new_behavior)
        """
        old_behavior = self.get_by_id(old_behavior_id)
        if not old_behavior:
            raise ValueError(f"Behavior {old_behavior_id} not found")

        old_behavior.state = BehaviorState.SUPERSEDED.value
        new_behavior = self.create(new_behavior)

        logger.info(
            f"Superseded behavior {old_behavior_id} with {new_behavior.behavior_id}"
        )
        return old_behavior, new_behavior

    def get_active_behaviors(
        self, user_id: str, intent: Optional[str] = None
    ) -> List[Behavior]:
        """
        Get all active behaviors for a user.
        
        Args:
            user_id: User identifier
            intent: Optional intent filter
        
        Returns:
            List of active behaviors
        """
        query = self.db.query(Behavior).filter(
            and_(
                Behavior.user_id == user_id,
                Behavior.state == BehaviorState.ACTIVE.value,
            )
        )

        if intent:
            query = query.filter(Behavior.intent == intent)

        return query.order_by(desc(Behavior.last_seen_at)).all()
