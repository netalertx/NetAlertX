"""Tests for the adguard_import (ADGUARDIMP) plugin's presence detection.

script.py is loaded with its NetAlertX-internal dependencies (plugin_helper,
logger, helper, const, conf, pytz, utils.crypto_utils) stubbed out - same
approach test_wificanary.py/test_dockerdisc.py use - so these run without the
full devcontainer environment. `ag_request()` is mocked per test rather than
actually calling AdGuard Home's API.

Regression coverage for GitHub issue #1813: devices imported from AdGuard
Home showed as permanently Online. Root cause: scanPresence was never mapped,
so it defaulted to 1 (server/db/schema/app.sql) for every row on every run -
but auto_clients (from /control/clients) is AdGuard's historical DNS-seen
roster, not a live-presence feed. Fix: scanPresence is now computed per
device from whether it currently holds an active *dynamic* DHCP lease
(/control/dhcp/status's `leases`, not `static_leases` - a static reservation
is a permanent binding, not evidence of current connectivity), passed via
helpVal4 (config.json maps helpVal4 -> scanPresence).
"""

import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])


def _load_adguard_import_module():
    missing_module = object()
    previous_modules = {}

    def stub(name, **attributes):
        previous_modules[name] = sys.modules.get(name, missing_module)
        module = types.ModuleType(name)
        for attribute, value in attributes.items():
            setattr(module, attribute, value)
        sys.modules[name] = module

    stub("plugin_helper", Plugin_Objects=MagicMock, string_to_fake_mac=lambda ip: f"fake:{ip}")
    stub("logger", mylog=MagicMock(), Logger=MagicMock())
    stub("helper", get_setting_value=MagicMock(return_value="UTC"))
    stub("const", logPath="/tmp")
    stub("utils.crypto_utils", string_to_fake_mac=lambda ip: f"fake:{ip}")
    stub("conf", tz=None)
    stub("pytz", timezone=MagicMock(return_value="UTC"))

    module_path = Path(__file__).resolve().parents[2] / "server" / "plugins" / "adguard_import" / "adguard_import.py"
    spec = importlib.util.spec_from_file_location("adguard_import_script", module_path)
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


adguard_import = _load_adguard_import_module()


def _settings(overrides=None):
    base = {
        "ADGUARDIMP_SERVER": "adguard.local",
        "ADGUARDIMP_PORT": 80,
        "ADGUARDIMP_PROTOCOL": "http",
        "ADGUARDIMP_USER": "",
        "ADGUARDIMP_PASS": "",
        "ADGUARDIMP_FAKE_MAC": False,
        "ADGUARDIMP_RUN_TIMEOUT": 30,
    }
    base.update(overrides or {})
    return base


def _run_main(clients_response, dhcp_response, settings_overrides=None):
    """Run main() with ag_request mocked to return the given API payloads,
    and capture every add_object() call's kwargs, keyed by primaryId (MAC)."""
    settings = _settings(settings_overrides)
    calls = {}

    def fake_add_object(**kwargs):
        calls[kwargs["primaryId"]] = kwargs

    def fake_ag_request(path, *args, **kwargs):
        if path == "/control/clients":
            return clients_response
        if path == "/control/dhcp/status":
            return dhcp_response
        raise AssertionError(f"unexpected path: {path}")

    with patch.object(adguard_import, "get_setting_value", side_effect=lambda k: settings.get(k)):
        with patch.object(adguard_import, "ag_request", side_effect=fake_ag_request):
            adguard_import.plugin_objects.add_object = fake_add_object
            adguard_import.plugin_objects.write_result_file = MagicMock()
            adguard_import.main()

    return calls


class TestPresenceFromDynamicLease:
    def test_device_with_active_dynamic_lease_is_present(self):
        clients = {"auto_clients": [{"ip": "192.168.1.10", "name": "laptop", "source": "DHCP"}]}
        dhcp = {"leases": [{"ip": "192.168.1.10", "mac": "aa:bb:cc:dd:ee:01"}], "static_leases": []}

        calls = _run_main(clients, dhcp)

        assert calls["AA:BB:CC:DD:EE:01"]["helpVal4"] == "1"

    def test_device_known_only_from_auto_clients_is_not_present(self):
        """The exact bug from #1813: a device AdGuard has historically seen
        via DNS traffic, with no current DHCP lease, must not be asserted
        as currently online."""
        clients = {"auto_clients": [{"ip": "192.168.1.20", "name": "old-phone", "source": "RDNS"}]}
        dhcp = {"leases": [], "static_leases": [{"ip": "192.168.1.20", "mac": "aa:bb:cc:dd:ee:02"}]}

        calls = _run_main(clients, dhcp)

        assert calls["AA:BB:CC:DD:EE:02"]["helpVal4"] == "0"

    def test_static_reservation_alone_is_not_present(self):
        """A static DHCP reservation is a permanent binding, not evidence the
        device is currently connected - only an active entry in the dynamic
        `leases` array counts."""
        clients = {"auto_clients": [{"ip": "192.168.1.30", "name": "printer", "source": "DHCP"}]}
        dhcp = {"leases": [], "static_leases": [{"ip": "192.168.1.30", "mac": "aa:bb:cc:dd:ee:03"}]}

        calls = _run_main(clients, dhcp)

        assert calls["AA:BB:CC:DD:EE:03"]["helpVal4"] == "0"

    def test_device_with_both_static_and_dynamic_entry_is_present(self):
        """A device can have a static reservation *and* currently be
        connected (holding the active lease that reservation grants it) -
        the dynamic-lease signal should still mark it present."""
        clients = {"auto_clients": [{"ip": "192.168.1.40", "name": "server", "source": "DHCP"}]}
        dhcp = {
            "leases": [{"ip": "192.168.1.40", "mac": "aa:bb:cc:dd:ee:04"}],
            "static_leases": [{"ip": "192.168.1.40", "mac": "aa:bb:cc:dd:ee:04"}],
        }

        calls = _run_main(clients, dhcp)

        assert calls["AA:BB:CC:DD:EE:04"]["helpVal4"] == "1"

    def test_fake_mac_device_is_never_present(self):
        """A device with no real MAC (identified only via a synthesized fake
        MAC) can never match a real DHCP lease's MAC, so it can't be
        asserted present."""
        clients = {"auto_clients": [{"ip": "192.168.1.50", "name": "unknown", "source": "RDNS"}]}
        dhcp = {"leases": [], "static_leases": []}

        calls = _run_main(clients, dhcp, settings_overrides={"ADGUARDIMP_FAKE_MAC": True})

        assert len(calls) == 1
        (only_call,) = calls.values()
        assert only_call["helpVal4"] == "0"

    def test_multiple_devices_mixed_presence(self):
        clients = {
            "auto_clients": [
                {"ip": "192.168.1.60", "name": "online-device", "source": "DHCP"},
                {"ip": "192.168.1.61", "name": "offline-device", "source": "RDNS"},
            ]
        }
        dhcp = {
            "leases": [{"ip": "192.168.1.60", "mac": "aa:bb:cc:dd:ee:60"}],
            "static_leases": [{"ip": "192.168.1.61", "mac": "aa:bb:cc:dd:ee:61"}],
        }

        calls = _run_main(clients, dhcp)

        assert calls["AA:BB:CC:DD:EE:60"]["helpVal4"] == "1"
        assert calls["AA:BB:CC:DD:EE:61"]["helpVal4"] == "0"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
