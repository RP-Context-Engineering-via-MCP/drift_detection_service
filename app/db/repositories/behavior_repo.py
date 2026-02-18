"""
BehaviorRepository - Data access layer for behavior_snapshots table.

Provides methods to query and retrieve BehaviorRecord objects from the database.
"""

import logging
from typing import List, Optional
from datetime import datetime

from app.models.behavior import BehaviorRecord

logger = logging.getLogger(__name__)


class BehaviorRepository:
    """Repository for accessing behavior snapshot data."""

    def __init__(self, connection):
        """
        Initialize repository with database connection.

        Args:
            connection: Database connection object (psycopg2 or asyncpg)
        """
        self.connection = connection
        # Detect database type for parameter placeholder
        self._is_sqlite = "sqlite" in str(type(connection)).lower()
    
    def _adapt_query(self, query: str) -> str:
        """Convert PostgreSQL-style placeholders to SQLite if needed."""
        if self._is_sqlite:
            return query.replace("%s", "?")
        return query

    def get_behaviors_in_window(
        self, user_id: str, start_ts: int, end_ts: int
    ) -> List[BehaviorRecord]:
        """
        Retrieve all active behaviors for a user within a time window.

        Args:
            user_id: User identifier
            start_ts: Window start timestamp (seconds since epoch)
            end_ts: Window end timestamp (seconds since epoch)

        Returns:
            List of BehaviorRecord objects (empty list if none found)
        """
        query = """
            SELECT 
                user_id, behavior_id, target, intent, context,
                polarity, credibility, reinforcement_count, state,
                created_at, last_seen_at, snapshot_updated_at
            FROM behavior_snapshots
            WHERE user_id = %s
              AND created_at BETWEEN %s AND %s
              AND state = 'ACTIVE'
            ORDER BY created_at ASC
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id, start_ts, end_ts))
            rows = cursor.fetchall()
            cursor.close()

            behaviors = []
            for row in rows:
                behavior = BehaviorRecord(
                    user_id=row[0],
                    behavior_id=row[1],
                    target=row[2],
                    intent=row[3],
                    context=row[4],
                    polarity=row[5],
                    credibility=row[6],
                    reinforcement_count=row[7],
                    state=row[8],
                    created_at=row[9],
                    last_seen_at=row[10],
                    snapshot_updated_at=row[11],
                )
                behaviors.append(behavior)

            logger.debug(
                f"Retrieved {len(behaviors)} behaviors for user {user_id} "
                f"in window [{start_ts}, {end_ts}]"
            )
            return behaviors

        except Exception as e:
            logger.error(f"Error retrieving behaviors: {e}")
            raise

    def get_all_behaviors(self, user_id: str) -> List[BehaviorRecord]:
        """
        Retrieve all behaviors for a user (active and superseded).

        Args:
            user_id: User identifier

        Returns:
            List of BehaviorRecord objects
        """
        query = """
            SELECT 
                user_id, behavior_id, target, intent, context,
                polarity, credibility, reinforcement_count, state,
                created_at, last_seen_at, snapshot_updated_at
            FROM behavior_snapshots
            WHERE user_id = %s
            ORDER BY created_at DESC
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id,))
            rows = cursor.fetchall()
            cursor.close()

            behaviors = []
            for row in rows:
                behavior = BehaviorRecord(
                    user_id=row[0],
                    behavior_id=row[1],
                    target=row[2],
                    intent=row[3],
                    context=row[4],
                    polarity=row[5],
                    credibility=row[6],
                    reinforcement_count=row[7],
                    state=row[8],
                    created_at=row[9],
                    last_seen_at=row[10],
                    snapshot_updated_at=row[11],
                )
                behaviors.append(behavior)

            logger.debug(f"Retrieved {len(behaviors)} total behaviors for user {user_id}")
            return behaviors

        except Exception as e:
            logger.error(f"Error retrieving all behaviors: {e}")
            raise

    def count_active_behaviors(self, user_id: str) -> int:
        """
        Count the number of active behaviors for a user.

        Args:
            user_id: User identifier

        Returns:
            Count of active behaviors
        """
        query = """
            SELECT COUNT(*)
            FROM behavior_snapshots
            WHERE user_id = %s AND state = 'ACTIVE'
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id,))
            count = cursor.fetchone()[0]
            cursor.close()

            logger.debug(f"User {user_id} has {count} active behaviors")
            return count

        except Exception as e:
            logger.error(f"Error counting active behaviors: {e}")
            raise

    def get_earliest_behavior_date(self, user_id: str) -> Optional[int]:
        """
        Get the timestamp of the earliest behavior for a user.

        Args:
            user_id: User identifier

        Returns:
            Earliest created_at timestamp, or None if no behaviors exist
        """
        query = """
            SELECT MIN(created_at)
            FROM behavior_snapshots
            WHERE user_id = %s
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id,))
            result = cursor.fetchone()[0]
            cursor.close()

            if result:
                logger.debug(f"Earliest behavior for user {user_id}: {result}")
            else:
                logger.debug(f"No behaviors found for user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Error getting earliest behavior date: {e}")
            raise

    def get_behaviors_by_target(self, user_id: str, target: str) -> List[BehaviorRecord]:
        """
        Retrieve all active behaviors for a specific target.

        Args:
            user_id: User identifier
            target: Target name to filter by

        Returns:
            List of BehaviorRecord objects for the target
        """
        query = """
            SELECT 
                user_id, behavior_id, target, intent, context,
                polarity, credibility, reinforcement_count, state,
                created_at, last_seen_at, snapshot_updated_at
            FROM behavior_snapshots
            WHERE user_id = %s
              AND target = %s
              AND state = 'ACTIVE'
            ORDER BY last_seen_at DESC
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id, target))
            rows = cursor.fetchall()
            cursor.close()

            behaviors = []
            for row in rows:
                behavior = BehaviorRecord(
                    user_id=row[0],
                    behavior_id=row[1],
                    target=row[2],
                    intent=row[3],
                    context=row[4],
                    polarity=row[5],
                    credibility=row[6],
                    reinforcement_count=row[7],
                    state=row[8],
                    created_at=row[9],
                    last_seen_at=row[10],
                    snapshot_updated_at=row[11],
                )
                behaviors.append(behavior)

            logger.debug(
                f"Retrieved {len(behaviors)} behaviors for user {user_id}, target '{target}'"
            )
            return behaviors

        except Exception as e:
            logger.error(f"Error retrieving behaviors by target: {e}")
            raise

    def get_latest_behavior_for_target(
        self, user_id: str, target: str
    ) -> Optional[BehaviorRecord]:
        """
        Get the most recent active behavior for a specific target.

        Args:
            user_id: User identifier
            target: Target name

        Returns:
            Most recent BehaviorRecord, or None if not found
        """
        behaviors = self.get_behaviors_by_target(user_id, target)
        return behaviors[0] if behaviors else None

    def _insert_behavior(self, behavior: BehaviorRecord) -> None:
        """
        Insert a behavior record into the database (for testing).

        Args:
            behavior: BehaviorRecord to insert
        """
        query = """
            INSERT INTO behavior_snapshots (
                user_id, behavior_id, target, intent, context,
                polarity, credibility, reinforcement_count, state,
                created_at, last_seen_at, snapshot_updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor = self.connection.cursor()
        try:
            cursor.execute(
                self._adapt_query(query),
                (
                    behavior.user_id,
                    behavior.behavior_id,
                    behavior.target,
                    behavior.intent,
                    behavior.context,
                    behavior.polarity,
                    behavior.credibility,
                    behavior.reinforcement_count,
                    behavior.state,
                    behavior.created_at,
                    behavior.last_seen_at,
                    behavior.snapshot_updated_at,
                ),
            )
            self.connection.commit()
            logger.debug(f"Inserted behavior: {behavior.behavior_id}")
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Failed to insert behavior: {e}")
            raise
        finally:
            cursor.close()
