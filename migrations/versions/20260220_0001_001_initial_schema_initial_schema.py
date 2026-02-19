"""Initial schema - Create all drift detection tables

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-02-20

Creates the following tables:
- behavior_snapshots: Local projection of behaviors from Behavior Service
- conflict_snapshots: Local projection of resolved conflicts
- drift_events: Detected behavioral drift events
- drift_scan_jobs: Queue for scheduled drift detection jobs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all drift detection tables."""
    
    # ═══════════════════════════════════════════════════════════════════════
    # Behavior Snapshots Table
    # ═══════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS behavior_snapshots (
            user_id              TEXT NOT NULL,
            behavior_id          TEXT NOT NULL,
            target               TEXT NOT NULL,
            intent               TEXT NOT NULL,
            context              TEXT NOT NULL,
            polarity             TEXT NOT NULL,
            credibility          REAL NOT NULL,
            reinforcement_count  INTEGER NOT NULL,
            state                TEXT NOT NULL,
            created_at           BIGINT NOT NULL,
            last_seen_at         BIGINT NOT NULL,
            snapshot_updated_at  BIGINT NOT NULL,
            
            PRIMARY KEY (user_id, behavior_id)
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bsnap_user_target 
            ON behavior_snapshots(user_id, target)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bsnap_user_state 
            ON behavior_snapshots(user_id, state)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bsnap_last_seen 
            ON behavior_snapshots(user_id, last_seen_at)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bsnap_created 
            ON behavior_snapshots(user_id, created_at)
    """)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Conflict Snapshots Table
    # ═══════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS conflict_snapshots (
            user_id            TEXT NOT NULL,
            conflict_id        TEXT NOT NULL,
            behavior_id_1      TEXT NOT NULL,
            behavior_id_2      TEXT NOT NULL,
            conflict_type      TEXT NOT NULL,
            resolution_status  TEXT NOT NULL,
            old_polarity       TEXT,
            new_polarity       TEXT,
            old_target         TEXT,
            new_target         TEXT,
            created_at         BIGINT NOT NULL,
            
            PRIMARY KEY (user_id, conflict_id)
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_csnap_user_created 
            ON conflict_snapshots(user_id, created_at)
    """)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Drift Events Table
    # ═══════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS drift_events (
            drift_event_id          TEXT PRIMARY KEY,
            user_id                 TEXT NOT NULL,
            drift_type              TEXT NOT NULL,
            drift_score             REAL NOT NULL,
            confidence              REAL NOT NULL,
            severity                TEXT NOT NULL,
            affected_targets        TEXT[] NOT NULL,
            evidence                JSONB NOT NULL,
            reference_window_start  BIGINT NOT NULL,
            reference_window_end    BIGINT NOT NULL,
            current_window_start    BIGINT NOT NULL,
            current_window_end      BIGINT NOT NULL,
            detected_at             BIGINT NOT NULL,
            acknowledged_at         BIGINT,
            behavior_ref_ids        TEXT[],
            conflict_ref_ids        TEXT[]
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_drift_user_detected 
            ON drift_events(user_id, detected_at)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_drift_type 
            ON drift_events(drift_type)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_drift_severity 
            ON drift_events(severity)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_drift_user_type 
            ON drift_events(user_id, drift_type)
    """)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Drift Scan Jobs Table
    # ═══════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE TABLE IF NOT EXISTS drift_scan_jobs (
            job_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id          TEXT NOT NULL,
            trigger_event    TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'PENDING',
            priority         TEXT NOT NULL DEFAULT 'NORMAL',
            scheduled_at     BIGINT NOT NULL,
            started_at       BIGINT,
            completed_at     BIGINT,
            error_message    TEXT,
            
            CONSTRAINT valid_status CHECK (status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED', 'SKIPPED'))
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_scan_jobs_user_status 
            ON drift_scan_jobs(user_id, status)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_scan_jobs_status_scheduled 
            ON drift_scan_jobs(status, scheduled_at)
    """)


def downgrade() -> None:
    """Drop all drift detection tables."""
    op.execute("DROP TABLE IF EXISTS drift_scan_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS drift_events CASCADE")
    op.execute("DROP TABLE IF EXISTS conflict_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS behavior_snapshots CASCADE")
