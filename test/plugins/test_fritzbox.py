"""
Tests for Fritz!Box plugin (fritzbox.py).

fritzbox.py is imported directly. Its module-level side effects
(get_setting_value, Logger, Plugin_Objects) are patched out before the
first import so no live config reads, log files, or result files are
created during tests.
"""

import sys
import os
from unittest.mock import patch, MagicMock

from utils.crypto_utils import string_to_fake_mac

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SERVER = os.path.join(_ROOT, "server")
_PLUGIN_DIR = os.path.join(_ROOT, "front", "plugins", "fritzbox")

for _p in [_ROOT, _SERVER, _PLUGIN_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Import fritzbox with module-level side effects patched
# ---------------------------------------------------------------------------
# fritzbox.py calls get_setting_value(), Logger(), and Plugin_Objects() at
# module level. Patching these before the first import prevents live config
# reads, log-file creation, and result-file creation during tests.

with patch("helper.get_setting_value", return_value="UTC"), \
     patch("logger.Logger"), \
     patch("plugin_helper.Plugin_Objects"):
    import fritzbox  # noqa: E402

from plugin_helper import normalize_mac  # noqa: E402

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_host_entry(mac="AA:BB:CC:DD:EE:FF", ip="192.168.1.10",
                     hostname="testdevice", active=1, interface="Ethernet"):
    return {
        "NewMACAddress": mac,
        "NewIPAddress": ip,
        "NewHostName": hostname,
        "NewActive": active,
        "NewInterfaceType": interface,
    }


@pytest.fixture
def mock_fritz_hosts():
    """
    Patches fritzbox.FritzHosts so that get_connected_devices() uses a
    controllable mock.  Yields the FritzHosts *instance* (what FritzHosts(fc)
    returns).
    """
    hosts_instance = MagicMock()
    with patch("fritzbox.FritzHosts", return_value=hosts_instance):
        yield hosts_instance


# ===========================================================================
# get_connected_devices
# ===========================================================================

class TestGetConnectedDevices:

    def test_returns_active_device(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 1
        mock_fritz_hosts.get_generic_host_entry.return_value = _make_host_entry(active=1)
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=True)
        assert len(devices) == 1
        assert devices[0]["active_status"] == "Active"

    def test_active_only_filters_inactive_device(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 2
        mock_fritz_hosts.get_generic_host_entry.side_effect = [
            _make_host_entry(mac="AA:BB:CC:DD:EE:01", active=1),
            _make_host_entry(mac="AA:BB:CC:DD:EE:02", active=0),
        ]
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=True)
        assert len(devices) == 1
        assert devices[0]["mac_address"] == "aa:bb:cc:dd:ee:01"

    def test_active_only_false_includes_inactive_device(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 2
        mock_fritz_hosts.get_generic_host_entry.side_effect = [
            _make_host_entry(mac="AA:BB:CC:DD:EE:01", active=1),
            _make_host_entry(mac="AA:BB:CC:DD:EE:02", active=0),
        ]
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert len(devices) == 2
        assert devices[1]["active_status"] == "Inactive"

    def test_device_without_mac_is_skipped(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 2
        mock_fritz_hosts.get_generic_host_entry.side_effect = [
            _make_host_entry(mac=""),
            _make_host_entry(mac="AA:BB:CC:DD:EE:01"),
        ]
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert len(devices) == 1
        assert devices[0]["mac_address"] == "aa:bb:cc:dd:ee:01"

    def test_ethernet_interface_maps_to_lan(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 1
        mock_fritz_hosts.get_generic_host_entry.return_value = _make_host_entry(interface="Ethernet")
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert devices[0]["interface_type"] == "LAN"

    def test_wifi_interface_maps_to_wifi(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 1
        mock_fritz_hosts.get_generic_host_entry.return_value = _make_host_entry(interface="802.11")
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert devices[0]["interface_type"] == "WiFi"

    def test_unknown_interface_is_preserved(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 1
        mock_fritz_hosts.get_generic_host_entry.return_value = _make_host_entry(interface="SomeOtherType")
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert devices[0]["interface_type"] == "SomeOtherType"

    def test_mac_address_is_normalized_to_lowercase(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 1
        mock_fritz_hosts.get_generic_host_entry.return_value = _make_host_entry(mac="AA:BB:CC:DD:EE:FF")
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert devices[0]["mac_address"] == "aa:bb:cc:dd:ee:ff"

    def test_missing_hostname_defaults_to_unknown(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 1
        mock_fritz_hosts.get_generic_host_entry.return_value = _make_host_entry(hostname="")
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert devices[0]["hostname"] == "Unknown"

    def test_failed_host_entry_does_not_abort_remaining(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 3
        mock_fritz_hosts.get_generic_host_entry.side_effect = [
            _make_host_entry(mac="AA:BB:CC:DD:EE:01"),
            Exception("TR-064 timeout"),
            _make_host_entry(mac="AA:BB:CC:DD:EE:03"),
        ]
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert len(devices) == 2

    def test_empty_host_list_returns_empty(self, mock_fritz_hosts):
        mock_fritz_hosts.host_numbers = 0
        devices = fritzbox.get_connected_devices(MagicMock(), active_only=False)
        assert devices == []


# ===========================================================================
# check_guest_wifi_status
# ===========================================================================

class TestCheckGuestWifiStatus:

    def test_disabled_service_returns_inactive(self):
        fc = MagicMock()
        fc.call_action.return_value = {"NewEnable": False, "NewSSID": ""}
        result = fritzbox.check_guest_wifi_status(fc, guest_service_num=3)
        assert result["active"] is False

    def test_enabled_service_returns_active(self):
        fc = MagicMock()
        fc.call_action.return_value = {"NewEnable": True, "NewSSID": "MyGuestWiFi"}
        result = fritzbox.check_guest_wifi_status(fc, guest_service_num=3)
        assert result["active"] is True
        assert result["ssid"] == "MyGuestWiFi"

    def test_queries_correct_service_number(self):
        fc = MagicMock()
        fc.call_action.return_value = {"NewEnable": True, "NewSSID": "Guest"}
        fritzbox.check_guest_wifi_status(fc, guest_service_num=2)
        fc.call_action.assert_called_once_with("WLANConfiguration2", "GetInfo")

    def test_service_exception_returns_inactive(self):
        fc = MagicMock()
        fc.call_action.side_effect = Exception("Service unavailable")
        result = fritzbox.check_guest_wifi_status(fc, guest_service_num=3)
        assert result["active"] is False

    def test_empty_ssid_uses_default_label(self):
        fc = MagicMock()
        fc.call_action.return_value = {"NewEnable": True, "NewSSID": ""}
        result = fritzbox.check_guest_wifi_status(fc, guest_service_num=3)
        assert result["active"] is True
        assert result["ssid"] == "Guest WiFi"

    def test_service1_can_be_guest(self):
        fc = MagicMock()
        fc.call_action.return_value = {"NewEnable": True, "NewSSID": "Gast"}
        result = fritzbox.check_guest_wifi_status(fc, guest_service_num=1)
        assert result["active"] is True
        fc.call_action.assert_called_once_with("WLANConfiguration1", "GetInfo")


# ===========================================================================
# create_guest_wifi_device
# ===========================================================================

class TestCreateGuestWifiDevice:

    def _fc_with_mac(self, mac):
        fc = MagicMock()
        fc.call_action.return_value = {"NewMACAddress": mac}
        return fc

    def test_returns_device_dict(self):
        device = fritzbox.create_guest_wifi_device(self._fc_with_mac("AA:BB:CC:DD:EE:FF"))
        assert device is not None
        assert "mac_address" in device
        assert device["hostname"] == "Guest WiFi Network"
        assert device["active_status"] == "Active"
        assert device["interface_type"] == "Access Point"
        assert device["ip_address"] == ""
        # MAC must match string_to_fake_mac output (fa:ce: prefix)
        assert device["mac_address"].startswith("fa:ce:")

    def test_guest_mac_has_locally_administered_bit(self):
        """The locally-administered bit (0x02) must be set in the first byte.
        string_to_fake_mac uses the 'fa:ce:' prefix; 0xFA & 0x02 == 0x02."""
        device = fritzbox.create_guest_wifi_device(self._fc_with_mac("AA:BB:CC:DD:EE:FF"))
        first_byte = int(device["mac_address"].split(":")[0], 16)
        assert first_byte & 0x02 != 0

    def test_guest_mac_format_is_valid(self):
        """MAC must be 6 colon-separated lowercase hex pairs."""
        device = fritzbox.create_guest_wifi_device(self._fc_with_mac("AA:BB:CC:DD:EE:FF"))
        parts = device["mac_address"].split(":")
        assert len(parts) == 6
        for part in parts:
            assert len(part) == 2
            int(part, 16)  # raises ValueError if not valid hex

    def test_guest_mac_is_deterministic(self):
        """Same Fritz!Box MAC must always produce the same guest MAC."""
        fc = self._fc_with_mac("AA:BB:CC:DD:EE:FF")
        mac1 = fritzbox.create_guest_wifi_device(fc)["mac_address"]
        mac2 = fritzbox.create_guest_wifi_device(fc)["mac_address"]
        assert mac1 == mac2

    def test_different_fritzbox_macs_produce_different_guest_macs(self):
        mac_a = fritzbox.create_guest_wifi_device(self._fc_with_mac("AA:BB:CC:DD:EE:01"))["mac_address"]
        mac_b = fritzbox.create_guest_wifi_device(self._fc_with_mac("AA:BB:CC:DD:EE:02"))["mac_address"]
        assert mac_a != mac_b

    def test_no_fritzbox_mac_uses_fallback(self):
        """When DeviceInfo returns no MAC, fall back to a sentinel-derived MAC."""
        fc = MagicMock()
        fc.call_action.return_value = {"NewMACAddress": ""}
        device = fritzbox.create_guest_wifi_device(fc)
        assert device["mac_address"] == string_to_fake_mac("FRITZBOX_GUEST")

    def test_device_info_exception_returns_none(self):
        """If DeviceInfo call raises, create_guest_wifi_device must return None."""
        fc = MagicMock()
        fc.call_action.side_effect = Exception("Connection refused")
        device = fritzbox.create_guest_wifi_device(fc)
        assert device is None

    def test_known_mac_produces_known_guest_mac(self):
        """
        Regression anchor: for a fixed Fritz!Box MAC, the expected guest MAC
        is derived via string_to_fake_mac(normalize_mac(...)).  If the hashing
        logic in fritzbox.py or string_to_fake_mac changes, this test fails.
        """
        fritzbox_mac = normalize_mac("AA:BB:CC:DD:EE:FF")
        expected = string_to_fake_mac(fritzbox_mac)

        device = fritzbox.create_guest_wifi_device(self._fc_with_mac("AA:BB:CC:DD:EE:FF"))
        assert device["mac_address"] == expected


# ===========================================================================
# get_fritzbox_connection
# ===========================================================================

class TestGetFritzboxConnection:

    def test_successful_connection(self):
        fc_instance = MagicMock()
        fc_instance.modelname = "FRITZ!Box 7590"
        fc_instance.system_version = "7.57"
        fc_class = MagicMock(return_value=fc_instance)

        with patch("fritzbox.FritzConnection", fc_class):
            result = fritzbox.get_fritzbox_connection("fritz.box", 49443, "admin", "pass", True)

        assert result is fc_instance
        fc_class.assert_called_once_with(
            address="fritz.box", port=49443, user="admin", password="pass", use_tls=True, timeout=10,
        )

    def test_import_error_returns_none(self):
        with patch("fritzbox.FritzConnection", side_effect=ImportError("fritzconnection not found")):
            result = fritzbox.get_fritzbox_connection("fritz.box", 49443, "admin", "pass", True)

        assert result is None

    def test_connection_exception_returns_none(self):
        with patch("fritzbox.FritzConnection", side_effect=Exception("Connection refused")):
            result = fritzbox.get_fritzbox_connection("fritz.box", 49443, "admin", "pass", True)

        assert result is None


# ===========================================================================
# main
# ===========================================================================

class TestMain:

    _SETTINGS = {
        "FRITZBOX_HOST": "fritz.box",
        "FRITZBOX_PORT": 49443,
        "FRITZBOX_USER": "admin",
        "FRITZBOX_PASS": "secret",
        "FRITZBOX_USE_TLS": True,
        "FRITZBOX_REPORT_GUEST": False,
        "FRITZBOX_GUEST_SERVICE": 3,
        "FRITZBOX_ACTIVE_ONLY": True,
    }

    def _patch_settings(self):
        return patch.object(
            fritzbox, "get_setting_value",
            side_effect=lambda key: self._SETTINGS[key],
        )

    def test_connection_failure_returns_1(self):
        mock_po = MagicMock()
        with self._patch_settings(), \
             patch.object(fritzbox, "get_fritzbox_connection", return_value=None), \
             patch.object(fritzbox, "plugin_objects", mock_po):
            result = fritzbox.main()

        assert result == 1
        mock_po.write_result_file.assert_called_once()
        mock_po.add_object.assert_not_called()

    def test_scan_processes_devices(self):
        devices = [
            {"mac_address": "aa:bb:cc:dd:ee:01", "ip_address": "192.168.1.10",
             "hostname": "device1", "active_status": "Active", "interface_type": "LAN"},
            {"mac_address": "aa:bb:cc:dd:ee:02", "ip_address": "192.168.1.11",
             "hostname": "device2", "active_status": "Active", "interface_type": "WiFi"},
        ]
        mock_po = MagicMock()

        with self._patch_settings(), \
             patch.object(fritzbox, "get_fritzbox_connection", return_value=MagicMock()), \
             patch.object(fritzbox, "get_connected_devices", return_value=devices), \
             patch.object(fritzbox, "plugin_objects", mock_po):
            result = fritzbox.main()

        assert result == 0
        assert mock_po.add_object.call_count == 2
        mock_po.write_result_file.assert_called_once()

    def test_guest_wifi_device_appended_when_active(self):
        devices = [
            {"mac_address": "aa:bb:cc:dd:ee:01", "ip_address": "192.168.1.10",
             "hostname": "device1", "active_status": "Active", "interface_type": "LAN"},
        ]
        guest_device = {
            "mac_address": "02:a1:b2:c3:d4:e5", "ip_address": "",
            "hostname": "Guest WiFi Network", "active_status": "Active",
            "interface_type": "Access Point",
        }
        settings = {**self._SETTINGS, "FRITZBOX_REPORT_GUEST": True}
        mock_po = MagicMock()

        with patch.object(fritzbox, "get_setting_value", side_effect=lambda k: settings[k]), \
             patch.object(fritzbox, "get_fritzbox_connection", return_value=MagicMock()), \
             patch.object(fritzbox, "get_connected_devices", return_value=devices), \
             patch.object(fritzbox, "check_guest_wifi_status", return_value={"active": True, "ssid": "Guest"}), \
             patch.object(fritzbox, "create_guest_wifi_device", return_value=guest_device), \
             patch.object(fritzbox, "plugin_objects", mock_po):
            result = fritzbox.main()

        assert result == 0
        assert mock_po.add_object.call_count == 2  # 1 device + 1 guest
        # Verify the guest device was passed correctly
        guest_call = mock_po.add_object.call_args_list[1]
        assert guest_call.kwargs["primaryId"] == "02:a1:b2:c3:d4:e5"
        assert guest_call.kwargs["watched3"] == "Access Point"

    def test_guest_wifi_not_appended_when_inactive(self):
        devices = [
            {"mac_address": "aa:bb:cc:dd:ee:01", "ip_address": "192.168.1.10",
             "hostname": "device1", "active_status": "Active", "interface_type": "LAN"},
        ]
        settings = {**self._SETTINGS, "FRITZBOX_REPORT_GUEST": True}
        mock_po = MagicMock()

        with patch.object(fritzbox, "get_setting_value", side_effect=lambda k: settings[k]), \
             patch.object(fritzbox, "get_fritzbox_connection", return_value=MagicMock()), \
             patch.object(fritzbox, "get_connected_devices", return_value=devices), \
             patch.object(fritzbox, "check_guest_wifi_status", return_value={"active": False, "ssid": ""}), \
             patch.object(fritzbox, "plugin_objects", mock_po):
            result = fritzbox.main()

        assert result == 0
        assert mock_po.add_object.call_count == 1  # only the real device
