"""
API Dependencies

Dependency injection for FastAPI
"""

from typing import Generator
from functools import lru_cache
import psycopg2
from psycopg2 import pool
from urllib.parse import urlparse

from app.config import get_settings, Settings
from app.core.drift_detector import DriftDetector
from app.db.connection import get_sync_connection


# ============================================================================
# Configuration
# ============================================================================

@lru_cache
def get_api_settings() -> Settings:
    """Get cached settings instance"""
    return get_settings()


# ============================================================================
# Database Connection
# ============================================================================

_connection_pool = None


def parse_database_url(database_url: str) -> dict:
    """Parse database URL into connection parameters"""
    parsed = urlparse(database_url)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip('/'),
        "user": parsed.username,
        "password": parsed.password
    }


def get_db_pool():
    """Get or create database connection pool"""
    global _connection_pool
    if _connection_pool is None:
        settings = get_api_settings()
        conn_params = parse_database_url(settings.database_url)
        _connection_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            **conn_params
        )
    return _connection_pool


def get_db_connection() -> Generator:
    """
    Dependency for database connection
    
    Yields connection from pool and returns it after use
    """
    db_pool = get_db_pool()
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)


# ============================================================================
# Drift Detector
# ============================================================================

@lru_cache
def get_drift_detector() -> DriftDetector:
    """Get cached drift detector instance"""
    return DriftDetector()


# ============================================================================
# Cleanup
# ============================================================================

def close_db_pool():
    """Close database connection pool (called on shutdown)"""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
