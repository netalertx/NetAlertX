"""
Tests for UniFi client SSID import and persistent full-import lock files.

Run from inside the NetAlertX container, or locally - NetAlertX-specific
modules are stubbed out automatically before the script is imported.

    pytest test/plugins/test_unifi_import.py -v
"""

import importlib.util
import json
import os
import sys
import tempfile
import types
from unittest.mock import MagicMock, patch

import pytest

_tmp_log = tempfile.mkdtemp()
_tmp_db = tempfile.mkdtemp()

_stubbed_module_names = []


def _stub(name: str, **attrs):
    """Register an absent dependency stub and track it for cleanup after importing the plugin."""
    if name not in sys.modules:
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
        _stubbed_module_names.append(name)


_stub("pytz", timezone=lambda tz: tz)
_stub("conf")
_stub("const", dbFolderPath=_tmp_db, logPath=_tmp_log)
_stub(
    "plugin_helper",
    Plugin_Objects=MagicMock,
    rmBadChars=lambda s: s,
    is_typical_router_ip=lambda ip: False,
    is_mac=lambda v: isinstance(v, str) and len(v.split(":")) == 6,
)
_stub("logger", mylog=lambda *a: None, Logger=MagicMock)
_stub("helper", get_setting_value=lambda k: "UTC" if k == "TIMEZONE" else "", normalize_string=lambda s: s)

if "pyunifi" not in sys.modules:
    _pyunifi = types.ModuleType("pyunifi")
    _pyunifi_controller = types.ModuleType("pyunifi.controller")
    _pyunifi_controller.Controller = MagicMock
    _pyunifi.controller = _pyunifi_controller
    sys.modules["pyunifi"] = _pyunifi
    sys.modules["pyunifi.controller"] = _pyunifi_controller
    _stubbed_module_names.extend(["pyunifi", "pyunifi.controller"])

if "urllib3" not in sys.modules:
    _urllib3 = types.ModuleType("urllib3")
    _urllib3.disable_warnings = lambda *a, **k: None
    _urllib3_exc = types.ModuleType("urllib3.exceptions")
    _urllib3_exc.InsecureRequestWarning = type("InsecureRequestWarning", (Warning,), {})
    _urllib3.exceptions = _urllib3_exc
    sys.modules["urllib3"] = _urllib3
    sys.modules["urllib3.exceptions"] = _urllib3_exc
    _stubbed_module_names.extend(["urllib3", "urllib3.exceptions"])

# unifi_import's module file is named "script.py", same as several other
# plugins (e.g. adguard_export) - load it under a private module name
# instead of a plain `import script`, so this test doesn't collide with
# another plugin's test importing its own same-named script.py in the same
# pytest process.
_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "server", "plugins", "unifi_import", "script.py")
_spec = importlib.util.spec_from_file_location("unifi_import_script", _SCRIPT_PATH)
script = importlib.util.module_from_spec(_spec)
sys.modules["unifi_import_script"] = script
_spec.loader.exec_module(script)

# Stops these fake entries from shadowing the real modules for other test
# files collected later in the same pytest session (script's own
# module-level `from x import y` bindings are already resolved by now).
for _name in _stubbed_module_names:
    sys.modules.pop(_name, None)

_migrate_legacy_lock_file = script._migrate_legacy_lock_file
check_full_run_state = script.check_full_run_state
read_lock_file = script.read_lock_file
set_lock_file_value = script.set_lock_file_value


@pytest.mark.parametrize(
    "client_fields,expected_ssid",
    [
        ({"is_wired": False, "essid": "example-wifi", "last_connection_network_name": "example-vlan"}, "example-wifi"),
        ({"is_wired": False, "essid": "example-wifi", "connection_network_name": "example-vlan"}, "example-wifi"),
        ({"essid": "example-wifi"}, "example-wifi"),
        ({"is_wired": True, "essid": "old-wifi", "connection_network_name": "example-vlan"}, ""),
        ({"is_wired": True}, ""),
        ({"is_wired": False, "last_connection_network_name": "example-vlan"}, ""),
        ({"is_wired": False, "essid": None}, ""),
        ({"is_wired": False, "essid": ""}, ""),
    ],
)
def test_collect_details_reports_wireless_ssid(client_fields, expected_ssid):
    """Import the wireless SSID without treating network names as SSIDs."""
    objects = MagicMock()
    client = {"mac": "aa:bb:cc:dd:ee:01", "ip": "192.0.2.1", **client_fields}

    script.collect_details(
        {"cl": ""}, [client], set(), [], objects, "client", "", True
    )

    objects.add_object.assert_called_once()
    assert objects.add_object.call_args.kwargs["extra"] == expected_ssid


def test_unifi_ssid_is_mapped_to_current_scan():
    """Route imported SSIDs through CurrentScan to the device update policy."""
    config_path = os.path.join(os.path.dirname(_SCRIPT_PATH), "config.json")
    with open(config_path, encoding="utf-8") as config_file:
        config = json.load(config_file)

    assert config["mapped_to_table"] == "CurrentScan"
    extra = next(column for column in config["database_column_definitions"] if column["column"] == "extra")
    assert extra.get("mapped_to_column") == "scanSSID"


class TestMigrateLegacyLockFile:
    def test_migrates_legacy_file_to_new_location(self, tmp_path):
        legacy = tmp_path / "full_run.UNFIMP.lock"
        new = tmp_path / "db" / "full_run.UNFIMP.lock"
        new.parent.mkdir()
        legacy.write_text("1")
        with patch.object(script, "LOCK_FILE", str(new)), patch.object(script, "_LEGACY_LOCK_FILE", str(legacy)):
            _migrate_legacy_lock_file()
        assert not legacy.exists()
        assert new.read_text() == "1"

    def test_does_not_overwrite_existing_new_file(self, tmp_path):
        legacy = tmp_path / "legacy.lock"
        new = tmp_path / "new.lock"
        legacy.write_text("1")
        new.write_text("0")
        with patch.object(script, "LOCK_FILE", str(new)), patch.object(script, "_LEGACY_LOCK_FILE", str(legacy)):
            _migrate_legacy_lock_file()
        assert legacy.exists()
        assert new.read_text() == "0"

    def test_no_op_when_neither_file_exists(self, tmp_path):
        legacy = tmp_path / "legacy.lock"
        new = tmp_path / "new.lock"
        with patch.object(script, "LOCK_FILE", str(new)), patch.object(script, "_LEGACY_LOCK_FILE", str(legacy)):
            _migrate_legacy_lock_file()
        assert not new.exists()


class TestLockFileRoundTrip:
    def test_read_missing_lock_file_returns_false(self, tmp_path):
        with patch.object(script, "LOCK_FILE", str(tmp_path / "nonexistent.lock")):
            assert read_lock_file() is False

    def test_set_and_read_round_trip(self, tmp_path):
        lock = tmp_path / "full_run.lock"
        with patch.object(script, "LOCK_FILE", str(lock)):
            set_lock_file_value("once", False)
            assert read_lock_file() is True

    @pytest.mark.parametrize(
        "config_value,lock_file_value,expected",
        [
            ("always", False, True),
            ("always", True, True),
            ("once", False, True),
            ("once", True, False),
            ("disabled", False, False),
            ("disabled", True, False),
        ],
    )
    def test_check_full_run_state(self, config_value, lock_file_value, expected):
        assert check_full_run_state(config_value, lock_file_value) is expected
