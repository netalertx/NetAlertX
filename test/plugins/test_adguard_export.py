"""
Tests for adguard_export/script.py

Run from inside the NetAlertX container (where the full environment is available),
or locally — in that case the NetAlertX-specific modules are stubbed out
automatically before the script is imported.

    pytest test/plugins/test_adguard_export.py -v
"""

import json
import os
import sys
import tempfile
import types
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Stub NetAlertX-specific modules so tests can run outside the container.
# sys.modules.setdefault() is a no-op when the real module is already loaded,
# so this is safe to run inside the container too.
# ---------------------------------------------------------------------------
_tmp_log = tempfile.mkdtemp()


def _stub(name: str, **attrs):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod


_stub("pytz", timezone=lambda tz: tz)
_stub("conf")
_stub("const", dataPath=_tmp_log, logPath=_tmp_log, fullDbPath=os.path.join(_tmp_log, "test.db"))
_stub("plugin_helper", Plugin_Objects=MagicMock)
_stub("logger", mylog=lambda *a: None, Logger=MagicMock)
_stub("helper", get_setting_value=lambda k: "")
_stub("models", )
_stub("models.device_instance", DeviceInstance=MagicMock)

# Stub requests only when it isn't installed (e.g. bare system Python locally).
# In the container and CI, the real package is present and will be used.
if "requests" not in sys.modules:
    _req = types.ModuleType("requests")
    _req.Session = MagicMock
    _req.HTTPError = type("HTTPError", (Exception,), {})
    _req_exc = types.ModuleType("requests.exceptions")
    _req_exc.ConnectionError = type("ConnectionError", (Exception,), {})
    _req.exceptions = _req_exc
    sys.modules["requests"] = _req
    sys.modules["requests.exceptions"] = _req_exc

# ---------------------------------------------------------------------------
# Import the functions under test (must come after the stubs above).
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "front", "plugins", "adguard_export"))

