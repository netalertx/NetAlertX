"""
Tests for the omada_sdn_openapi plugin's device/client normalization,
specifically filtering out disconnected devices by status.

Run from inside the NetAlertX container, or locally - NetAlertX-specific
modules are stubbed out automatically before the script is imported.

    pytest test/plugins/test_omada_sdn_openapi.py -v
"""

import importlib.util
import os
import sys
import tempfile
import types
from unittest.mock import MagicMock

_tmp_log = tempfile.mkdtemp()

_stubbed_module_names = []


def _stub(name: str, **attrs):
    """Register an absent dependency stub and track it for cleanup after importing the plugin."""
    if name not in sys.modules:
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
        _stubbed_module_names.append(name)


_stub("conf")
_stub("const", logPath=_tmp_log)
_stub(
    "plugin_helper",
    Plugin_Objects=MagicMock,
    is_typical_router_ip=lambda ip: False,
    is_mac=lambda v: isinstance(v, str) and len(v.split(":")) == 6,
)
_stub("logger", mylog=lambda *a: None, Logger=MagicMock)
_stub("helper", get_setting_value=lambda k: "UTC" if k == "TIMEZONE" else "")

if "urllib3" not in sys.modules:
    _urllib3 = types.ModuleType("urllib3")
    _urllib3.disable_warnings = lambda *a, **k: None
    _urllib3_exc = types.ModuleType("urllib3.exceptions")
    _urllib3_exc.InsecureRequestWarning = type("InsecureRequestWarning", (Warning,), {})
    _urllib3.exceptions = _urllib3_exc
    sys.modules["urllib3"] = _urllib3
    sys.modules["urllib3.exceptions"] = _urllib3_exc
    _stubbed_module_names.extend(["urllib3", "urllib3.exceptions"])

_stub("requests")

if "packaging" not in sys.modules:
    _packaging = types.ModuleType("packaging")
    _packaging_version = types.ModuleType("packaging.version")
    _packaging_version.Version = lambda v: v
    _packaging_version.InvalidVersion = type("InvalidVersion", (Exception,), {})
    _packaging.version = _packaging_version
    sys.modules["packaging"] = _packaging
    sys.modules["packaging.version"] = _packaging_version
    _stubbed_module_names.extend(["packaging", "packaging.version"])

# omada_sdn_openapi's module file is named "script.py", same as several
# other plugins (e.g. adguard_export) - load it under a private module name
# instead of a plain `import script`, so this test doesn't collide with
# another plugin's test importing its own same-named script.py in the same
# pytest process.
_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "server", "plugins", "omada_sdn_openapi", "script.py")
_spec = importlib.util.spec_from_file_location("omada_sdn_openapi_script", _SCRIPT_PATH)
script = importlib.util.module_from_spec(_spec)
sys.modules["omada_sdn_openapi_script"] = script
_spec.loader.exec_module(script)

# Stops these fake entries from shadowing the real modules for other test
# files collected later in the same pytest session (script's own
# module-level `from x import y` bindings are already resolved by now).
for _name in _stubbed_module_names:
    sys.modules.pop(_name, None)

OmadaHelper = script.OmadaHelper

_CONNECTED_AP = {
    "mac": "aa:bb:cc:dd:ee:01",
    "ip": "192.168.0.11",
    "name": "office-ap",
    "type": "ap",
    "status": 1,
    "lastSeen": 0,
}

_DISCONNECTED_AP = {
    "mac": "aa:bb:cc:dd:ee:02",
    "ip": "192.168.0.12",
    "name": "garage-ap",
    "type": "ap",
    "status": 0,
    "lastSeen": 0,
}


def test_normalize_data_excludes_disconnected_device_by_default():
    """A disconnected AP/switch must not be reported as a device when offline devices aren't opted in."""
    result = OmadaHelper.normalize_data(
        [_CONNECTED_AP, _DISCONNECTED_AP], "device", "Default", "UTC", include_offline_devices=False
    )

    macs = [entry["mac_address"] for entry in result["response_result"]]
    assert "aa:bb:cc:dd:ee:01" in macs
    assert "aa:bb:cc:dd:ee:02" not in macs


def test_normalize_data_includes_disconnected_device_when_opted_in():
    """Setting include_offline_devices=True should surface disconnected devices too."""
    result = OmadaHelper.normalize_data(
        [_CONNECTED_AP, _DISCONNECTED_AP], "device", "Default", "UTC", include_offline_devices=True
    )

    macs = [entry["mac_address"] for entry in result["response_result"]]
    assert "aa:bb:cc:dd:ee:01" in macs
    assert "aa:bb:cc:dd:ee:02" in macs


def test_normalize_data_client_status_is_not_filtered():
    """The status-based filter only applies to devices - clients are already online-only from the API."""
    client = {
        "mac": "aa:bb:cc:dd:ee:03",
        "ip": "192.168.0.50",
        "name": "laptop",
        "deviceType": "pc",
        "status": 0,
        "lastSeen": 0,
    }

    result = OmadaHelper.normalize_data([client], "client", "Default", "UTC", include_offline_devices=False)

    macs = [entry["mac_address"] for entry in result["response_result"]]
    assert "aa:bb:cc:dd:ee:03" in macs
