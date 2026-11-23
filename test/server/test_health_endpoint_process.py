"""
Tests for health_endpoint.py's process-scoped metrics: get_process_cpu_percent()/
get_process_rss_mb() (the /health live gauge, Design §2 of the resource-usage
history feature) and their inclusion in get_health_status().
"""

import psutil
from unittest.mock import MagicMock

from server.api_server import health_endpoint as he


def test_get_process_cpu_percent_returns_value(monkeypatch):
    monkeypatch.setattr(he._health_process, "cpu_percent", lambda interval=None: 12.5)
    assert he.get_process_cpu_percent() == 12.5


def test_get_process_cpu_percent_falls_back_to_zero_on_error(monkeypatch):
    def raising(interval=None):
        raise psutil.NoSuchProcess(pid=1)
    monkeypatch.setattr(he._health_process, "cpu_percent", raising)
    assert he.get_process_cpu_percent() == 0.0


def test_get_process_rss_mb_returns_rounded_mb(monkeypatch):
    fake_process = MagicMock()
    fake_process.memory_info.return_value = MagicMock(rss=150 * 1024 * 1024)
    monkeypatch.setattr(he.psutil, "Process", lambda: fake_process)
    assert he.get_process_rss_mb() == 150.0


def test_get_process_rss_mb_falls_back_to_zero_on_error(monkeypatch):
    def raising():
        raise psutil.AccessDenied()
    monkeypatch.setattr(he.psutil, "Process", raising)
    assert he.get_process_rss_mb() == 0.0


def test_get_health_status_includes_process_fields(monkeypatch):
    """get_health_status() must expose the two new process metrics alongside
    the seven existing host-level ones."""
    monkeypatch.setattr(he, "get_process_cpu_percent", lambda: 3.2)
    monkeypatch.setattr(he, "get_process_rss_mb", lambda: 142.75)

    status = he.get_health_status()

    assert status["process_cpu_pct"] == 3.2
    assert status["process_rss_mb"] == 142.75
    for key in ("db_size_mb", "mem_usage_pct", "load_1m", "storage_pct",
                "cpu_temp", "storage_gb", "mem_mb"):
        assert key in status


def _reading(current):
    return MagicMock(current=current)


def test_get_cpu_temp_skips_implausible_reading_within_coretemp(monkeypatch):
    """A single implausible coretemp reading (e.g. a sensor glitch on core 0)
    must not discard the whole 'coretemp' group when another core in the
    same group reports a plausible temperature - must not fall through to
    None or to a less-preferred sensor group."""
    monkeypatch.setattr(he.psutil, "sensors_temperatures", lambda: {
        "coretemp": [_reading(-273.0), _reading(55.0)],
        "acpitz": [_reading(40.0)],
    })
    assert he.get_cpu_temp() == 55


def test_get_cpu_temp_falls_back_to_other_sensor_when_coretemp_fully_implausible(monkeypatch):
    monkeypatch.setattr(he.psutil, "sensors_temperatures", lambda: {
        "coretemp": [_reading(-273.0)],
        "acpitz": [_reading(42.0)],
    })
    assert he.get_cpu_temp() == 42
