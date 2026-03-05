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


def now_ms() -> int:
    """
    Get current UTC time as a unix timestamp in milliseconds.
    
    This is the standardized function for all timestamp operations
    in the drift detection service to match database storage format.
    
    Returns:
        Current timestamp as integer (milliseconds since epoch)
        
    Example:
        >>> ts = now_ms()
        >>> isinstance(ts, int)
        True
        >>> ts > 1000000000000  # After 2001 in milliseconds
        True
    """
    return int(datetime.now(timezone.utc).timestamp() * 1000)


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
    Convert datetime to unix timestamp in seconds.
    
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


def datetime_to_timestamp_ms(dt: datetime) -> int:
    """
    Convert datetime to unix timestamp in milliseconds.
    
    Args:
        dt: Datetime object (naive datetimes assumed to be UTC)
        
    Returns:
        Unix timestamp in milliseconds
        
    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2021, 1, 1, tzinfo=timezone.utc)
        >>> datetime_to_timestamp_ms(dt)
        1609459200000
    """
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def timestamp_ms_to_datetime(timestamp_ms: int) -> datetime:
    """
    Convert unix timestamp in milliseconds to timezone-aware datetime.
    
    Args:
        timestamp_ms: Unix timestamp in milliseconds
        
    Returns:
        Timezone-aware datetime object in UTC
        
    Example:
        >>> dt = timestamp_ms_to_datetime(1609459200000)
        >>> dt.year
        2021
    """
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)


def days_ago(days: int) -> int:
    """
    Get timestamp for N days ago from now.
    
    Args:
        days: Number of days ago
        
    Returns:
        Unix timestamp for that point in time
    """
    return now() - (days * 86400)


def days_ago_ms(days: int) -> int:
    """
    Get timestamp in milliseconds for N days ago from now.
    
    Args:
        days: Number of days ago
        
    Returns:
        Unix timestamp in milliseconds for that point in time
    """
    return now_ms() - (days * 86400 * 1000)


def seconds_since(timestamp: int) -> int:
    """
    Calculate seconds elapsed since a timestamp.
    
    Args:
        timestamp: Unix timestamp to compare against
        
    Returns:
        Number of seconds since the timestamp
    """
    return now() - timestamp
