"""
DriftEventRepository - Data access layer for drift_events table.

Provides methods to persist and retrieve DriftEvent objects.
"""

import logging
import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.drift import DriftEvent, DriftType, DriftSeverity

logger = logging.getLogger(__name__)


class DriftEventRepository:
    """Repository for managing drift event data."""

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

    def insert(self, drift_event: DriftEvent) -> str:
        """
        Insert a new drift event into the database.

        Args:
            drift_event: DriftEvent object to persist

        Returns:
            drift_event_id (str) of the inserted event
        """
        # Generate ID if not present or looks like a default UUID
        # (containing dashes, indicating it wasn't manually set)
        if not drift_event.drift_event_id or "-" in drift_event.drift_event_id:
            drift_event.drift_event_id = f"drift_{uuid.uuid4().hex[:12]}"

        query = """
            INSERT INTO drift_events (
                drift_event_id, user_id, drift_type, drift_score, severity,
                affected_targets, evidence, confidence,
                reference_window_start, reference_window_end,
                current_window_start, current_window_end,
                detected_at, acknowledged_at,
                behavior_ref_ids, conflict_ref_ids
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s
            )
        """

        try:
            cursor = self.connection.cursor()
            
            # For PostgreSQL: pass lists directly, psycopg2 handles conversion
            # For SQLite: serialize to JSON strings
            if self._is_sqlite:
                affected_targets = json.dumps(drift_event.affected_targets)
                evidence = json.dumps(drift_event.evidence)
                behavior_ref_ids = json.dumps(drift_event.behavior_ref_ids or [])
                conflict_ref_ids = json.dumps(drift_event.conflict_ref_ids or [])
            else:
                # PostgreSQL: pass native lists and dicts
                affected_targets = drift_event.affected_targets
                evidence = json.dumps(drift_event.evidence)  # JSONB still needs JSON
                behavior_ref_ids = drift_event.behavior_ref_ids or []
                conflict_ref_ids = drift_event.conflict_ref_ids or []
            
            cursor.execute(
                self._adapt_query(query),
                (
                    drift_event.drift_event_id,
                    drift_event.user_id,
                    drift_event.drift_type.value,
                    drift_event.drift_score,
                    drift_event.severity.value,
                    affected_targets,
                    evidence,
                    drift_event.confidence,
                    drift_event.reference_window_start,
                    drift_event.reference_window_end,
                    drift_event.current_window_start,
                    drift_event.current_window_end,
                    drift_event.detected_at,
                    drift_event.acknowledged_at,
                    behavior_ref_ids,
                    conflict_ref_ids,
                ),
            )
            self.connection.commit()
            cursor.close()

            logger.info(
                f"Inserted drift event {drift_event.drift_event_id} "
                f"for user {drift_event.user_id}: {drift_event.drift_type.value}"
            )
            return drift_event.drift_event_id

        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error inserting drift event: {e}")
            raise

    def get_by_id(self, drift_event_id: str) -> Optional[DriftEvent]:
        """
        Retrieve a drift event by its ID.

        Args:
            drift_event_id: Unique identifier for the drift event

        Returns:
            DriftEvent object, or None if not found
        """
        query = """
            SELECT 
                drift_event_id, user_id, drift_type, drift_score, severity,
                affected_targets, evidence, confidence,
                reference_window_start, reference_window_end,
                current_window_start, current_window_end,
                detected_at, acknowledged_at,
                behavior_ref_ids, conflict_ref_ids
            FROM drift_events
            WHERE drift_event_id = %s
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (drift_event_id,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                logger.debug(f"No drift event found with ID: {drift_event_id}")
                return None

            event = self._row_to_drift_event(row)
            return event

        except Exception as e:
            logger.error(f"Error retrieving drift event by ID: {e}")
            raise

    def get_by_user(
        self,
        user_id: str,
        drift_type: Optional[DriftType] = None,
        severity: Optional[DriftSeverity] = None,
        start_date: Optional[int] = None,
        end_date: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DriftEvent]:
        """
        Retrieve drift events for a user with optional filters.

        Args:
            user_id: User identifier
            drift_type: Optional filter by drift type
            severity: Optional filter by severity level
            start_date: Optional filter by detected_at >= start_date
            end_date: Optional filter by detected_at <= end_date
            limit: Maximum number of results (default: 100)
            offset: Number of results to skip (default: 0)

        Returns:
            List of DriftEvent objects matching the criteria
        """
        # Build dynamic query
        query = """
            SELECT 
                drift_event_id, user_id, drift_type, drift_score, severity,
                affected_targets, evidence, confidence,
                reference_window_start, reference_window_end,
                current_window_start, current_window_end,
                detected_at, acknowledged_at,
                behavior_ref_ids, conflict_ref_ids
            FROM drift_events
            WHERE user_id = %s
        """

        params = [user_id]

        if drift_type:
            query += " AND drift_type = %s"
            params.append(drift_type.value)

        if severity:
            query += " AND severity = %s"
            params.append(severity.value)

        if start_date:
            query += " AND detected_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND detected_at <= %s"
            params.append(end_date)

        query += " ORDER BY detected_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), tuple(params))
            rows = cursor.fetchall()
            cursor.close()

            events = [self._row_to_drift_event(row) for row in rows]
            logger.debug(f"Retrieved {len(events)} drift events for user {user_id}")
            return events

        except Exception as e:
            logger.error(f"Error retrieving drift events by user: {e}")
            raise

    def get_latest_detection_time(self, user_id: str) -> Optional[int]:
        """
        Get the timestamp of the most recent drift detection for a user.

        Used for cooldown enforcement.

        Args:
            user_id: User identifier

        Returns:
            Latest detected_at timestamp, or None if no events exist
        """
        query = """
            SELECT MAX(detected_at)
            FROM drift_events
            WHERE user_id = %s
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id,))
            result = cursor.fetchone()[0]
            cursor.close()

            if result:
                logger.debug(f"Latest detection for user {user_id}: {result}")
            else:
                logger.debug(f"No drift events found for user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Error getting latest detection time: {e}")
            raise

    def update_acknowledged(self, drift_event_id: str, timestamp: int) -> bool:
        """
        Mark a drift event as acknowledged.

        Args:
            drift_event_id: Drift event identifier
            timestamp: Acknowledgment timestamp (seconds since epoch)

        Returns:
            True if updated successfully, False if event not found
        """
        query = """
            UPDATE drift_events
            SET acknowledged_at = %s
            WHERE drift_event_id = %s
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (timestamp, drift_event_id))
            rows_affected = cursor.rowcount
            self.connection.commit()
            cursor.close()

            if rows_affected > 0:
                logger.info(f"Acknowledged drift event {drift_event_id}")
                return True
            else:
                logger.warning(f"Drift event {drift_event_id} not found for acknowledgment")
                return False

        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error updating acknowledgment: {e}")
            raise

    def _row_to_drift_event(self, row: tuple) -> DriftEvent:
        """
        Convert a database row to a DriftEvent object.

        Args:
            row: Tuple of database row values

        Returns:
            DriftEvent object
        """
        # Parse affected_targets (could be JSON string or list)
        affected_targets = row[5]
        if isinstance(affected_targets, str):
            affected_targets = json.loads(affected_targets)
        
        # Parse evidence (could be JSON string or dict)
        evidence = row[6]
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        
        # Parse behavior_ ref_ids (could be JSON string or list)
        behavior_ref_ids = row[14] or []
        if isinstance(behavior_ref_ids, str):
            behavior_ref_ids = json.loads(behavior_ref_ids)
        
        # Parse conflict_ref_ids (could be JSON string or list)
        conflict_ref_ids = row[15] or []
        if isinstance(conflict_ref_ids, str):
            conflict_ref_ids = json.loads(conflict_ref_ids)
        
        return DriftEvent(
            user_id=row[1],
            drift_type=DriftType(row[2]),
            drift_score=row[3],
            confidence=row[7],
            severity=DriftSeverity(row[4]),
            affected_targets=affected_targets,
            evidence=evidence,
            reference_window_start=row[8],
            reference_window_end=row[9],
            current_window_start=row[10],
            current_window_end=row[11],
            detected_at=row[12],
            drift_event_id=row[0],
            acknowledged_at=row[13],
            behavior_ref_ids=behavior_ref_ids,
            conflict_ref_ids=conflict_ref_ids,
        )
