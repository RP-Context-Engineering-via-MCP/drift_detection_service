"""
Database connection management.

Handles PostgreSQL/Supabase connections and table creation.
"""

import asyncpg
import psycopg2
from psycopg2 import pool
from datetime import datetime, timezone
from typing import Optional, Union
from contextlib import asynccontextmanager, contextmanager

from app.config import get_settings
from app.utils.time import now  # Centralized time utility

# Global connection pool
_async_pool: Optional[asyncpg.Pool] = None
_sync_pool: Optional[pool.SimpleConnectionPool] = None


# ─── Async Database Connection (asyncpg) ─────────────────────────────────

async def get_async_pool() -> asyncpg.Pool:
    """
    Get or create the asyncpg connection pool.
    
    Returns:
        asyncpg connection pool
    """
    global _async_pool
    
    if _async_pool is None:
        settings = get_settings()
        _async_pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=settings.db_pool_size,
            command_timeout=settings.db_pool_timeout,
        )
    
    return _async_pool


async def close_async_pool() -> None:
    """Close the asyncpg connection pool."""
    global _async_pool
    
    if _async_pool is not None:
        await _async_pool.close()
        _async_pool = None


@asynccontextmanager
async def get_async_connection():
    """
    Get an async database connection from the pool.
    
    Usage:
        async with get_async_connection() as conn:
            result = await conn.fetch("SELECT * FROM table")
    
    Yields:
        asyncpg.Connection
    """
    pool = await get_async_pool()
    async with pool.acquire() as connection:
        yield connection


# ─── Sync Database Connection (psycopg2) ─────────────────────────────────

def get_sync_pool() -> pool.SimpleConnectionPool:
    """
    Get or create the psycopg2 connection pool.
    
    Returns:
        psycopg2 connection pool
    """
    global _sync_pool
    
    if _sync_pool is None:
        settings = get_settings()
        _sync_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=settings.db_pool_size,
            dsn=settings.database_url,
        )
    
    return _sync_pool


def close_sync_pool() -> None:
    """Close the psycopg2 connection pool."""
    global _sync_pool
    
    if _sync_pool is not None:
        _sync_pool.closeall()
        _sync_pool = None


@contextmanager
def get_sync_connection():
    """
    Get a sync database connection from the pool.
    
    Usage:
        with get_sync_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM table")
            result = cursor.fetchall()
    
    Yields:
        psycopg2.connection
    """
    pool = get_sync_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def get_sync_connection_simple():
    """
    Get a simple sync database connection (not from pool, for long-lived use).
    
    Returns:
        psycopg2.connection
    """
    settings = get_settings()
    conn = psycopg2.connect(dsn=settings.database_url)
    return conn


# ─── Universal Connection Interface ──────────────────────────────────────

def get_db_connection(async_mode: bool = False):
    """
    Get a database connection (sync or async).
    
    Args:
        async_mode: If True, returns async context manager, else sync
        
    Returns:
        Context manager for database connection
    """
    if async_mode:
        return get_async_connection()
    else:
        return get_sync_connection()


# ─── Database Schema Creation ────────────────────────────────────────────

