"""
ScanJobRepository - Data access layer for drift_scan_jobs table.

Provides methods to manage drift scan job lifecycle:
- Enqueue new scan jobs
- Retrieve pending jobs for processing
- Update job status
- Check for existing pending jobs
- Get last scan time for cooldown enforcement
"""

import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def now() -> int:
    """Get current UTC timestamp as integer."""
    return int(datetime.now(timezone.utc).timestamp())


class ScanJobRepository:
    """Repository for managing drift scan job data."""

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

    def enqueue(
        self,
        user_id: str,
        trigger_event: str,
        priority: str = "NORMAL"
    ) -> str:
        """
        Enqueue a new drift scan job.

        Args:
            user_id: User ID to scan
            trigger_event: Event that triggered the scan (e.g., "behavior.created")
            priority: Job priority (NORMAL, HIGH, LOW)

        Returns:
            job_id (str) of the enqueued job
        """
        job_id = str(uuid.uuid4())
        scheduled_at = now()

        query = """
            INSERT INTO drift_scan_jobs (
                job_id, user_id, trigger_event, status, priority, scheduled_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            )
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                self._adapt_query(query),
                (job_id, user_id, trigger_event, "PENDING", priority, scheduled_at)
            )
            
            logger.info(
                f"Enqueued scan job {job_id} for user {user_id} "
                f"(trigger: {trigger_event}, priority: {priority})"
            )
            
            return job_id

        except Exception as e:
            logger.error(f"Failed to enqueue scan job for user {user_id}: {e}")
            raise

    def get_pending_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve pending scan jobs ordered by priority and scheduled time.

        Jobs with HIGH priority are returned first, followed by NORMAL and LOW.
        Within the same priority, older jobs are returned first (FIFO).

        Args:
            limit: Maximum number of jobs to retrieve

        Returns:
            List of job dictionaries
        """
        query = """
            SELECT 
                job_id, user_id, trigger_event, status, priority, 
                scheduled_at, started_at, completed_at, error_message
            FROM drift_scan_jobs
            WHERE status = 'PENDING'
            ORDER BY 
                CASE priority
                    WHEN 'HIGH' THEN 1
                    WHEN 'NORMAL' THEN 2
                    WHEN 'LOW' THEN 3
                    ELSE 4
                END,
                scheduled_at ASC
            LIMIT %s
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (limit,))
            
            rows = cursor.fetchall()
            
            jobs = []
            for row in rows:
                jobs.append({
                    "job_id": str(row[0]),
                    "user_id": row[1],
                    "trigger_event": row[2],
                    "status": row[3],
                    "priority": row[4],
                    "scheduled_at": row[5],
                    "started_at": row[6],
                    "completed_at": row[7],
                    "error_message": row[8],
                })
            
            return jobs

        except Exception as e:
            logger.error(f"Failed to get pending jobs: {e}")
            raise

    def update_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update the status of a scan job.

        Args:
            job_id: Job ID to update
            status: New status (PENDING, RUNNING, DONE, FAILED, SKIPPED)
            error_message: Optional error message for FAILED status
        """
        timestamp = now()
        
        # Determine which timestamp field to update
        if status == "RUNNING":
            query = """
                UPDATE drift_scan_jobs
                SET status = %s, started_at = %s
                WHERE job_id = %s
            """
            params = (status, timestamp, job_id)
        elif status in ("DONE", "FAILED", "SKIPPED"):
            query = """
                UPDATE drift_scan_jobs
                SET status = %s, completed_at = %s, error_message = %s
                WHERE job_id = %s
            """
            params = (status, timestamp, error_message, job_id)
        else:
            query = """
                UPDATE drift_scan_jobs
                SET status = %s
                WHERE job_id = %s
            """
            params = (status, job_id)

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), params)
            
            logger.debug(f"Updated job {job_id} status to {status}")

        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            raise

    def has_pending_job(self, user_id: str) -> bool:
        """
        Check if there's already a pending job for this user.

        Used to prevent duplicate scans in the queue.

        Args:
            user_id: User ID to check

        Returns:
            True if a pending job exists, False otherwise
        """
        query = """
            SELECT COUNT(*) 
            FROM drift_scan_jobs
            WHERE user_id = %s AND status = 'PENDING'
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id,))
            
            count = cursor.fetchone()[0]
            return count > 0

        except Exception as e:
            logger.error(f"Failed to check pending jobs for user {user_id}: {e}")
            raise

    def get_last_completed_scan(self, user_id: str) -> Optional[int]:
        """
        Get the timestamp of the last completed scan for a user.

        Used to enforce cooldown periods between scans.

        Args:
            user_id: User ID to check

        Returns:
            Timestamp of last completed scan, or None if no scans exist
        """
        query = """
            SELECT completed_at
            FROM drift_scan_jobs
            WHERE user_id = %s AND status = 'DONE'
            ORDER BY completed_at DESC
            LIMIT 1
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id,))
            
            row = cursor.fetchone()
            return row[0] if row else None

        except Exception as e:
            logger.error(f"Failed to get last scan time for user {user_id}: {e}")
            raise

    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific job by its ID.

        Args:
            job_id: Job ID to retrieve

        Returns:
            Job dictionary, or None if not found
        """
        query = """
            SELECT 
                job_id, user_id, trigger_event, status, priority, 
                scheduled_at, started_at, completed_at, error_message
            FROM drift_scan_jobs
            WHERE job_id = %s
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (job_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                "job_id": str(row[0]),
                "user_id": row[1],
                "trigger_event": row[2],
                "status": row[3],
                "priority": row[4],
                "scheduled_at": row[5],
                "started_at": row[6],
                "completed_at": row[7],
                "error_message": row[8],
            }

        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise

    def get_user_job_history(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get job history for a specific user.

        Args:
            user_id: User ID
            limit: Maximum number of jobs to retrieve

        Returns:
            List of job dictionaries, sorted by scheduled time (newest first)
        """
        query = """
            SELECT 
                job_id, user_id, trigger_event, status, priority, 
                scheduled_at, started_at, completed_at, error_message
            FROM drift_scan_jobs
            WHERE user_id = %s
            ORDER BY scheduled_at DESC
            LIMIT %s
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(self._adapt_query(query), (user_id, limit))
            
            rows = cursor.fetchall()
            
            jobs = []
            for row in rows:
                jobs.append({
                    "job_id": str(row[0]),
                    "user_id": row[1],
                    "trigger_event": row[2],
                    "status": row[3],
                    "priority": row[4],
                    "scheduled_at": row[5],
                    "started_at": row[6],
                    "completed_at": row[7],
                    "error_message": row[8],
                })
            
            return jobs

        except Exception as e:
            logger.error(f"Failed to get job history for user {user_id}: {e}")
            raise

    def count_jobs_by_status(self) -> Dict[str, int]:
        """
        Get count of jobs grouped by status.

        Returns:
            Dictionary mapping status to count
        """
        query = """
            SELECT status, COUNT(*) as count
            FROM drift_scan_jobs
            GROUP BY status
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            
            rows = cursor.fetchall()
            
            return {row[0]: row[1] for row in rows}

        except Exception as e:
            logger.error(f"Failed to count jobs by status: {e}")
            raise

    def get_all_scannable_users(
        self,
        active_since: int,
        moderate_since: int
    ) -> Dict[str, List[str]]:
        """
        Get users eligible for scheduled scans, grouped by activity tier.

        Users are classified as:
        - active: Has behaviors after active_since timestamp
        - moderate: Has behaviors after moderate_since but before active_since
        - dormant: No behaviors after moderate_since (not returned)

        Args:
            active_since: Unix timestamp - users active after this are "active"
            moderate_since: Unix timestamp - users active after this are "moderate" or "active"

        Returns:
            Dictionary with 'active' and 'moderate' keys containing user ID lists
        """
        # Get active users (activity within active threshold)
        active_query = """
            SELECT DISTINCT user_id
            FROM behavior_snapshots
            WHERE last_seen_at >= %s
            AND state = 'ACTIVE'
        """

        # Get moderate users (activity within moderate threshold but not active)
        moderate_query = """
            SELECT DISTINCT user_id
            FROM behavior_snapshots
            WHERE last_seen_at >= %s
            AND last_seen_at < %s
            AND state = 'ACTIVE'
        """

        try:
            cursor = self.connection.cursor()
            
            # Get active users
            cursor.execute(self._adapt_query(active_query), (active_since,))
            active_users = [row[0] for row in cursor.fetchall()]
            
            # Get moderate users
            cursor.execute(
                self._adapt_query(moderate_query),
                (moderate_since, active_since)
            )
            moderate_users = [row[0] for row in cursor.fetchall()]
            
            logger.debug(
                f"Found {len(active_users)} active users and "
                f"{len(moderate_users)} moderate users for scheduled scan"
            )
            
            return {
                "active": active_users,
                "moderate": moderate_users
            }

        except Exception as e:
            logger.error(f"Failed to get scannable users: {e}")
            raise
