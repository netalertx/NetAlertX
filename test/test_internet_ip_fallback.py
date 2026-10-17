import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'front', 'plugins', 'internet_ip', 'script.py')


def _load_script():
    """Load the plugin script with its NetAlertX-runtime imports stubbed out."""
    stubs = {}
    for name in ('plugin_helper', 'utils', 'utils.datetime_utils', 'logger', 'helper', 'const', 'conf', 'pytz'):
        stubs[name] = MagicMock()
    stubs['helper'].get_setting_value.return_value = 'UTC'
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location('internet_ip_script', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def test_fallback_requests_ipv4_over_https_with_timeouts():
    script = _load_script()
    with patch.object(script.subprocess, 'check_output', return_value='203.0.113.7\n') as co:
        ip, _ = script.fallback_check_ip()
    cmd = co.call_args[0][0]
    assert ip == '203.0.113.7'
    assert '-4' in cmd
    assert cmd[-1] == 'https://ifconfig.me/ip'
    assert '--connect-timeout' in cmd and '--max-time' in cmd


def test_fallback_rejects_ipv6_response():
    script = _load_script()
    with patch.object(script.subprocess, 'check_output', return_value='2001:db8::1\n'):
        ip, _ = script.fallback_check_ip()
    assert ip == script.no_internet_ip
