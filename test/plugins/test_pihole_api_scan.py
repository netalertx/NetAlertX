"""Tests for the pihole_api_scan (PIHOLEAPI) plugin's online detection.

pihole_api_scan.py is loaded with its NetAlertX-internal dependencies stubbed
out (same approach as test_adguard_import.py), so these tests run without a
Pi-hole instance. get_pihole_network_devices() is patched per test.

Pi-hole FTL refreshes ips[].lastSeen for every client it still holds in
memory, even when the client is not in the ARP cache, so lastSeen stays fresh
for about 24 hours after a device left. The device's lastQuery (time of its
last DNS query) is what tells the plugin whether a device is still active.
"""

import datetime
import importlib.util
import os
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

# Unix time of the debug run the bug report is based on (2026-10-31 20:05:10 UTC).
NOW_TS = 1793477110

_MAC_PATTERN = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


def _fixed_now(as_string=True):
    """Stand-in for timeNowUTC() that always returns NOW_TS."""
    now = datetime.datetime.fromtimestamp(NOW_TS, tz=datetime.timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S") if as_string else now


def _load_pihole_api_scan_module():
    """Import pihole_api_scan.py with NetAlertX modules stubbed, then restore sys.modules."""
    missing_module = object()
    previous_modules = {}

    def stub(name, **attributes):
        """Put a fake module with the given attributes into sys.modules, remembering the previous entry."""
        previous_modules[name] = sys.modules.get(name, missing_module)
        module = types.ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        sys.modules[name] = module

    stub("plugin_helper", Plugin_Objects=MagicMock, is_mac=lambda value: bool(_MAC_PATTERN.match(value)))
    stub("utils.datetime_utils", timeNowUTC=_fixed_now)
    stub("logger", mylog=MagicMock(), Logger=MagicMock())
    stub("helper", get_setting_value=MagicMock(return_value="UTC"))
    stub("const", logPath="/tmp")
    stub("conf", tz=None)
    stub("pytz", timezone=MagicMock(return_value="UTC"))
    stub("utils.crypto_utils", string_to_fake_mac=MagicMock(return_value="fa:ce:00:00:00:01"))

    module_path = Path(__file__).resolve().parents[2] / "server" / "plugins" / "pihole_api_scan" / "pihole_api_scan.py"
    spec = importlib.util.spec_from_file_location("pihole_api_scan_script", module_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        for name, previous_module in previous_modules.items():
            if previous_module is missing_module:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module

    return module


pihole_api_scan = _load_pihole_api_scan_module()


def _api_device(hwaddr, ips, last_query, last_seen):
    """Build one /api/network/devices entry with the fields Pi-hole FTL v6 returns."""
    return {
        "id": 1,
        "hwaddr": hwaddr,
        "interface": "eth0",
        "firstSeen": NOW_TS - 30 * 86400,
        "lastQuery": last_query,
        "numQueries": 42,
        "macVendor": "Test Vendor",
        "ips": [
            {"ip": ip, "name": f"host{index}.lan", "lastSeen": last_seen, "nameUpdated": last_seen}
            for index, ip in enumerate(ips)
        ],
    }


def _gather(devices, get_offline=False, consider_online=300):
    """Run gather_device_entries() against the given API devices and plugin settings."""
    with patch.object(pihole_api_scan, "get_pihole_network_devices", return_value=devices), \
            patch.object(pihole_api_scan, "PIHOLEAPI_GET_OFFLINE", get_offline), \
            patch.object(pihole_api_scan, "PIHOLEAPI_CONSIDER_ONLINE", consider_online), \
            patch.object(pihole_api_scan, "PIHOLEAPI_FAKE_MAC", False):
        return pihole_api_scan.gather_device_entries()


class TestOnlineFromLastQuery:
    def test_stale_last_query_with_fresh_last_seen_is_skipped(self):
        """The reported bug: the phone's last DNS query is 5 h 47 min old, but
        Pi-hole still refreshes its ips[].lastSeen (10 s old)."""
        phone = _api_device("0a:60:b8:ad:b6:9d", ["192.168.178.64"], last_query=1793456269, last_seen=1793477100)

        assert _gather([phone]) == []

    def test_entry_reports_device_last_query(self):
        """The 'Last Query' column (watched3) shows the last DNS query, not ips[].lastSeen."""
        laptop = _api_device("f8:01:b4:b4:67:94", ["192.168.178.52"], last_query=1793477050, last_seen=1793477105)

        entries = _gather([laptop])

        assert [entry["lastQuery"] for entry in entries] == ["1793477050"]

    def test_recent_last_query_is_online(self):
        """A device whose last DNS query is 60 s old is imported as online."""
        laptop = _api_device("f8:01:b4:b4:67:94", ["192.168.178.52"], last_query=1793477050, last_seen=1793477105)

        entries = _gather([laptop])

        assert [entry["isOnline"] for entry in entries] == [True]

    @pytest.mark.parametrize(
        "last_query, expected_online",
        [
            (1793476810, [True]),  # exactly 300 s old: still online
            (1793476809, []),  # 301 s old: offline, so skipped
            (1793477140, [True]),  # 30 s in the future (Pi-hole clock ahead): online
        ],
    )
    def test_consider_online_window(self, last_query, expected_online):
        """The PIHOLEAPI_CONSIDER_ONLINE window is inclusive, and a lastQuery slightly in the future counts as online."""
        laptop = _api_device("f8:01:b4:b4:67:94", ["192.168.178.52"], last_query=last_query, last_seen=1793477105)

        entries = _gather([laptop], consider_online=300)

        assert [entry["isOnline"] for entry in entries] == expected_online

    @pytest.mark.parametrize(
        "last_query, consider_online",
        [
            (None, 300),  # field missing in the API response
            (0, 300),  # Pi-hole never saw a DNS query from this device
            (0, 10_000_000_000),  # a huge window must not turn "never" into online
        ],
    )
    def test_never_queried_device_is_offline(self, last_query, consider_online):
        """A device without a lastQuery (missing or 0) is offline, whatever the window."""
        scale = _api_device("00:24:e4:d0:82:7c", ["192.168.178.50"], last_query=last_query, last_seen=1793477100)
        if last_query is None:
            del scale["lastQuery"]

        entries = _gather([scale], get_offline=True, consider_online=consider_online)

        assert [entry["isOnline"] for entry in entries] == [False]

    def test_multi_ip_device_rows_share_online_state(self):
        """lastQuery is per device, so every IP row of a device gets the same state,
        however fresh each IP's own lastSeen is."""
        tv = _api_device("f8:01:b4:b4:67:94", ["192.168.178.52", "192.168.178.53"], last_query=1793453291, last_seen=1793477100)

        entries = _gather([tv], get_offline=True)

        assert [(entry["ip"], entry["isOnline"]) for entry in entries] == [
            ("192.168.178.52", False),
            ("192.168.178.53", False),
        ]


def _use_settings(monkeypatch, settings):
    """Serve settings to main() via get_setting_value, and restore the module globals main() rebinds after the test."""
    for name in ("PIHOLEAPI_URL", "PIHOLEAPI_PASSWORD", "PIHOLEAPI_API_MAXCLIENTS", "PIHOLEAPI_VERIFY_SSL",
                 "PIHOLEAPI_RUN_TIMEOUT", "PIHOLEAPI_GET_OFFLINE", "PIHOLEAPI_CONSIDER_ONLINE"):
        monkeypatch.setattr(pihole_api_scan, name, getattr(pihole_api_scan, name))
    monkeypatch.setattr(pihole_api_scan, "get_setting_value", settings.get)


def _run_main(monkeypatch, devices):
    """Run main() with PIHOLEAPI_GET_OFFLINE on against the given API devices; return add_object() kwargs keyed by (MAC, IP)."""
    # Auth and the devices request are patched below, so main() needs no other settings.
    _use_settings(monkeypatch, {
        "PIHOLEAPI_URL": "http://pi.hole/",
        "PIHOLEAPI_GET_OFFLINE": True,
        "PIHOLEAPI_CONSIDER_ONLINE": 300,
    })
    plugin_objects = MagicMock()
    monkeypatch.setattr(pihole_api_scan, "pihole_api_auth", lambda: True)
    monkeypatch.setattr(pihole_api_scan, "pihole_api_deauth", lambda: None)
    monkeypatch.setattr(pihole_api_scan, "get_pihole_network_devices", lambda: devices)
    monkeypatch.setattr(pihole_api_scan, "PIHOLEAPI_FAKE_MAC", False)
    monkeypatch.setattr(pihole_api_scan, "plugin_objects", plugin_objects)

    pihole_api_scan.main()
    return {(call.kwargs["primaryId"], call.kwargs["secondaryId"]): call.kwargs for call in plugin_objects.add_object.call_args_list}


class TestPresenceFromOnlineState:
    def test_offline_import_is_not_present(self, monkeypatch):
        """With PIHOLEAPI_GET_OFFLINE, an offline device is still imported, but its
        rows must not assert presence (helpVal4 maps to CurrentScan.scanPresence)."""
        phone = _api_device("0a:60:b8:ad:b6:9d", ["192.168.178.64"], last_query=1793456269, last_seen=1793477100)
        tv = _api_device("f8:01:b4:b4:67:94", ["192.168.178.52", "192.168.178.53"], last_query=1793477050, last_seen=1793477100)

        calls = _run_main(monkeypatch, [phone, tv])

        assert {key: kwargs.get("helpVal4") for key, kwargs in calls.items()} == {
            ("0a:60:b8:ad:b6:9d", "192.168.178.64"): "0",
            ("f8:01:b4:b4:67:94", "192.168.178.52"): "1",
            ("f8:01:b4:b4:67:94", "192.168.178.53"): "1",
        }
