"""
Time utilities for Drift Detection Service.

Centralizes all time-related operations to ensure consistency
across the application.
"""

from datetime import datetime, timezone
from typing import Optional


def now() -> int:
    """
    Get current UTC time as a unix timestamp integer.
    
    Returns:
        Current timestamp as integer (seconds since epoch)
        
    Example:
        >>> ts = now()
        >>> isinstance(ts, int)
        True
    """
    return int(datetime.now(timezone.utc).timestamp())


def timestamp_to_datetime(timestamp: int) -> datetime:
    """
    Convert unix timestamp to timezone-aware datetime.
    
    Args:
        timestamp: Unix timestamp (seconds since epoch)
        
    Returns:
        Timezone-aware datetime object in UTC
        
    Example:
        >>> dt = timestamp_to_datetime(1609459200)
        >>> dt.year
        2021
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> int:
    """
    Convert datetime to unix timestamp.
    
    Args:
        dt: Datetime object (naive datetimes assumed to be UTC)
        
    Returns:
        Unix timestamp as integer
        
    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2021, 1, 1, tzinfo=timezone.utc)
        >>> datetime_to_timestamp(dt)
        1609459200
    """
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def days_ago(days: int) -> int:
    """
    Get timestamp for N days ago from now.
    
    Args:
        days: Number of days ago
        
    Returns:
        Unix timestamp for that point in time
    """
    return now() - (days * 86400)


def seconds_since(timestamp: int) -> int:
    """
    Calculate seconds elapsed since a timestamp.
    
    Args:
        timestamp: Unix timestamp to compare against
        
    Returns:
        Number of seconds since the timestamp
    """
    return now() - timestamp
