"""
Unit tests for time utilities.

Tests for the centralized time functions.
"""

import pytest
from datetime import datetime, timezone, timedelta
from app.utils.time import (
    now, 
    timestamp_to_datetime, 
    datetime_to_timestamp,
    days_ago,
    seconds_since,
)


class TestNow:
    """Tests for now() function."""
    
    def test_returns_integer(self):
        """Test that now() returns an integer."""
        result = now()
        assert isinstance(result, int)
    
    def test_returns_reasonable_timestamp(self):
        """Test that timestamp is in a reasonable range."""
        result = now()
        # Should be after Jan 1, 2020
        assert result > 1577836800
        # Should be before Jan 1, 2100
        assert result < 4102444800
    
    def test_increases_over_time(self):
        """Test that subsequent calls return equal or greater values."""
        t1 = now()
        t2 = now()
        assert t2 >= t1


class TestTimestampToDatetime:
    """Tests for timestamp_to_datetime() function."""
    
    def test_converts_correctly(self):
        """Test conversion from timestamp to datetime."""
        # Jan 1, 2021 00:00:00 UTC
        timestamp = 1609459200
        result = timestamp_to_datetime(timestamp)
        
        assert result.year == 2021
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 0
        assert result.minute == 0
    
    def test_returns_timezone_aware(self):
        """Test that result is timezone-aware."""
        result = timestamp_to_datetime(1609459200)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc


class TestDatetimeToTimestamp:
    """Tests for datetime_to_timestamp() function."""
    
    def test_converts_correctly(self):
        """Test conversion from datetime to timestamp."""
        dt = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = datetime_to_timestamp(dt)
        assert result == 1609459200
    
    def test_handles_naive_datetime(self):
        """Test that naive datetimes are treated as UTC."""
        dt_naive = datetime(2021, 1, 1, 0, 0, 0)
        dt_utc = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        result_naive = datetime_to_timestamp(dt_naive)
        result_utc = datetime_to_timestamp(dt_utc)
        
        assert result_naive == result_utc
    
    def test_roundtrip(self):
        """Test that timestamp -> datetime -> timestamp is lossless."""
        original = 1609459200
        dt = timestamp_to_datetime(original)
        result = datetime_to_timestamp(dt)
        assert result == original


class TestDaysAgo:
    """Tests for days_ago() function."""
    
    def test_returns_past_timestamp(self):
        """Test that days_ago returns a timestamp in the past."""
        current = now()
        past = days_ago(7)
        
        assert past < current
    
    def test_correct_days_difference(self):
        """Test that the difference is correct number of days."""
        current = now()
        past = days_ago(7)
        
        # 7 days = 7 * 86400 seconds
        expected_diff = 7 * 86400
        actual_diff = current - past
        
        # Allow 1 second tolerance for test execution time
        assert abs(actual_diff - expected_diff) <= 1
    
    def test_zero_days_ago(self):
        """Test that 0 days ago is approximately now."""
        current = now()
        result = days_ago(0)
        
        assert abs(result - current) <= 1


class TestSecondsSince:
    """Tests for seconds_since() function."""
    
    def test_returns_positive_for_past(self):
        """Test that seconds_since returns positive for past timestamps."""
        past = now() - 3600  # 1 hour ago
        result = seconds_since(past)
        
        assert result >= 3599  # Allow small tolerance
        assert result <= 3601
    
    def test_returns_zero_for_now(self):
        """Test that seconds_since returns ~0 for current time."""
        current = now()
        result = seconds_since(current)
        
        # Should be very close to 0
        assert result <= 1
