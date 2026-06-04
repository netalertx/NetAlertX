"""
NetAlertX Notification Text Template Tests

Tests the template substitution and section header toggle in
construct_notifications(). All tests mock get_setting_value to avoid
database/config dependencies.

License: GNU GPLv3
"""

import sys
import os
import unittest
from unittest.mock import patch

# Add the server directory to the path for imports
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server"])


def _make_json(section, devices, column_names, title="Test Section"):
    """Helper to build the JSON structure expected by construct_notifications."""
    return {
        section: devices,
        f"{section}_meta": {
            "title": title,
            "columnNames": column_names,
        },
    }


SAMPLE_NEW_DEVICES = [
    {
        "devName": "MyPhone",
        "eveMac": "aa:bb:cc:dd:ee:ff",
        "devVendor": "",
        "eveIp": "192.168.1.42",
        "eveDateTime": "2025-01-15 10:30:00",
        "eveEventType": "New Device",
        "devComments": "",
    },
    {
        "devName": "Laptop",
        "eveMac": "11:22:33:44:55:66",
        "devVendor": "Dell",
        "eveIp": "192.168.1.99",
        "eveDateTime": "2025-01-15 11:00:00",
        "eveEventType": "New Device",
        "devComments": "Office",
    },
]

NEW_DEVICE_COLUMNS = ["devName", "eveMac", "devVendor", "eveIp", "eveDateTime", "eveEventType", "devComments"]


