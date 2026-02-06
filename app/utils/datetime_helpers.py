"""Date and time utility functions."""

from datetime import datetime, timedelta, timezone


def now_utc() -> datetime:
    """
    Get current UTC datetime with timezone info.
    
    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc)


def days_between(start: datetime, end: datetime) -> int:
    """
    Calculate days between two datetimes.
    
    Args:
        start: Start datetime
        end: End datetime
    
    Returns:
        Number of days between the datetimes
    """
    return abs((end - start).days)


def is_within_window(timestamp: datetime, window_days: int) -> bool:
    """
    Check if a timestamp is within a time window from now.
    
    Args:
        timestamp: Timestamp to check
        window_days: Window size in days
    
    Returns:
        True if timestamp is within the window
    """
    cutoff = now_utc() - timedelta(days=window_days)
    return timestamp >= cutoff


def make_timezone_aware(dt: datetime) -> datetime:
    """
    Make a naive datetime timezone-aware (UTC).
    
    Args:
        dt: Datetime to convert
    
    Returns:
        Timezone-aware datetime
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
