"""
Tests for NameResolver.resolve_from_plugin (server/scan/name_resolution.py).

A name-resolution plugin (DIGSCAN, NSLOOKUP, AVAHISCAN, NBTSCAN) stores one
Plugins_Objects row per (MAC, IP) it queried. When a device changes IP the old
row is never deleted, so the resolver must only trust the row for the device's
current IP instead of any row sharing its MAC (issue #1731).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import DummyDB, make_plugin_db, seed_plugin_object  # noqa: E402

import scan.name_resolution as name_resolution  # noqa: E402
from scan.name_resolution import NameResolver  # noqa: E402

MAC = "aa:bb:cc:dd:ee:01"
OTHER_MAC = "aa:bb:cc:dd:ee:02"
OLD_IP = "10.0.1.11"
NEW_IP = "10.5.1.40"
OLD_NAME = "nb-pre3581-03.example.local."
NEW_NAME = "nb-3520-20.example.local."
NOT_FOUND = "(name not found)"

PLUGIN_CASES = [
    ("DIGSCAN", "resolve_dig"),
    ("NSLOOKUP", "resolve_nslookup"),
    ("AVAHISCAN", "resolve_mdns"),
    ("NBTSCAN", "resolve_nbtlookup"),
]


@pytest.fixture
def plugin_conn():
    """In-memory DB with the plugin tables; yields (DummyDB, cursor, conn)."""
    _, conn = make_plugin_db()
    yield DummyDB(conn), conn.cursor(), conn
    conn.close()


@pytest.fixture
def ip_match_setting(monkeypatch):
    """Patch NEWDEV_IP_MATCH_NAME / NEWDEV_NAME_CLEANUP_REGEX for the resolver."""
    def _set(ip_match):
        def _get(key, default=""):
            if key == "NEWDEV_IP_MATCH_NAME":
                return ip_match
            if key == "NEWDEV_NAME_CLEANUP_REGEX":
                return []
            return default
        monkeypatch.setattr(name_resolution, "get_setting_value", _get)
    return _set


@pytest.mark.parametrize("plugin,method", PLUGIN_CASES)
def test_current_ip_row_wins_over_stale_old_ip_row(plugin_conn, ip_match_setting, plugin, method):
    """Two rows for one MAC: the row for the device's current IP is returned."""
    db, cur, _ = plugin_conn
    ip_match_setting(False)
    seed_plugin_object(cur, plugin, MAC, OLD_IP, watched2=OLD_NAME,
                       status="missing-in-last-scan", changed="2026-01-01 00:00:00")
    seed_plugin_object(cur, plugin, MAC, NEW_IP, watched2=NEW_NAME,
                       changed="2026-02-01 00:00:00")

    resolved = getattr(NameResolver(db), method)(MAC, NEW_IP)

    assert resolved.raw == NEW_NAME


@pytest.mark.parametrize("plugin,method", PLUGIN_CASES)
def test_current_ip_row_wins_regardless_of_insertion_order(plugin_conn, ip_match_setting, plugin, method):
    """The result must not depend on which row happens to be stored first."""
    db, cur, _ = plugin_conn
    ip_match_setting(False)
    seed_plugin_object(cur, plugin, MAC, NEW_IP, watched2=NEW_NAME,
                       changed="2026-02-01 00:00:00")
    seed_plugin_object(cur, plugin, MAC, OLD_IP, watched2=OLD_NAME,
                       changed="2026-03-01 00:00:00")

    resolved = getattr(NameResolver(db), method)(MAC, NEW_IP)

    assert resolved.raw == NEW_NAME