class TestConstructNotificationsTemplates(unittest.TestCase):
    """Tests for template substitution in construct_notifications."""

    def _setting_factory(self, overrides=None):
        """Return a mock get_setting_value that resolves from overrides dict."""
        settings = overrides or {}

        def mock_get(key):
            return settings.get(key, "")

        return mock_get

    # -----------------------------------------------------------------
    # Empty section should always return ("", "") regardless of settings
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_empty_section_returns_empty(self, mock_setting):
        from models.notification_instance import construct_notifications

        mock_setting.return_value = ""
        json_data = _make_json("new_devices", [], [])
        html, text = construct_notifications(json_data, "new_devices")
        self.assertEqual(html, "")
        self.assertEqual(text, "")

    # -----------------------------------------------------------------
    # Legacy fallback: no template → vertical Header: Value per device
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_legacy_fallback_no_template(self, mock_setting):
        from models.notification_instance import construct_notifications

        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": True,
            "NTFPRCS_TEXT_TEMPLATE_new_devices": "",
        })

        json_data = _make_json(
            "new_devices", SAMPLE_NEW_DEVICES, NEW_DEVICE_COLUMNS, "🆕 New devices"
        )
        html, text = construct_notifications(json_data, "new_devices")

        # Section header must be present
        self.assertIn("🆕 New devices", text)
        self.assertIn("---------", text)

        # Legacy format: each header appears as "Header: \tValue"
        self.assertIn("eveMac:", text)
        self.assertIn("aa:bb:cc:dd:ee:ff", text)
        self.assertIn("devName:", text)
        self.assertIn("MyPhone", text)

        # HTML must still be generated
        self.assertNotEqual(html, "")

    # -----------------------------------------------------------------
    # Template substitution: single-line format per device
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_template_substitution(self, mock_setting):
        from models.notification_instance import construct_notifications

        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": True,
            "NTFPRCS_TEXT_TEMPLATE_new_devices": "{devName} ({eveMac}) - {eveIp}",
        })

        json_data = _make_json(
            "new_devices", SAMPLE_NEW_DEVICES, NEW_DEVICE_COLUMNS, "🆕 New devices"
        )
        _, text = construct_notifications(json_data, "new_devices")

        self.assertIn("MyPhone (aa:bb:cc:dd:ee:ff) - 192.168.1.42", text)
        self.assertIn("Laptop (11:22:33:44:55:66) - 192.168.1.99", text)

    # -----------------------------------------------------------------
    # Missing field: {NonExistent} left as-is (safe failure)
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_missing_field_safe_failure(self, mock_setting):
        from models.notification_instance import construct_notifications

        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": True,
            "NTFPRCS_TEXT_TEMPLATE_new_devices": "{devName} - {NonExistent}",
        })

        json_data = _make_json(
            "new_devices", SAMPLE_NEW_DEVICES, NEW_DEVICE_COLUMNS, "🆕 New devices"
        )
        _, text = construct_notifications(json_data, "new_devices")

        self.assertIn("MyPhone - {NonExistent}", text)
        self.assertIn("Laptop - {NonExistent}", text)

    # -----------------------------------------------------------------
    # Section headers disabled: no title/separator in text output
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_section_headers_disabled(self, mock_setting):
        from models.notification_instance import construct_notifications

        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": False,
            "NTFPRCS_TEXT_TEMPLATE_new_devices": "{devName} ({eveMac})",
        })

        json_data = _make_json(
            "new_devices", SAMPLE_NEW_DEVICES, NEW_DEVICE_COLUMNS, "🆕 New devices"
        )
        _, text = construct_notifications(json_data, "new_devices")

        self.assertNotIn("🆕 New devices", text)
        self.assertNotIn("---------", text)
        # Template output still present
        self.assertIn("MyPhone (aa:bb:cc:dd:ee:ff)", text)

    # -----------------------------------------------------------------
    # Section headers enabled (default when setting absent/empty)
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_section_headers_default_enabled(self, mock_setting):
        from models.notification_instance import construct_notifications

        # Simulate setting not configured (returns empty string)
        mock_setting.side_effect = self._setting_factory({})

        json_data = _make_json(
            "new_devices", SAMPLE_NEW_DEVICES, NEW_DEVICE_COLUMNS, "🆕 New devices"
        )
        _, text = construct_notifications(json_data, "new_devices")

        # Headers should be shown by default
        self.assertIn("🆕 New devices", text)
        self.assertIn("---------", text)

    # -----------------------------------------------------------------
    # Mixed valid and invalid fields in same template
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_mixed_valid_and_invalid_fields(self, mock_setting):
        from models.notification_instance import construct_notifications

        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": True,
            "NTFPRCS_TEXT_TEMPLATE_new_devices": "{devName} ({BadField}) - {eveIp}",
        })

        json_data = _make_json(
            "new_devices", SAMPLE_NEW_DEVICES, NEW_DEVICE_COLUMNS, "🆕 New devices"
        )
        _, text = construct_notifications(json_data, "new_devices")

        self.assertIn("MyPhone ({BadField}) - 192.168.1.42", text)

    # -----------------------------------------------------------------
    # Down devices section uses same column names as all other sections
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_down_devices_template(self, mock_setting):
        from models.notification_instance import construct_notifications

        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": True,
            "NTFPRCS_TEXT_TEMPLATE_down_devices": "{devName} ({eveMac}) down since {eveDateTime}",
        })

        down_devices = [
            {
                "devName": "Router",
                "eveMac": "ff:ee:dd:cc:bb:aa",
                "devVendor": "Cisco",
                "eveIp": "10.0.0.1",
                "eveDateTime": "2025-01-15 08:00:00",
                "eveEventType": "Device Down",
                "devComments": "",
            }
        ]
        columns = ["devName", "eveMac", "devVendor", "eveIp", "eveDateTime", "eveEventType", "devComments"]

        json_data = _make_json("down_devices", down_devices, columns, "🔴 Down devices")
        _, text = construct_notifications(json_data, "down_devices")

        self.assertIn("Router (ff:ee:dd:cc:bb:aa) down since 2025-01-15 08:00:00", text)

    # -----------------------------------------------------------------
    # Down reconnected section uses same unified column names
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_down_reconnected_template(self, mock_setting):
        from models.notification_instance import construct_notifications

        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": True,
            "NTFPRCS_TEXT_TEMPLATE_down_reconnected": "{devName} ({eveMac}) reconnected at {eveDateTime}",
        })

        reconnected = [
            {
                "devName": "Switch",
                "eveMac": "aa:11:bb:22:cc:33",
                "devVendor": "Netgear",
                "eveIp": "10.0.0.2",
                "eveDateTime": "2025-01-15 09:30:00",
                "eveEventType": "Down Reconnected",
                "devComments": "",
            }
        ]
        columns = ["devName", "eveMac", "devVendor", "eveIp", "eveDateTime", "eveEventType", "devComments"]

        json_data = _make_json("down_reconnected", reconnected, columns, "🔁 Reconnected down devices")
        _, text = construct_notifications(json_data, "down_reconnected")

        self.assertIn("Switch (aa:11:bb:22:cc:33) reconnected at 2025-01-15 09:30:00", text)

    # -----------------------------------------------------------------
    # HTML output is unchanged regardless of template config
    # -----------------------------------------------------------------
    @patch("models.notification_instance.get_setting_value")
    def test_html_unchanged_with_template(self, mock_setting):
        from models.notification_instance import construct_notifications

        # Get HTML without template
        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": True,
            "NTFPRCS_TEXT_TEMPLATE_new_devices": "",
        })
        json_data = _make_json(
            "new_devices", SAMPLE_NEW_DEVICES, NEW_DEVICE_COLUMNS, "🆕 New devices"
        )
        html_without, _ = construct_notifications(json_data, "new_devices")

        # Get HTML with template
        mock_setting.side_effect = self._setting_factory({
            "NTFPRCS_TEXT_SECTION_HEADERS": True,
            "NTFPRCS_TEXT_TEMPLATE_new_devices": "{devName} ({eveMac})",
        })
        html_with, _ = construct_notifications(json_data, "new_devices")

        self.assertEqual(html_without, html_with)


if __name__ == "__main__":
    unittest.main()
