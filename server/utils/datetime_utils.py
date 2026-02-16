#!/usr/bin/env python

# from datetime import datetime
from dateutil import parser
import datetime
import re
import pytz
from typing import Union, Optional
from zoneinfo import ZoneInfo
import email.utils
import conf
# from const import *


# -------------------------------------------------------------------------------
# DateTime
# -------------------------------------------------------------------------------

DATETIME_PATTERN = "%Y-%m-%d %H:%M:%S"
DATETIME_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')


# ⚠️ CRITICAL: ALL database timestamps MUST be stored in UTC
# This is the SINGLE SOURCE OF TRUTH for current time in NetAlertX
# Use timeNowUTC() for DB writes (returns UTC string by default)
# Use timeNowUTC(as_string=False) for datetime operations (scheduling, comparisons, logging)
def timeNowUTC(as_string=True):
    """
    Return the current time in UTC.

    This is the ONLY function that calls datetime.datetime.now() in the entire codebase.
    All timestamps stored in the database MUST use UTC format.

    Args:
        as_string (bool): If True, returns formatted string for DB storage.
                         If False, returns datetime object for operations.

    Returns:
        str: UTC timestamp as 'YYYY-MM-DD HH:MM:SS' when as_string=True
        datetime.datetime: UTC datetime object when as_string=False

    Examples:
        timeNowUTC()              → '2025-11-04 07:09:11'  (for DB writes)
        timeNowUTC(as_string=False) → datetime.datetime(2025, 11, 4, 7, 9, 11, tzinfo=UTC)
    """
    utc_now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
    return utc_now.strftime(DATETIME_PATTERN) if as_string else utc_now


def timeNowTZ(as_string=True):
    """
    Return the current time in the configured local timezone.
    Falls back to UTC if conf.tz is invalid or missing.
    """
    # Get canonical UTC time
    utc_now = timeNowUTC(as_string=False)

    # Resolve timezone safely
    tz = None
    try:
        if isinstance(conf.tz, datetime.tzinfo):
            tz = conf.tz
        elif isinstance(conf.tz, str) and conf.tz:
            tz = ZoneInfo(conf.tz)
    except Exception:
        tz = None

    if tz is None:
        tz = datetime.UTC  # fallback to UTC

    # Convert to local timezone (or UTC fallback)
    local_now = utc_now.astimezone(tz)

    return local_now.strftime(DATETIME_PATTERN) if as_string else local_now


def get_timezone_offset():
    if conf.tz:
        now = timeNowUTC(as_string=False).astimezone(conf.tz)
        offset_hours = now.utcoffset().total_seconds() / 3600
    else:
        offset_hours = 0
    offset_formatted = "{:+03d}:{:02d}".format(int(offset_hours), int((offset_hours % 1) * 60))
    return offset_formatted


# -------------------------------------------------------------------------------
#  Date and time methods
# -------------------------------------------------------------------------------

