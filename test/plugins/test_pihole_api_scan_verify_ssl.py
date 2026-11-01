"""Tests for the "Verify SSL" setting of the pihole_api_scan (PIHOLEAPI) plugin.

pihole_api_scan.py is loaded with its NetAlertX-internal dependencies stubbed
out (same approach as test_adguard_import.py), so these tests run without a
Pi-hole instance. Only the HTTP call to Pi-hole is mocked; main() and
pihole_api_auth() run for real.
"""

import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])


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

    stub("plugin_helper", Plugin_Objects=MagicMock, is_mac=MagicMock(return_value=True))
    stub("utils.datetime_utils", timeNowUTC=MagicMock())
    stub("logger", mylog=MagicMock(), Logger=MagicMock())
    stub("helper", get_setting_value=MagicMock(return_value="UTC"))
    stub("const", logPath="/tmp")
    stub("conf", tz=None)
    stub("pytz", timezone=MagicMock(return_value="UTC"))
    stub("utils.crypto_utils", string_to_fake_mac=MagicMock(return_value="fa:ce:00:00:00:01"))

    module_path = Path(__file__).resolve().parents[2] / "server" / "plugins" / "pihole_api_scan" / "pihole_api_scan.py"
    spec = importlib.util.spec_from_file_location("pihole_api_scan_verify_ssl_script", module_path)
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


def _use_settings(monkeypatch, settings):
    """Serve settings to main() via get_setting_value, and restore the module globals main() rebinds after the test."""
    # raising=False: a global may only come into existence when main() runs.
    for name in ("PIHOLEAPI_URL", "PIHOLEAPI_PASSWORD", "PIHOLEAPI_API_MAXCLIENTS", "PIHOLEAPI_VERIFY_SSL",
                 "PIHOLEAPI_RUN_TIMEOUT", "PIHOLEAPI_GET_OFFLINE", "PIHOLEAPI_CONSIDER_ONLINE"):
        monkeypatch.setattr(pihole_api_scan, name, getattr(pihole_api_scan, name, None), raising=False)
    monkeypatch.setattr(pihole_api_scan, "get_setting_value", settings.get)


class TestVerifySsl:
    @pytest.mark.parametrize("verify_ssl", [True, False])
    def test_verify_ssl_setting_reaches_pihole_request(self, monkeypatch, verify_ssl):
        """The VERIFY_SSL setting (key PIHOLEAPI_VERIFY_SSL) is what main() passes as verify= to the Pi-hole API."""
        _use_settings(monkeypatch, {
            "PIHOLEAPI_URL": "https://pi.hole/",
            "PIHOLEAPI_PASSWORD": "secret",
            "PIHOLEAPI_RUN_TIMEOUT": 30,
            "PIHOLEAPI_VERIFY_SSL": verify_ssl,
        })
        auth_response = MagicMock()
        auth_response.json.return_value = {"session": {"valid": False}}
        post = MagicMock(return_value=auth_response)
        monkeypatch.setattr(pihole_api_scan.requests, "post", post)
        monkeypatch.setattr(pihole_api_scan.requests.packages.urllib3, "disable_warnings", MagicMock())

        pihole_api_scan.main()

        assert post.call_args.kwargs["verify"] is verify_ssl
