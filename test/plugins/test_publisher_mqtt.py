"""Tests for the _publisher_mqtt (MQTT) plugin's device_tracker attribute payload.

mqtt.py is loaded with its NetAlertX-internal dependencies (conf, const,
utils.plugin_utils, plugin_helper, logger, helper, database,
utils.datetime_utils, models.notification_instance) and the external
paho.mqtt.client/pytz packages stubbed out - same approach
test_wificanary.py/test_adguard_import.py use - so this runs without the full
devcontainer environment or a real MQTT broker. `sanitize_string`/
`format_date_iso` are reimplemented locally (same shape as helper's/
utils.datetime_utils') to avoid pulling in their own dependency chains.

Regression coverage: devSSID and devVlan were missing
from the JSON payload published to both a device's individual sensor state
topic and its device_tracker's json_attributes_topic (mqtt.py's
build_device_tracker_attributes(), extracted from mqtt_start() specifically
so this logic is testable without mocking the whole MQTT publish flow).

Also covers publish_mqtt()'s bounded retry: a failing publish() call used to
retry indefinitely (an unbounded `while status != 0` loop), which could burn
this plugin's entire RUN_TIMEOUT budget on one stuck call against a degraded
broker. It now gives up after _PUBLISH_MAX_ATTEMPTS.
"""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])


def _sanitize_string(value):
    """Same shape as helper.sanitize_string, without its import chain."""
    import re
    return re.sub(r"[^a-zA-Z0-9-_\s]", "", str(value))


def _format_date_iso(value):
    """Same shape as utils.datetime_utils.format_date_iso, without its import chain."""
    return value


def _bytes_to_string(value):
    """Same shape as helper.bytes_to_string, without its import chain."""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return value


def _load_mqtt_module():
    missing_module = object()
    previous_modules = {}

    def stub(name, **attributes):
        previous_modules[name] = sys.modules.get(name, missing_module)
        module = types.ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        sys.modules[name] = module

    stub("conf", tz=None)
    stub("const", confFileName="/tmp/app.conf", logPath="/tmp")
    stub("utils.plugin_utils", getPluginObject=MagicMock())
    stub("plugin_helper", Plugin_Objects=MagicMock)
    stub("logger", mylog=MagicMock(), Logger=MagicMock())
    stub(
        "helper",
        get_setting_value=MagicMock(return_value="UTC"),
        bytes_to_string=_bytes_to_string,
        sanitize_string=_sanitize_string,
        normalize_string=lambda s: s,
    )
    stub("database", DB=MagicMock, get_device_stats=MagicMock())
    stub("utils.datetime_utils", timeNowUTC=MagicMock(), format_date_iso=_format_date_iso)
    stub("models.notification_instance", NotificationInstance=MagicMock)
    stub("pytz", timezone=MagicMock(return_value="UTC"))
    stub("paho", mqtt=types.ModuleType("paho.mqtt"))
    stub("paho.mqtt", client=types.ModuleType("paho.mqtt.client"))
    stub("paho.mqtt.client", Client=MagicMock)

    module_path = Path(__file__).resolve().parents[2] / "server" / "plugins" / "_publisher_mqtt" / "mqtt.py"
    spec = importlib.util.spec_from_file_location("publisher_mqtt_script", module_path)
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


mqtt = _load_mqtt_module()


def _device(**overrides):
    base = {
        "devLastIP": "192.168.1.33",
        "devIsNew": 0,
        "devAlertDown": 0,
        "devVendor": "Some Vendor",
        "devMac": "44:ef:44:ef:44:ef",
        "devLastConnection": "2026-01-01 00:00:00",
        "devFirstConnection": "2025-01-01 00:00:00",
        "devSyncHubNode": "",
        "devGroup": "",
        "devLocation": "",
        "devSSID": "",
        "devVlan": "",
        "devParentMAC": "",
    }
    base.update(overrides)
    return base


class TestBuildDeviceId:
    def test_colons_become_underscores(self):
        assert mqtt.build_device_id("AA:BB:CC:DD:EE:FF") == "mac_aa_bb_cc_dd_ee_ff"

    def test_spaces_are_stripped_hyphens_are_kept(self):
        assert mqtt.build_device_id("AA-BB-CC DD:EE:FF") == "mac_aa-bb-ccdd_ee_ff"


class TestBuildDisplayName:
    def test_plain_name_unchanged(self):
        assert mqtt.build_display_name("Living Room TV") == "Living Room TV"

    def test_disallowed_punctuation_is_stripped(self):
        assert mqtt.build_display_name("Bob's Phone!") == "Bobs Phone"

    def test_hyphen_and_underscore_are_kept(self):
        assert mqtt.build_display_name("office-printer_2") == "office-printer_2"


class TestToBinarySensor:
    def test_int_at_least_one_is_on(self):
        assert mqtt.to_binary_sensor(1) == "ON"
        assert mqtt.to_binary_sensor(2) == "ON"

    def test_int_zero_is_off(self):
        assert mqtt.to_binary_sensor(0) == "OFF"

    def test_float_at_least_one_is_on(self):
        assert mqtt.to_binary_sensor(1.0) == "ON"

    def test_bool_true_is_on(self):
        assert mqtt.to_binary_sensor(True) == "ON"

    def test_bool_false_is_off(self):
        assert mqtt.to_binary_sensor(False) == "OFF"

    def test_string_one_is_on(self):
        assert mqtt.to_binary_sensor("1") == "ON"

    def test_other_strings_are_off(self):
        assert mqtt.to_binary_sensor("0") == "OFF"
        assert mqtt.to_binary_sensor("yes") == "OFF"

    def test_bytes_one_is_on(self):
        assert mqtt.to_binary_sensor(b"1") == "ON"

    def test_bytes_other_is_off(self):
        assert mqtt.to_binary_sensor(b"0") == "OFF"

    def test_none_is_off(self):
        assert mqtt.to_binary_sensor(None) == "OFF"