def normalizeTimeStamp(inputTimeStamp):
    """
    Normalize various timestamp formats into a datetime.datetime object.

    Supports:
    - SQLite-style 'YYYY-MM-DD HH:MM:SS'
    - ISO 8601 'YYYY-MM-DDTHH:MM:SSZ'
    - Epoch timestamps (int or float)
    - datetime.datetime objects (returned as-is)
    - Empty or invalid values (returns None)
    """
    if inputTimeStamp is None:
        return None

    # Already a datetime
    if isinstance(inputTimeStamp, datetime.datetime):
        return inputTimeStamp

    # Epoch timestamp (integer or float)
    if isinstance(inputTimeStamp, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(inputTimeStamp)
        except (OSError, OverflowError, ValueError):
            return None

    # String formats (SQLite / ISO8601)
    if isinstance(inputTimeStamp, str):
        inputTimeStamp = inputTimeStamp.strip()
        if not inputTimeStamp:
            return None
        try:
            # match the "2025-11-08 14:32:10" format
            pattern = DATETIME_REGEX

            if pattern.match(inputTimeStamp):
                return datetime.datetime.strptime(inputTimeStamp, DATETIME_PATTERN)
            else:
                # Handles SQLite and ISO8601 automatically
                return parser.parse(inputTimeStamp)
        except Exception:
            return None

    # Unrecognized type
    return None


# -------------------------------------------------------------------------------------------
def format_date_iso(date_val: str) -> Optional[str]:
    """Ensures a date string from DB is returned as a proper ISO string with TZ.

    Assumes DB timestamps are stored in UTC and converts them to user's configured timezone.
    """
    if not date_val:
        return None

    try:
        # 1. Parse the string from DB (e.g., "2026-01-20 07:58:18")
        if isinstance(date_val, str):
            # Use a more flexible parser if it's not strict ISO
            dt = datetime.datetime.fromisoformat(date_val.replace(" ", "T"))
        else:
            dt = date_val

        # 2. If it has no timezone, assume it's UTC (our DB storage format)
        #    then CONVERT to user's configured timezone
        if dt.tzinfo is None:
            # Mark as UTC first
            dt = dt.replace(tzinfo=datetime.UTC)
            # Convert to user's timezone
            target_tz = conf.tz if isinstance(conf.tz, datetime.tzinfo) else ZoneInfo(conf.tz)
            dt = dt.astimezone(target_tz)

        # 3. Return the string. .isoformat() will now include the +11:00 or +10:00
        return dt.isoformat()
    except Exception as e:
        print(f"Error formatting date: {e}")
        return str(date_val)


# -------------------------------------------------------------------------------------------
def format_event_date(date_str: str, event_type: str) -> str:
    """Format event date with fallback rules."""
    if date_str:
        return format_date(date_str)
    elif event_type == "<missing event>":
        return "<missing event>"
    else:
        return "<still connected>"


# -------------------------------------------------------------------------------------------
def ensure_datetime(dt: Union[str, datetime.datetime, None]) -> datetime.datetime:
    if dt is None:
        return timeNowUTC(as_string=False)
    if isinstance(dt, str):
        return datetime.datetime.fromisoformat(dt)
    return dt


def parse_datetime(dt_str):
    if not dt_str:
        return None
    try:
        # Try ISO8601 first
        return datetime.datetime.fromisoformat(dt_str)
    except ValueError:
        # Try RFC1123 / HTTP format
        try:
            return datetime.datetime.strptime(dt_str, '%a, %d %b %Y %H:%M:%S GMT')
        except ValueError:
            return None


def format_date(date_str: str) -> str:
    """Format a date string from DB for display.

    Assumes DB timestamps are stored in UTC and converts them to user's configured timezone.
    """
    try:
        if not date_str:
            return ""

        date_str = re.sub(r"\s+", " ", str(date_str).strip())
        dt = parse_datetime(date_str)

        if not dt:
            return f"invalid:{repr(date_str)}"

        # If the DB timestamp has no timezone, assume it's UTC (our storage format)
        # then CONVERT to user's configured timezone
        if dt.tzinfo is None:
            # Mark as UTC first
            dt = dt.replace(tzinfo=datetime.UTC)
            # Convert to user's timezone
            if isinstance(conf.tz, str):
                dt = dt.astimezone(ZoneInfo(conf.tz))
            else:
                dt = dt.astimezone(conf.tz)

        # Return ISO format with timezone offset
        return dt.isoformat()

    except Exception as e:
        return f"invalid:{repr(date_str)} e: {e}"


def format_date_diff(date1, date2, tz_name):
    """
    Return difference between two datetimes as 'Xd   HH:MM'.
    Assumes DB timestamps are stored in UTC and converts them to user's configured timezone.
    date2 can be None (uses now).
    """
    # Get timezone from settings
    tz = pytz.timezone(tz_name)

    def parse_dt(dt):
        if dt is None:
            # Get current UTC time and convert to user's timezone
            return timeNowUTC(as_string=False).astimezone(tz)
        if isinstance(dt, str):
            try:
                dt_parsed = email.utils.parsedate_to_datetime(dt)
            except (ValueError, TypeError):
                # fallback: parse ISO string
                dt_parsed = datetime.datetime.fromisoformat(dt)
            # If naive (no timezone), assume it's UTC from DB, then convert to user's timezone
            if dt_parsed.tzinfo is None:
                dt_parsed = dt_parsed.replace(tzinfo=datetime.UTC).astimezone(tz)
            else:
                dt_parsed = dt_parsed.astimezone(tz)
            return dt_parsed
        # If datetime object without timezone, assume it's UTC from DB
        return dt.astimezone(tz) if dt.tzinfo else dt.replace(tzinfo=datetime.UTC).astimezone(tz)

    dt1 = parse_dt(date1)
    dt2 = parse_dt(date2)

    delta = dt2 - dt1
    total_minutes = int(delta.total_seconds() // 60)
    days, rem_minutes = divmod(total_minutes, 1440)  # 1440 mins in a day
    hours, minutes = divmod(rem_minutes, 60)

    return {
        "text": f"{days}d {hours:02}:{minutes:02}",
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "total_minutes": total_minutes
    }