from script import (  # noqa: E402
    AdGuardClient,
    _TYPE_TAG_MAP,
    build_agrd_client,
    device_type_to_tag,
    get_netalertx_devices,
    load_managed_names,
    save_managed_names,
    sync_to_adguard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_device(**overrides) -> dict:
    """Build a raw DeviceInstance.getAll() style dict."""
    base = {
        "devMac": "AA:BB:CC:00:00:01",
        "devName": "PC",
        "devLastIP": "10.0.0.1",
        "devType": "desktop",
        "devIsArchived": 0,
        "devPresentLastScan": 1,
        "devIsNew": 0,
    }
    return {**base, **overrides}


def _mock_agrd(existing=None) -> MagicMock:
    """Return a mock AdGuardClient whose get_clients() returns *existing*."""
    agrd = MagicMock(spec=AdGuardClient)
    agrd.get_clients.return_value = existing or []
    return agrd


# ---------------------------------------------------------------------------
# device_type_to_tag
# ---------------------------------------------------------------------------


class TestDeviceTypeToTag:
    def test_empty_string_returns_empty(self):
        assert device_type_to_tag("") == ""

    def test_none_returns_empty(self):
        assert device_type_to_tag(None) == ""

    def test_exact_match_case_insensitive(self):
        assert device_type_to_tag("Smartphone") == "device_phone"
        assert device_type_to_tag("LAPTOP") == "device_laptop"
        assert device_type_to_tag("nas") == "device_nas"

    def test_substring_fallback(self):
        # "gaming smartphone" contains "smartphone"
        assert device_type_to_tag("gaming smartphone") == "device_phone"

    def test_unknown_type_returns_empty(self):
        assert device_type_to_tag("toaster") == ""

    def test_all_map_values_are_valid_adguard_tags(self):
        valid_prefixes = ("device_", "ct_", "os_")
        for tag in _TYPE_TAG_MAP.values():
            assert any(tag.startswith(p) for p in valid_prefixes), (
                f"{tag!r} is not a valid AdGuard Home tag"
            )


# ---------------------------------------------------------------------------
# build_agrd_client
# ---------------------------------------------------------------------------


class TestBuildAgrdClient:
    def _device(self, **overrides) -> dict:
        base = {"mac": "AA:BB:CC:DD:EE:FF", "name": "My PC", "last_ip": "192.168.1.10", "dev_type": "desktop"}
        return {**base, **overrides}

    def test_mac_and_ip_both_included_when_use_mac_true(self):
        result = build_agrd_client(self._device(), use_mac=True)
        assert "aa:bb:cc:dd:ee:ff" in result["ids"]
        assert "192.168.1.10" in result["ids"]

    def test_only_ip_when_use_mac_false(self):
        result = build_agrd_client(self._device(), use_mac=False)
        assert result["ids"] == ["192.168.1.10"]

    def test_returns_empty_dict_when_no_usable_id(self):
        result = build_agrd_client(
            {"mac": "", "name": "Ghost", "last_ip": "0.0.0.0", "dev_type": ""},
            use_mac=True,
        )
        assert result == {}

    def test_null_mac_falls_back_to_ip(self):
        result = build_agrd_client(
            {"mac": "00:00:00:00:00:00", "name": "Dev", "last_ip": "10.0.0.5", "dev_type": ""},
            use_mac=True,
        )
        assert result["ids"] == ["10.0.0.5"]

    def test_device_type_tag_applied(self):
        result = build_agrd_client(self._device(dev_type="smartphone"), use_mac=True)
        assert result["tags"] == ["device_phone"]

    def test_unknown_device_type_produces_no_tag(self):
        result = build_agrd_client(self._device(dev_type=""), use_mac=True)
        assert result["tags"] == []

    def test_mac_is_lowercased(self):
        result = build_agrd_client(self._device(mac="AA:BB:CC:DD:EE:FF"), use_mac=True)
        assert "aa:bb:cc:dd:ee:ff" in result["ids"]


# ---------------------------------------------------------------------------
# load_managed_names / save_managed_names
# ---------------------------------------------------------------------------


class TestManagedNames:
    def test_round_trip(self, tmp_path):
        state = tmp_path / "state.json"
        with patch("script.STATE_FILE", str(state)):
            save_managed_names({"alpha", "beta", "gamma"})
            loaded = load_managed_names()
        assert loaded == {"alpha", "beta", "gamma"}

    def test_missing_file_returns_empty_set(self, tmp_path):
        with patch("script.STATE_FILE", str(tmp_path / "nonexistent.json")):
            assert load_managed_names() == set()

    def test_corrupt_file_returns_empty_set(self, tmp_path):
        state = tmp_path / "state.json"
        state.write_text("not valid json")
        with patch("script.STATE_FILE", str(state)):
            assert load_managed_names() == set()

    def test_save_sorts_names(self, tmp_path):
        state = tmp_path / "state.json"
        with patch("script.STATE_FILE", str(state)):
            save_managed_names({"zebra", "apple", "mango"})
            data = json.loads(state.read_text())
        assert data["managed"] == ["apple", "mango", "zebra"]


# ---------------------------------------------------------------------------
# get_netalertx_devices
# ---------------------------------------------------------------------------


class TestGetNetalertxDevices:
    def _call(self, rows, include_offline=True, include_new=True):
        with patch("script.DeviceInstance") as mock_di:
            mock_di.return_value.getAll.return_value = rows
            return get_netalertx_devices(include_offline=include_offline, include_new=include_new)

    def test_basic_query(self):
        result = self._call([_raw_device()])
        assert len(result) == 1
        assert result[0]["name"] == "PC"
        assert result[0]["mac"] == "AA:BB:CC:00:00:01"

    def test_archived_devices_excluded(self):
        result = self._call([
            _raw_device(devMac="AA:00:00:00:00:01", devName="Active", devIsArchived=0),
            _raw_device(devMac="AA:00:00:00:00:02", devName="Archived", devIsArchived=1),
        ])
        assert len(result) == 1
        assert result[0]["name"] == "Active"

    def test_offline_excluded_when_flag_false(self):
        result = self._call([
            _raw_device(devMac="AA:00:00:00:00:01", devName="Online", devPresentLastScan=1),
            _raw_device(devMac="AA:00:00:00:00:02", devName="Offline", devPresentLastScan=0),
        ], include_offline=False)
        assert len(result) == 1
        assert result[0]["name"] == "Online"

    def test_new_devices_excluded_when_flag_false(self):
        result = self._call([
            _raw_device(devMac="AA:00:00:00:00:01", devName="Known", devIsNew=0),
            _raw_device(devMac="AA:00:00:00:00:02", devName="Unknown", devIsNew=1),
        ], include_new=False)
        assert len(result) == 1
        assert result[0]["name"] == "Known"

    def test_nameless_device_falls_back_to_mac(self):
        result = self._call([_raw_device(devMac="BB:CC:DD:EE:FF:00", devName="", devLastIP="10.0.0.5")])
        assert result[0]["name"] == "BB:CC:DD:EE:FF:00"

    def test_row_with_no_mac_and_no_ip_skipped(self):
        result = self._call([_raw_device(devMac="", devName="Ghost", devLastIP="")])
        assert result == []

    def test_exception_returns_empty_list(self):
        with patch("script.DeviceInstance") as mock_di:
            mock_di.return_value.getAll.side_effect = Exception("db error")
            assert get_netalertx_devices(True, True) == []


# ---------------------------------------------------------------------------
# sync_to_adguard
# ---------------------------------------------------------------------------


class TestSyncToAdguard:
    def _device(self, name="PC", mac="AA:BB:CC:00:00:01", ip="10.0.0.1", dev_type="desktop") -> dict:
        return {"mac": mac, "name": name, "last_ip": ip, "dev_type": dev_type}

    def test_new_device_is_added(self, tmp_path):
        agrd = _mock_agrd(existing=[])
        with patch("script.STATE_FILE", str(tmp_path / "state.json")):
            added, updated, skipped, deleted = sync_to_adguard(
                agrd, [self._device()], use_mac=True, delete_missing=False
            )
        assert added == 1
        assert updated == skipped == deleted == 0
        agrd.add_client.assert_called_once()

    def test_unchanged_device_is_skipped(self, tmp_path):
        existing = [{"name": "PC", "ids": ["aa:bb:cc:00:00:01", "10.0.0.1"], "tags": ["device_pc"]}]
        agrd = _mock_agrd(existing=existing)
        with patch("script.STATE_FILE", str(tmp_path / "state.json")):
            added, updated, skipped, deleted = sync_to_adguard(
                agrd, [self._device()], use_mac=True, delete_missing=False
            )
        assert skipped == 1
        assert added == updated == deleted == 0
        agrd.update_client.assert_not_called()

    def test_renamed_device_is_updated(self, tmp_path):
        existing = [{"name": "Old Name", "ids": ["aa:bb:cc:00:00:01", "10.0.0.1"], "tags": ["device_pc"]}]
        agrd = _mock_agrd(existing=existing)
        with patch("script.STATE_FILE", str(tmp_path / "state.json")):
            added, updated, skipped, deleted = sync_to_adguard(
                agrd, [self._device(name="New Name")], use_mac=True, delete_missing=False
            )
        assert updated == 1
        agrd.update_client.assert_called_once_with("Old Name", agrd.update_client.call_args[0][1])

    def test_missing_device_deleted_when_flag_true(self, tmp_path):
        state = tmp_path / "state.json"
        state.write_text(json.dumps({"managed": ["Gone Device"]}))
        existing = [{"name": "Gone Device", "ids": ["10.0.0.99"], "tags": []}]
        agrd = _mock_agrd(existing=existing)
        with patch("script.STATE_FILE", str(state)):
            added, updated, skipped, deleted = sync_to_adguard(
                agrd, [], use_mac=True, delete_missing=True
            )
        assert deleted == 1
        agrd.delete_client.assert_called_once_with("Gone Device")

    def test_unmanaged_device_not_deleted(self, tmp_path):
        # State file is empty — we never added this client
        state = tmp_path / "state.json"
        state.write_text(json.dumps({"managed": []}))
        existing = [{"name": "Manual Client", "ids": ["10.0.0.50"], "tags": []}]
        agrd = _mock_agrd(existing=existing)
        with patch("script.STATE_FILE", str(state)):
            sync_to_adguard(agrd, [], use_mac=True, delete_missing=True)
        agrd.delete_client.assert_not_called()

    def test_manual_client_matched_by_id_not_adopted(self, tmp_path):
        # A manually-created AdGuard client whose IP matches a NetAlertX device
        # must not be added to managed_names — so DELETE=true won't touch it later.
        state = tmp_path / "state.json"
        state.write_text(json.dumps({"managed": []}))
        existing = [{"name": "Manual Client", "ids": ["10.0.0.5"], "tags": []}]
        agrd = _mock_agrd(existing=existing)
        device = {"mac": "", "name": "Manual Client", "last_ip": "10.0.0.5", "dev_type": ""}
        with patch("script.STATE_FILE", str(state)):
            sync_to_adguard(agrd, [device], use_mac=True, delete_missing=True)
            loaded = load_managed_names()
        assert "Manual Client" not in loaded
        agrd.delete_client.assert_not_called()

    def test_device_with_no_usable_id_is_skipped(self, tmp_path):
        agrd = _mock_agrd(existing=[])
        device = {"mac": "00:00:00:00:00:00", "name": "Ghost", "last_ip": "0.0.0.0", "dev_type": ""}
        with patch("script.STATE_FILE", str(tmp_path / "state.json")):
            added, updated, skipped, deleted = sync_to_adguard(
                agrd, [device], use_mac=True, delete_missing=False
            )
        assert skipped == 1
        agrd.add_client.assert_not_called()

    def test_existing_clients_parameter_avoids_extra_api_call(self, tmp_path):
        existing = []
        agrd = _mock_agrd(existing=existing)
        with patch("script.STATE_FILE", str(tmp_path / "state.json")):
            sync_to_adguard(
                agrd, [self._device()], use_mac=True, delete_missing=False,
                existing_clients=existing,
            )
        agrd.get_clients.assert_not_called()

    def test_rename_removes_old_name_from_managed_names(self, tmp_path):
        state = tmp_path / "state.json"
        state.write_text(json.dumps({"managed": ["Old Name"]}))
        existing = [{"name": "Old Name", "ids": ["aa:bb:cc:00:00:01", "10.0.0.1"], "tags": ["device_pc"]}]
        agrd = _mock_agrd(existing=existing)
        with patch("script.STATE_FILE", str(state)):
            sync_to_adguard(agrd, [self._device(name="New Name")], use_mac=True, delete_missing=False)
            loaded = load_managed_names()
        assert "Old Name" not in loaded
        assert "New Name" in loaded

    def test_update_preserves_custom_adguard_settings(self, tmp_path):
        existing = [{
            "name": "Old Name",
            "ids": ["aa:bb:cc:00:00:01", "10.0.0.1"],
            "tags": ["device_pc"],
            "filtering_enabled": True,
            "use_global_settings": False,
            "parental_enabled": True,
            "safebrowsing_enabled": False,
            "safesearch_enabled": False,
            "use_global_blocked_services": False,
            "blocked_services": ["youtube.com"],
            "upstreams": ["1.1.1.1"],
        }]
        agrd = _mock_agrd(existing=existing)
        with patch("script.STATE_FILE", str(tmp_path / "state.json")):
            sync_to_adguard(agrd, [self._device(name="New Name")], use_mac=True, delete_missing=False)
        _, sent_payload = agrd.update_client.call_args[0]
        assert sent_payload["filtering_enabled"] is True
        assert sent_payload["use_global_settings"] is False
        assert sent_payload["blocked_services"] == ["youtube.com"]
        assert sent_payload["upstreams"] == ["1.1.1.1"]