class TestBuildDeviceTrackerAttributes:
    def test_ssid_and_vlan_are_included(self):
        device = _device(devSSID="HomeWiFi", devVlan="10")
        attrs = mqtt.build_device_tracker_attributes(device, [device], "My Device")
        assert attrs["ssid"] == "HomeWiFi"
        assert attrs["vlan"] == "10"

    def test_blank_ssid_and_vlan_pass_through_unchanged(self):
        device = _device(devSSID="", devVlan="")
        attrs = mqtt.build_device_tracker_attributes(device, [device], "My Device")
        assert attrs["ssid"] == ""
        assert attrs["vlan"] == ""

    def test_existing_keys_still_present(self):
        """Regression guard: the extraction in #1816 must not drop any of
        the pre-existing payload keys."""
        device = _device()
        attrs = mqtt.build_device_tracker_attributes(device, [device], "My Device")
        for key in (
            "last_ip", "is_new", "alert_down", "vendor", "mac_address", "model",
            "last_connection", "first_connection", "sync_node", "group", "location",
            "network_parent_mac", "network_parent_name",
        ):
            assert key in attrs, f"missing pre-existing key: {key}"

    def test_network_parent_name_resolved_from_devices_list(self):
        parent = _device(devMac="aa:bb:cc:dd:ee:ff")
        parent["devName"] = "Router"
        child = _device(devParentMAC="aa:bb:cc:dd:ee:ff")
        attrs = mqtt.build_device_tracker_attributes(child, [parent, child], "Child Device")
        assert attrs["network_parent_name"] == "Router"

    def test_vendor_is_sanitized_but_ssid_is_not(self):
        """vendor goes through sanitize_string() (OUI-lookup text); ssid does
        not, since real-world SSIDs commonly contain punctuation that
        sanitize_string() would strip out, mangling the displayed value."""
        device = _device(devVendor="TP-Link!", devSSID="Bob's WiFi!")
        attrs = mqtt.build_device_tracker_attributes(device, [device], "My Device")
        assert attrs["vendor"] == "TP-Link"
        assert attrs["ssid"] == "Bob's WiFi!"

    def test_missing_ssid_and_vlan_columns_default_to_blank(self):
        """MQTT_DEVICES_SQL is a free-text user setting (default SELECT *,
        but users can save a narrower custom query). A pre-#1816 custom query
        that doesn't select devSSID/devVlan must not crash the whole device
        loop - it should fall back to blank for just those two fields."""
        device = _device()
        del device["devSSID"]
        del device["devVlan"]
        attrs = mqtt.build_device_tracker_attributes(device, [device], "My Device")
        assert attrs["ssid"] == ""
        assert attrs["vlan"] == ""


class TestPublishMqttBoundedRetry:
    def _client(self, publish_return):
        client = MagicMock()
        client.publish.return_value = publish_return
        return client

    def test_succeeds_immediately_on_first_try(self):
        mqtt.mqtt_connected_to_broker = True
        client = self._client((0, 1))
        with patch.object(mqtt.time, "sleep") as mock_sleep:
            assert mqtt.publish_mqtt(client, "topic", "payload") is True
        assert client.publish.call_count == 1
        mock_sleep.assert_not_called()

    def test_retries_then_succeeds(self):
        mqtt.mqtt_connected_to_broker = True
        client = MagicMock()
        client.publish.side_effect = [(1, 1), (1, 1), (0, 1)]
        with patch.object(mqtt.time, "sleep"):
            assert mqtt.publish_mqtt(client, "topic", "payload") is True
        assert client.publish.call_count == 3

    def test_gives_up_after_max_attempts_instead_of_hanging_forever(self):
        """The regression this guards against: a broker that always rejects
        the publish must not spin the caller indefinitely."""
        mqtt.mqtt_connected_to_broker = True
        client = self._client((1, 1))  # always fails
        with patch.object(mqtt.time, "sleep") as mock_sleep:
            assert mqtt.publish_mqtt(client, "topic", "payload") is False
        assert client.publish.call_count == mqtt._PUBLISH_MAX_ATTEMPTS
        assert mock_sleep.call_count == mqtt._PUBLISH_MAX_ATTEMPTS

    def test_aborts_immediately_when_not_connected(self):
        mqtt.mqtt_connected_to_broker = False
        client = self._client((0, 1))
        assert mqtt.publish_mqtt(client, "topic", "payload") is False
        client.publish.assert_not_called()

    def test_dict_payload_with_apostrophe_serializes_to_valid_json(self):
        """Regression guard: a prior post-serialization .replace("'", '"')
        corrupted any string value containing an apostrophe (e.g. an SSID
        like "Bob's WiFi!") into invalid JSON. json.dumps() output must be
        published unmodified."""
        mqtt.mqtt_connected_to_broker = True
        client = self._client((0, 1))
        mqtt.publish_mqtt(client, "topic", {"ssid": "Bob's WiFi!"})
        published_payload = client.publish.call_args.kwargs["payload"]
        assert json.loads(published_payload) == {"ssid": "Bob's WiFi!"}