def create_tables() -> None:
    """
    Create all required database tables for drift detection.
    
    This creates:
    - behavior_snapshots: Local projection of behaviors
    - conflict_snapshots: Local projection of conflicts
    - drift_events: Detected drift events
    
    Safe to call multiple times (uses IF NOT EXISTS).
    """
    
    schema_sql = """
    -- ═══════════════════════════════════════════════════════════════════════
    -- Behavior Snapshots Table
    -- ═══════════════════════════════════════════════════════════════════════
    
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
    );
    
    CREATE INDEX IF NOT EXISTS idx_bsnap_user_target 
        ON behavior_snapshots(user_id, target);
    
    CREATE INDEX IF NOT EXISTS idx_bsnap_user_state 
        ON behavior_snapshots(user_id, state);
    
    CREATE INDEX IF NOT EXISTS idx_bsnap_last_seen 
        ON behavior_snapshots(user_id, last_seen_at);
    
    CREATE INDEX IF NOT EXISTS idx_bsnap_created 
        ON behavior_snapshots(user_id, created_at);
    
    -- ═══════════════════════════════════════════════════════════════════════
    -- Conflict Snapshots Table
    -- ═══════════════════════════════════════════════════════════════════════
    
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
    );
    
    CREATE INDEX IF NOT EXISTS idx_csnap_user_created 
        ON conflict_snapshots(user_id, created_at);
    
    -- ═══════════════════════════════════════════════════════════════════════
    -- Drift Events Table
    -- ═══════════════════════════════════════════════════════════════════════
    
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
    );
    
    CREATE INDEX IF NOT EXISTS idx_drift_user_detected 
        ON drift_events(user_id, detected_at);
    
    CREATE INDEX IF NOT EXISTS idx_drift_type 
        ON drift_events(drift_type);
    
    CREATE INDEX IF NOT EXISTS idx_drift_severity 
        ON drift_events(severity);
    
    CREATE INDEX IF NOT EXISTS idx_drift_user_type 
        ON drift_events(user_id, drift_type);
    
    -- ═══════════════════════════════════════════════════════════════════════
    -- Drift Scan Jobs Table
    -- ═══════════════════════════════════════════════════════════════════════
    
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
    );
    
    CREATE INDEX IF NOT EXISTS idx_scan_jobs_user_status 
        ON drift_scan_jobs(user_id, status);
    
    CREATE INDEX IF NOT EXISTS idx_scan_jobs_status_scheduled 
        ON drift_scan_jobs(status, scheduled_at);
    """
    
    print("Creating database tables...")
    
    with get_sync_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(schema_sql)
        conn.commit()
    
    print("✅ Database tables created successfully!")


def drop_tables() -> None:
    """
    Drop all drift detection tables.
    
    WARNING: This will delete all data!
    Use only for testing or complete resets.
    """
    
    drop_sql = """
    DROP TABLE IF EXISTS drift_scan_jobs CASCADE;
    DROP TABLE IF EXISTS drift_events CASCADE;
    DROP TABLE IF EXISTS conflict_snapshots CASCADE;
    DROP TABLE IF EXISTS behavior_snapshots CASCADE;
    """
    
    print("⚠️  Dropping all drift detection tables...")
    
    try:
        with get_sync_connection() as conn:
            # Set a reasonable statement timeout for drops
            cursor = conn.cursor()
            cursor.execute("SET statement_timeout = '10s'")
            cursor.execute(drop_sql)
            conn.commit()
        
        print("✅ All tables dropped!")
    except Exception as e:
        print(f"⚠️  Warning: Error dropping tables: {e}")
        # Don't raise - this is cleanup code


def clear_all_data() -> None:
    """
    Clear all data from drift detection tables without dropping them.
    
    Useful for test cleanup - much faster than drop/create cycle.
    """
    clear_sql = """
    DELETE FROM drift_scan_jobs;
    DELETE FROM drift_events;
    DELETE FROM conflict_snapshots;
    DELETE FROM behavior_snapshots;
    """
    
    with get_sync_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(clear_sql)
        conn.commit()


# ─── Database Health Check ───────────────────────────────────────────────

def check_database_health() -> bool:
    """
    Check if database is accessible and tables exist.
    
    Returns:
        True if database is healthy, False otherwise
    """
    try:
        with get_sync_connection() as conn:
            cursor = conn.cursor()
            
            # Check if main tables exist
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name IN (
                    'behavior_snapshots', 
                    'conflict_snapshots', 
                    'drift_events',
                    'drift_scan_jobs'
                )
            """)
            
            count = cursor.fetchone()[0]
            return count == 4
            
    except Exception as e:
        print(f"❌ Database health check failed: {e}")
        return False


# ─── Utility: Get Table Row Counts ──────────────────────────────────────

def get_table_stats() -> dict:
    """
    Get row counts for all drift detection tables.
    
    Returns:
        Dictionary with table names and row counts
    """
    stats = {}
    
    with get_sync_connection() as conn:
        cursor = conn.cursor()
        
        tables = ['behavior_snapshots', 'conflict_snapshots', 'drift_events']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats[table] = count
    
    return stats
