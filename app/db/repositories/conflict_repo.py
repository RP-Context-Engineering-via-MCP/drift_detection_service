"""
ConflictRepository - Data access layer for conflict_snapshots table.

Provides methods to query and retrieve ConflictRecord objects from the database.
"""

import logging
from typing import List
from datetime import datetime

from app.models.behavior import ConflictRecord

logger = logging.getLogger(__name__)


class ConflictRepository:
    """Repository for accessing conflict snapshot data."""

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
        # Detect database type for parameter placeholder
        self._is_sqlite = "sqlite" in str(type(connection)).lower()
    
    def _adapt_query(self, query: str) -> str:
        """Convert PostgreSQL-style placeholders to SQLite if needed."""
        if self._is_sqlite:
            return query.replace("%s", "?")
        return query

    def get_conflicts_in_window(
        self, user_id: str, start_ts: int, end_ts: int
    ) -> List[ConflictRecord]:
        """
        Retrieve all conflicts for a user within a time window.

        Args:
            user_id: User identifier
            start_ts: Window start timestamp (seconds since epoch)
            end_ts: Window end timestamp (seconds since epoch)

        Returns:
            List of ConflictRecord objects (empty list if none found)
        """
        query = """
            SELECT 
                user_id, conflict_id, conflict_type, behavior_id_1, behavior_id_2,
                old_target, new_target, old_polarity, new_polarity,
                resolution_status, created_at
            FROM conflict_snapshots
            WHERE user_id = %s
              AND created_at BETWEEN %s AND %s
            ORDER BY created_at ASC
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id, start_ts, end_ts))
            rows = cursor.fetchall()
            cursor.close()

            conflicts = []
            for row in rows:
                conflict = ConflictRecord(
                    user_id=row[0],
                    conflict_id=row[1],
                    conflict_type=row[2],
                    behavior_id_1=row[3],
                    behavior_id_2=row[4],
                    old_target=row[5],
                    new_target=row[6],
                    old_polarity=row[7],
                    new_polarity=row[8],
                    resolution_status=row[9],
                    created_at=row[10],
                )
                conflicts.append(conflict)

            logger.debug(
                f"Retrieved {len(conflicts)} conflicts for user {user_id} "
                f"in window [{start_ts}, {end_ts}]"
            )
            return conflicts

        except Exception as e:
            logger.error(f"Error retrieving conflicts: {e}")
            raise

    def get_polarity_reversals(
        self, user_id: str, start_ts: int, end_ts: int
    ) -> List[ConflictRecord]:
        """
        Retrieve conflicts that represent polarity reversals.

        A polarity reversal occurs when old_polarity != new_polarity
        (e.g., POSITIVE → NEGATIVE or vice versa).

        Args:
            user_id: User identifier
            start_ts: Window start timestamp
            end_ts: Window end timestamp

        Returns:
            List of ConflictRecord objects that are polarity reversals
        """
        query = """
            SELECT 
                user_id, conflict_id, conflict_type, behavior_id_1, behavior_id_2,
                old_target, new_target, old_polarity, new_polarity,
                resolution_status, created_at
            FROM conflict_snapshots
            WHERE user_id = %s
              AND created_at BETWEEN %s AND %s
              AND old_polarity IS NOT NULL
              AND new_polarity IS NOT NULL
              AND old_polarity != new_polarity
            ORDER BY created_at ASC
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id, start_ts, end_ts))
            rows = cursor.fetchall()
            cursor.close()

            conflicts = []
            for row in rows:
                conflict = ConflictRecord(
                    user_id=row[0],
                    conflict_id=row[1],
                    conflict_type=row[2],
                    behavior_id_1=row[3],
                    behavior_id_2=row[4],
                    old_target=row[5],
                    new_target=row[6],
                    old_polarity=row[7],
                    new_polarity=row[8],
                    resolution_status=row[9],
                    created_at=row[10],
                )
                conflicts.append(conflict)

            logger.debug(
                f"Retrieved {len(conflicts)} polarity reversals for user {user_id}"
            )
            return conflicts

        except Exception as e:
            logger.error(f"Error retrieving polarity reversals: {e}")
            raise

    def get_target_migrations(
        self, user_id: str, start_ts: int, end_ts: int
    ) -> List[ConflictRecord]:
        """
        Retrieve conflicts that represent target migrations.

        A target migration occurs when old_target != new_target
        (e.g., "vim" → "vscode").

        Args:
            user_id: User identifier
            start_ts: Window start timestamp
            end_ts: Window end timestamp

        Returns:
            List of ConflictRecord objects that are target migrations
        """
        query = """
            SELECT 
                user_id, conflict_id, conflict_type, behavior_id_1, behavior_id_2,
                old_target, new_target, old_polarity, new_polarity,
                resolution_status, created_at
            FROM conflict_snapshots
            WHERE user_id = %s
              AND created_at BETWEEN %s AND %s
              AND old_target IS NOT NULL
              AND new_target IS NOT NULL
              AND old_target != new_target
            ORDER BY created_at ASC
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id, start_ts, end_ts))
            rows = cursor.fetchall()
            cursor.close()

            conflicts = []
            for row in rows:
                conflict = ConflictRecord(
                    user_id=row[0],
                    conflict_id=row[1],
                    conflict_type=row[2],
                    behavior_id_1=row[3],
                    behavior_id_2=row[4],
                    old_target=row[5],
                    new_target=row[6],
                    old_polarity=row[7],
                    new_polarity=row[8],
                    resolution_status=row[9],
                    created_at=row[10],
                )
                conflicts.append(conflict)

            logger.debug(
                f"Retrieved {len(conflicts)} target migrations for user {user_id}"
            )
            return conflicts

        except Exception as e:
            logger.error(f"Error retrieving target migrations: {e}")
            raise

    def get_all_conflicts(self, user_id: str) -> List[ConflictRecord]:
        """
        Retrieve all conflicts for a user (no time filtering).

        Args:
            user_id: User identifier

        Returns:
            List of all ConflictRecord objects for the user
        """
        query = """
            SELECT 
                user_id, conflict_id, conflict_type, behavior_id_1, behavior_id_2,
                old_target, new_target, old_polarity, new_polarity,
                resolution_status, created_at
            FROM conflict_snapshots
            WHERE user_id = %s
            ORDER BY created_at DESC
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id,))
            rows = cursor.fetchall()
            cursor.close()

            conflicts = []
            for row in rows:
                conflict = ConflictRecord(
                    user_id=row[0],
                    conflict_id=row[1],
                    conflict_type=row[2],
                    behavior_id_1=row[3],
                    behavior_id_2=row[4],
                    old_target=row[5],
                    new_target=row[6],
                    old_polarity=row[7],
                    new_polarity=row[8],
                    resolution_status=row[9],
                    created_at=row[10],
                )
                conflicts.append(conflict)

            logger.debug(f"Retrieved {len(conflicts)} total conflicts for user {user_id}")
            return conflicts

        except Exception as e:
            logger.error(f"Error retrieving all conflicts: {e}")
            raise