@pytest.mark.parametrize("plugin,method", PLUGIN_CASES)
def test_stale_old_ip_row_is_not_used_for_new_ip(plugin_conn, ip_match_setting, plugin, method):
    """Only an old-IP row exists and the device moved: no name, not the stale one."""
    db, cur, _ = plugin_conn
    ip_match_setting(False)
    seed_plugin_object(cur, plugin, MAC, OLD_IP, watched2=OLD_NAME,
                       status="missing-in-last-scan")

    resolved = getattr(NameResolver(db), method)(MAC, NEW_IP)

    assert resolved.raw == NOT_FOUND
    assert resolved.cleaned == NOT_FOUND


@pytest.mark.parametrize("plugin,method", PLUGIN_CASES)
def test_missing_in_last_scan_current_ip_row_still_matches(plugin_conn, ip_match_setting, plugin, method):
    """Status is not a filter: a resolved device's row goes missing-in-last-scan
    once the plugin stops querying it, but is still the valid answer."""
    db, cur, _ = plugin_conn
    ip_match_setting(False)
    seed_plugin_object(cur, plugin, MAC, NEW_IP, watched2=NEW_NAME,
                       status="missing-in-last-scan")

    resolved = getattr(NameResolver(db), method)(MAC, NEW_IP)

    assert resolved.raw == NEW_NAME


def test_same_mac_and_ip_returns_newest_row(plugin_conn, ip_match_setting):
    """Duplicate (MAC, IP) rows resolve deterministically to the most recently changed."""
    db, cur, _ = plugin_conn
    ip_match_setting(False)
    seed_plugin_object(cur, "DIGSCAN", MAC, NEW_IP, watched2=OLD_NAME,
                       changed="2026-01-01 00:00:00")
    seed_plugin_object(cur, "DIGSCAN", MAC, NEW_IP, watched2=NEW_NAME,
                       changed="2026-02-01 00:00:00")

    assert NameResolver(db).resolve_dig(MAC, NEW_IP).raw == NEW_NAME


def test_other_plugin_rows_are_ignored(plugin_conn, ip_match_setting):
    """A row from a different plugin never answers a DIGSCAN lookup."""
    db, cur, _ = plugin_conn
    ip_match_setting(False)
    seed_plugin_object(cur, "NSLOOKUP", MAC, NEW_IP, watched2=NEW_NAME)

    assert NameResolver(db).resolve_dig(MAC, NEW_IP).raw == NOT_FOUND


def test_ip_match_fallback_still_matches_other_mac_by_ip(plugin_conn, ip_match_setting):
    """NEWDEV_IP_MATCH_NAME keeps matching another MAC's row by IP, tagged "(IP match)"."""
    db, cur, _ = plugin_conn
    ip_match_setting(True)
    seed_plugin_object(cur, "DIGSCAN", OTHER_MAC, NEW_IP, watched2=NEW_NAME)

    resolved = NameResolver(db).resolve_dig(MAC, NEW_IP)

    assert resolved.raw == NEW_NAME
    assert resolved.cleaned.endswith("(IP match)")


def test_ip_match_fallback_disabled_returns_not_found(plugin_conn, ip_match_setting):
    """With NEWDEV_IP_MATCH_NAME off, another MAC's row is never used."""
    db, cur, _ = plugin_conn
    ip_match_setting(False)
    seed_plugin_object(cur, "DIGSCAN", OTHER_MAC, NEW_IP, watched2=NEW_NAME)

    assert NameResolver(db).resolve_dig(MAC, NEW_IP).raw == NOT_FOUND


def test_mac_row_takes_priority_over_ip_match_fallback(plugin_conn, ip_match_setting):
    """A matching (MAC, IP) row wins over another MAC's row for the same IP."""
    db, cur, _ = plugin_conn
    ip_match_setting(True)
    seed_plugin_object(cur, "DIGSCAN", OTHER_MAC, NEW_IP, watched2=OLD_NAME)
    seed_plugin_object(cur, "DIGSCAN", MAC, NEW_IP, watched2=NEW_NAME)

    resolved = NameResolver(db).resolve_dig(MAC, NEW_IP)

    assert resolved.raw == NEW_NAME
    assert "(IP match)" not in resolved.cleaned
