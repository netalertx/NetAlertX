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


def get_cpu_temp():
    """
    Get CPU temperature from hardware sensors if available.

    Returns:
        int: CPU temperature in Celsius, or None if unavailable.
    """
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None

        # Prefer 'coretemp' (Intel), fallback to first available
        if "coretemp" in temps and temps["coretemp"]:
            return int(temps["coretemp"][0].current)

        # Fallback to first sensor with data
        for sensor_type, readings in temps.items():
            if readings:
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
    }
