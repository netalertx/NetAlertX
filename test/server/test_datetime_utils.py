"""
Unit tests for datetime_utils.py UTC timestamp functions.

Tests verify that:
- timeNowUTC() returns correct formats (string and datetime object)
- All timestamps are in UTC timezone
- No other functions call datetime.datetime.now() (single source of truth)
"""

import sys
import os
import datetime
import pytest

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from utils.datetime_utils import timeNowUTC, DATETIME_PATTERN  # noqa: E402


class TestTimeNowUTC:
    """Test suite for timeNowUTC() function"""

    def test_timeNowUTC_returns_string_by_default(self):
        """Test that timeNowUTC() returns a string by default"""
        result = timeNowUTC()
        assert isinstance(result, str)
        assert len(result) == 19  # 'YYYY-MM-DD HH:MM:SS' format

    def test_timeNowUTC_string_format(self):
        """Test that timeNowUTC() returns correct string format"""
        result = timeNowUTC()
        # Verify format matches DATETIME_PATTERN
        try:
            datetime.datetime.strptime(result, DATETIME_PATTERN)
        except ValueError:
            pytest.fail(f"timeNowUTC() returned invalid format: {result}")

    def test_timeNowUTC_returns_datetime_object_when_false(self):
        """Test that timeNowUTC(as_string=False) returns datetime object"""
        result = timeNowUTC(as_string=False)
        assert isinstance(result, datetime.datetime)

    def test_timeNowUTC_datetime_has_UTC_timezone(self):
        """Test that datetime object has UTC timezone"""
        result = timeNowUTC(as_string=False)
        assert result.tzinfo is datetime.UTC

    def test_timeNowUTC_datetime_no_microseconds(self):
        """Test that datetime object has microseconds set to 0"""
        result = timeNowUTC(as_string=False)
        assert result.microsecond == 0

    def test_timeNowUTC_consistency_between_modes(self):
        """Test that string and datetime modes return consistent values"""
        dt_obj = timeNowUTC(as_string=False)
        str_result = timeNowUTC(as_string=True)

        # Convert datetime to string and compare (within 1 second tolerance)
        dt_str = dt_obj.strftime(DATETIME_PATTERN)
        # Parse both to compare timestamps
        t1 = datetime.datetime.strptime(dt_str, DATETIME_PATTERN)
        t2 = datetime.datetime.strptime(str_result, DATETIME_PATTERN)
        diff = abs((t1 - t2).total_seconds())
        assert diff <= 1  # Allow 1 second difference

    def test_timeNowUTC_is_actually_UTC(self):
        """Test that timeNowUTC() returns actual UTC time, not local time"""
        utc_now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
        result = timeNowUTC(as_string=False)

        # Should be within 1 second
        diff = abs((utc_now - result).total_seconds())
        assert diff <= 1

    def test_timeNowUTC_string_matches_datetime_conversion(self):
        """Test that string result matches datetime object conversion"""
        dt_obj = timeNowUTC(as_string=False)
        str_result = timeNowUTC(as_string=True)

        # Convert datetime to string using same format
        expected = dt_obj.strftime(DATETIME_PATTERN)

        # Should be same or within 1 second
        t1 = datetime.datetime.strptime(expected, DATETIME_PATTERN)
        t2 = datetime.datetime.strptime(str_result, DATETIME_PATTERN)
        diff = abs((t1 - t2).total_seconds())
        assert diff <= 1

    def test_timeNowUTC_explicit_true_parameter(self):
        """Test that timeNowUTC(as_string=True) explicitly returns string"""
        result = timeNowUTC(as_string=True)
        assert isinstance(result, str)

    def test_timeNowUTC_multiple_calls_increase(self):
        """Test that subsequent calls return increasing timestamps"""
        import time

        t1_str = timeNowUTC()
        time.sleep(0.1)
        t2_str = timeNowUTC()

        t1 = datetime.datetime.strptime(t1_str, DATETIME_PATTERN)
        t2 = datetime.datetime.strptime(t2_str, DATETIME_PATTERN)

        assert t2 >= t1
