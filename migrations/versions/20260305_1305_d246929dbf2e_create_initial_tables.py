"""create_initial_tables

Revision ID: d246929dbf2e
Revises: 
Create Date: 2026-03-05 13:05:42.688245+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd246929dbf2e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create all tables."""
    
    # Create behavior_snapshots table
    op.execute("""
        CREATE TABLE IF NOT EXISTS behavior_snapshots (
            user_id VARCHAR(255) NOT NULL,
            behavior_id VARCHAR(255) PRIMARY KEY,
            target VARCHAR(255) NOT NULL,
            intent VARCHAR(50) NOT NULL,
            context VARCHAR(255) NOT NULL,
            polarity VARCHAR(20) NOT NULL,
            credibility DECIMAL(3,2) NOT NULL,
            reinforcement_count INTEGER NOT NULL,
            state VARCHAR(20) NOT NULL,
            created_at BIGINT NOT NULL,
            last_seen_at BIGINT NOT NULL,
            snapshot_updated_at BIGINT NOT NULL
        )
    """)
    
    # Create indexes for behavior_snapshots
    op.execute("CREATE INDEX IF NOT EXISTS idx_behavior_user_id ON behavior_snapshots(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_behavior_target ON behavior_snapshots(target)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_behavior_created_at ON behavior_snapshots(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_behavior_last_seen_at ON behavior_snapshots(last_seen_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_behavior_state ON behavior_snapshots(state)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_behavior_window_lookup 
        ON behavior_snapshots(user_id, created_at, last_seen_at)
    """)
    
    # Create conflict_snapshots table
    op.execute("""
        CREATE TABLE IF NOT EXISTS conflict_snapshots (
            conflict_id VARCHAR(255) PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            behavior_id_1 VARCHAR(255) NOT NULL,
            behavior_id_2 VARCHAR(255) NOT NULL,
            conflict_type VARCHAR(50) NOT NULL,
            resolution_status VARCHAR(50) NOT NULL,
            old_polarity VARCHAR(20),
            new_polarity VARCHAR(20),
            old_target VARCHAR(255),
            new_target VARCHAR(255),
            created_at BIGINT NOT NULL
        )
    """)
    
    # Create indexes for conflict_snapshots
    op.execute("CREATE INDEX IF NOT EXISTS idx_conflict_user_id ON conflict_snapshots(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_conflict_type ON conflict_snapshots(conflict_type)")
    
    # Create drift_events table
    op.execute("""
        CREATE TABLE IF NOT EXISTS drift_events (
            drift_event_id VARCHAR(255) PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            drift_type VARCHAR(50) NOT NULL,
            drift_score DECIMAL(3,2) NOT NULL,
            confidence DECIMAL(3,2) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            affected_targets TEXT[],
            evidence JSONB,
            reference_window_start BIGINT NOT NULL,
            reference_window_end BIGINT NOT NULL,
            current_window_start BIGINT NOT NULL,
            current_window_end BIGINT NOT NULL,
            detected_at BIGINT NOT NULL,
            acknowledged_at BIGINT,
            behavior_ref_ids TEXT[],
            conflict_ref_ids TEXT[]
        )
    """)
    
    # Create indexes for drift_events
    op.execute("CREATE INDEX IF NOT EXISTS idx_drift_user_id ON drift_events(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_drift_type ON drift_events(drift_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_drift_severity ON drift_events(severity)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_drift_detected_at ON drift_events(detected_at)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_drift_user_type_detected 
        ON drift_events(user_id, drift_type, detected_at DESC)
    """)
    
    # Create drift_scan_jobs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS drift_scan_jobs (
            job_id VARCHAR(255) PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            status VARCHAR(20) NOT NULL,
            trigger_event VARCHAR(100),
            created_at BIGINT NOT NULL,
            started_at BIGINT,
            completed_at BIGINT,
            error_message TEXT
        )
    """)
    
    # Create indexes for drift_scan_jobs
    op.execute("CREATE INDEX IF NOT EXISTS idx_job_status ON drift_scan_jobs(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_job_user_id ON drift_scan_jobs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_job_created_at ON drift_scan_jobs(created_at)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_job_pending 
        ON drift_scan_jobs(status, created_at) 
        WHERE status = 'PENDING'
    """)


def downgrade() -> None:
    """Downgrade schema - drop all tables."""
    
    # Drop tables in reverse order
    op.execute("DROP TABLE IF EXISTS drift_scan_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS drift_events CASCADE")
    op.execute("DROP TABLE IF EXISTS conflict_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS behavior_snapshots CASCADE")

