"""Tests for plugin_manager.handle_test and _run_test_cmd."""

import sys
import unittest
from unittest.mock import MagicMock, patch, call

import server.plugin as plugin_module
from server.plugin import plugin_manager


def _make_plugin(prefix, data_source="template", cmd_value=None, settings=None):
    """Build a minimal plugin dict for testing."""
    plugin = {
        "unique_prefix": prefix,
        "data_source": data_source,
        "settings": list(settings or []),
        "params": [],
    }
    if cmd_value is not None:
        plugin["settings"].append({
            "function": "CMD",
            "value": cmd_value,
        })
    return plugin


class TestRunTestCmd(unittest.TestCase):
    """Tests for _run_test_cmd (non-script plugin test execution)."""

    def _make_manager(self, plugins):
        with patch.object(plugin_manager, "__init__", return_value=None):
            mgr = plugin_manager.__new__(plugin_manager)
        mgr.db = MagicMock()
        mgr.all_plugins = plugins
        return mgr

    @patch.object(plugin_module, "write_notification")
    @patch.object(plugin_module.subprocess, "check_output", return_value="[LDAP Test] ✅ SUCCESS: Connected\n")
    def test_run_test_cmd_sends_notification(self, mock_subproc, mock_notify):
        """Output from CMD should appear in an in-app notification."""
        plugin = _make_plugin("LDAP", cmd_value="echo hello")
        mgr = self._make_manager([plugin])

        mgr._run_test_cmd(plugin)

        mock_subproc.assert_called_once()
        mock_notify.assert_called_once()
        content = mock_notify.call_args[0][0]
        self.assertIn("[LDAP Test]", content)
        self.assertIn("SUCCESS", content)

    @patch.object(plugin_module, "write_notification")
    @patch.object(plugin_module.subprocess, "check_output", return_value="test output\n")
    def test_run_test_cmd_resolves_setting_wildcards(self, mock_subproc, mock_notify):
        """Setting wildcards like {LDAP_test_username} should be resolved."""
        plugin = _make_plugin(
            "LDAP",
            cmd_value='python3 /app/front/plugins/auth_ldap/test_ldap.py --test-user="{LDAP_test_username}"',
            settings=[
                {"function": "test_username", "value": "jdoe"},
            ],
        )
        mgr = self._make_manager([plugin])

        mgr._run_test_cmd(plugin)

        # Verify the command was called with the resolved wildcard
        cmd_args = mock_subproc.call_args[0][0]
        joined = " ".join(cmd_args)
        self.assertIn("jdoe", joined)
        self.assertNotIn("{LDAP_test_username}", joined)

    @patch.object(plugin_module, "write_notification")
    def test_run_test_cmd_no_cmd_setting(self, mock_notify):
        """Plugin with no CMD setting should produce an alert notification."""
        plugin = _make_plugin("LDAP", cmd_value=None)
        mgr = self._make_manager([plugin])

        mgr._run_test_cmd(plugin)

        mock_notify.assert_called_once()
        content = mock_notify.call_args[0][0]
        self.assertIn("No CMD setting", content)

    @patch.object(plugin_module, "write_notification")
    @patch.object(plugin_module.subprocess, "check_output", side_effect=Exception("connection refused"))
    def test_run_test_cmd_handles_exception(self, mock_subproc, mock_notify):
        """Exceptions should be caught and reported in the notification."""
        plugin = _make_plugin("LDAP", cmd_value="python3 test.py")
        mgr = self._make_manager([plugin])

        mgr._run_test_cmd(plugin)

        mock_notify.assert_called_once()
        content = mock_notify.call_args[0][0]
        self.assertIn("connection refused", content)

    @patch.object(plugin_module, "write_notification")
    @patch.object(plugin_module.subprocess, "check_output")
    def test_run_test_cmd_truncates_long_output(self, mock_subproc, mock_notify):
        """Output longer than 2000 chars should be truncated."""
        mock_subproc.return_value = "A" * 5000 + "\n"
        plugin = _make_plugin("LDAP", cmd_value="echo long")
        mgr = self._make_manager([plugin])

        mgr._run_test_cmd(plugin)

        content = mock_notify.call_args[0][0]
        # Content = prefix + output; output portion should be <=2000 chars
        self.assertLessEqual(len(content), 2100)  # prefix + 2000


class TestHandleTest(unittest.TestCase):
    """Tests for handle_test dispatching between script and non-script plugins."""

    def _make_manager(self, plugins):
        with patch.object(plugin_manager, "__init__", return_value=None):
            mgr = plugin_manager.__new__(plugin_manager)
        mgr.db = MagicMock()
        mgr.all_plugins = plugins
        return mgr

    def test_handle_test_nonscript_calls_run_test_cmd(self):
        """Non-script plugins should go through _run_test_cmd, not handle_run."""
        plugin = _make_plugin("LDAP", data_source="template", cmd_value="echo ok")
        mgr = self._make_manager([plugin])

        with patch.object(mgr, "_run_test_cmd") as mock_cmd, \
             patch.object(mgr, "handle_run") as mock_run:
            mgr.handle_test("LDAP")

        mock_cmd.assert_called_once_with(plugin)
        mock_run.assert_not_called()

    @patch.object(plugin_module, "NotificationInstance")
    @patch.object(plugin_module, "get_file_content", return_value='[{"body":{"attachments":[{"text":"sample"}]}}]')
    def test_handle_test_script_uses_existing_flow(self, mock_gfc, mock_notif_cls):
        """Script-type plugins should use the existing handle_run flow."""
        plugin = _make_plugin("EMAIL", data_source="script", cmd_value="echo ok")
        mgr = self._make_manager([plugin])

        with patch.object(mgr, "_run_test_cmd") as mock_cmd, \
             patch.object(mgr, "handle_run") as mock_run:
            mgr.handle_test("EMAIL")

        mock_run.assert_called_once_with("EMAIL")
        mock_cmd.assert_not_called()

    @patch.object(plugin_module, "write_notification")
    def test_handle_test_unknown_plugin_sends_notification(self, mock_notify):
        """Unknown plugin prefix should produce an alert notification."""
        mgr = self._make_manager([])

        mgr.handle_test("NONEXISTENT")

        mock_notify.assert_called_once()
        content = mock_notify.call_args[0][0]
        self.assertIn("not found", content)
