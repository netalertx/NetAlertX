"""Health check endpoint for NetAlertX system vitality monitoring."""

import os
import psutil
from pathlib import Path

from const import dbPath, dataPath
from logger import mylog


# ===============================================================================
# Database Vitality
# ===============================================================================

def get_db_size_mb():
    """
    Calculate total database size in MB (app.db + app.db-wal).

    Returns:
        float: Size in MB, or 0 if database files don't exist.
    """
    try:
        db_file = Path(dbPath)
        wal_file = Path(f"{dbPath}-wal")

        size_bytes = 0
        if db_file.exists():
            size_bytes += db_file.stat().st_size
        if wal_file.exists():
            size_bytes += wal_file.stat().st_size

        return round(size_bytes / (1024 * 1024), 2)
    except Exception as e:
        mylog("verbose", [f"[health] Error calculating DB size: {e}"])
        return 0.0


# ===============================================================================
# Memory Pressure
# ===============================================================================

def get_mem_usage_pct():
    """
    Calculate memory usage percentage (used / total * 100).

    Returns:
        int: Memory usage as integer percentage (0-100), or None on error.
    """
    try:
        vm = psutil.virtual_memory()
        pct = int((vm.used / vm.total) * 100)
        return max(0, min(100, pct))  # Clamp to 0-100
    except Exception as e:
        mylog("verbose", [f"[health] Error calculating memory usage: {e}"])
        return None


def get_load_avg_1m():
    """
    Get 1-minute load average.

    Returns:
        float: 1-minute load average, or -1 on error.
    """
    try:
        load_1m, _, _ = os.getloadavg()
        return round(load_1m, 2)
    except Exception as e:
        mylog("verbose", [f"[health] Error getting load average: {e}"])
        return -1.0


# ===============================================================================
# Disk Headroom
# ===============================================================================

def get_storage_pct():
    """
    Calculate disk usage percentage of /data mount.

    Returns:
        int: Disk usage as integer percentage (0-100), or None on error.
    """
    try:
        stat = os.statvfs(dataPath)
        total = stat.f_blocks * stat.f_frsize
        used = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
        pct = int((used / total) * 100) if total > 0 else 0
        return max(0, min(100, pct))  # Clamp to 0-100
    except Exception as e:
        mylog("verbose", [f"[health] Error calculating storage usage: {e}"])
        return None


def _is_plausible_cpu_temp(celsius):
    """-273(.15)C (absolute zero) is a known sentinel some virtualized/container
    thermal zones (e.g. acpitz) report when there is no real sensor behind them;
    reject any reading outside a sane physical range instead of trusting it."""
    return -50 < celsius < 150


def get_cpu_temp():
    """
    Get CPU temperature from hardware sensors if available.

    Returns:
        int: CPU temperature in Celsius, or None if unavailable or if no
        sensor reports a physically plausible reading.
    """
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None

        # Prefer 'coretemp' (Intel), fallback to first available
        if "coretemp" in temps and temps["coretemp"] and _is_plausible_cpu_temp(temps["coretemp"][0].current):
            return int(temps["coretemp"][0].current)

        # Fallback to first sensor with a plausible reading
        for sensor_type, readings in temps.items():
            if readings and _is_plausible_cpu_temp(readings[0].current):
                return int(readings[0].current)

        return None
    except Exception as e:
        mylog("verbose", [f"[health] Error reading CPU temperature: {e}"])
        return None


def get_mem_mb():
    """
    Get total system memory in MB.

    Returns:
        int: Total memory in MB, or None on error.
    """
    try:
        vm = psutil.virtual_memory()
        total_mb = int(vm.total / (1024 * 1024))
        return total_mb

    except Exception as e:
        mylog("verbose", [f"[health] Error getting memory size: {e}"])
        return None


def get_storage_gb():
    """
    Get total storage size of /data in GB.

    Returns:
        float: Total storage in GB, or None on error.
    """
    try:
        stat = os.statvfs(dataPath)
        total = stat.f_blocks * stat.f_frsize

        gb = round(total / (1024 ** 3), 2)
        return gb

    except Exception as e:
        mylog("verbose", [f"[health] Error getting storage size: {e}"])
        return None


# ===============================================================================
# Process Vitality (NetAlertX's own process, not the host)
# ===============================================================================

# Non-blocking cpu_percent() needs one persistent Process object to mean anything
# ("since the last time this was called") - this object is dedicated to /health only,
# never shared with the tick-scoped sampler in scan/resource_history.py, so the two
# measurement paths can't interfere with each other.
_health_process = psutil.Process()


def get_process_cpu_percent():
    """
    CPU% for the NetAlertX process since the last time this was called - a live
    gauge for /health, not a tick-scoped measurement (see scan/resource_history.py's
    tick-scoped sampler for that).

    Returns:
        float: CPU utilization percentage, or 0.0 on error.
    """
    try:
        return _health_process.cpu_percent(interval=None)
    except (psutil.Error, AttributeError) as e:
        mylog("verbose", [f"[health] Error reading process CPU%: {e}"])
        return 0.0


def get_process_rss_mb():
    """
    Resident memory (RSS) for the current process, in MB - a point-in-time
    snapshot, not a delta (RSS doesn't accumulate the way CPU-time/IO do).

    Returns:
        float: RSS in MB, or 0.0 on error.
    """
    try:
        return round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
    except (psutil.Error, AttributeError) as e:
        mylog("verbose", [f"[health] Error reading process RSS: {e}"])
        return 0.0


# ===============================================================================
# Aggregator
# ===============================================================================

def get_health_status():
    """
    Collect all health metrics into a single dict.

    Returns:
        dict: Dictionary with all health metrics.
    """
    return {
        "db_size_mb": get_db_size_mb(),
        "mem_usage_pct": get_mem_usage_pct(),
        "load_1m": get_load_avg_1m(),
        "storage_pct": get_storage_pct(),
        "cpu_temp": get_cpu_temp(),
        "storage_gb": get_storage_gb(),
        "mem_mb": get_mem_mb(),
        "process_cpu_pct": get_process_cpu_percent(),
        "process_rss_mb": get_process_rss_mb(),
    }
