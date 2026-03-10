"""
Test for atomicity of device updates with source-tracking.

Verifies that:
1. If source-tracking fails, the device row is rolled back.
2. If source-tracking succeeds, device row and sources are both committed.
3. Database remains consistent in both scenarios.
"""

import sys
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


# Add server and plugins to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'front', 'plugins'))

from models.device_instance import DeviceInstance  # noqa: E402 [flake8 lint suppression]
from plugin_helper import normalize_mac  # noqa: E402 [flake8 lint suppression]


class TestDeviceAtomicity(unittest.TestCase):
    """Test atomic transactions for device updates with source-tracking."""

    def setUp(self):
        """Create an in-memory SQLite DB for testing."""
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db_path = self.test_db.name
        self.test_db.close()

        # Create minimal schema
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Create Devices table with source-tracking columns
        cur.execute("""
            CREATE TABLE Devices (
                devMac TEXT PRIMARY KEY,
                devName TEXT,
                devOwner TEXT,
                devType TEXT,
                devVendor TEXT,
                devIcon TEXT,
                devFavorite INTEGER DEFAULT 0,
                devGroup TEXT,
                devLocation TEXT,
                devComments TEXT,
                devParentMAC TEXT,
                devParentPort TEXT,
                devSSID TEXT,
                devSite TEXT,
                devStaticIP INTEGER DEFAULT 0,
                devScan INTEGER DEFAULT 0,
                devAlertEvents INTEGER DEFAULT 0,
                devAlertDown INTEGER DEFAULT 0,
                devCanSleep INTEGER DEFAULT 0,
                devParentRelType TEXT DEFAULT 'default',
                devReqNicsOnline INTEGER DEFAULT 0,
                devSkipRepeated INTEGER DEFAULT 0,
                devIsNew INTEGER DEFAULT 0,
                devIsArchived INTEGER DEFAULT 0,
                devLastConnection TEXT,
                devFirstConnection TEXT,
                devLastIP TEXT,
                devGUID TEXT,
                devCustomProps TEXT,
                devSourcePlugin TEXT,
                devNameSource TEXT,
                devTypeSource TEXT,
                devVendorSource TEXT,
                devIconSource TEXT,
                devGroupSource TEXT,
                devLocationSource TEXT,
                devCommentsSource TEXT,
                devMacSource TEXT,
                devVlan TEXT,
                devForceStatus STRING DEFAULT NULL
            )
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        """Clean up test database."""
        if os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)

    def _get_test_db_connection(self):
        """Override database connection for testing."""
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_create_new_device_atomicity(self):
        """
        Test that device creation and source-tracking are atomic.
        If source tracking fails, the device should not be created.
        """
        device_instance = DeviceInstance()
        test_mac = normalize_mac("aa:bb:cc:dd:ee:ff")

        # Patch at module level where it's used
        with patch('models.device_instance.get_temp_db_connection', self._get_test_db_connection):
            # Create a new device
            data = {
                "createNew": True,
                "devMac": test_mac,
                "devName": "Test Device",
                "devOwner": "John Doe",
                "devType": "Laptop",
            }

            result = device_instance.setDeviceData(test_mac, data)

            # Verify success
            self.assertTrue(result["success"], f"Device creation failed: {result}")

            # Verify device exists
            conn = self._get_test_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM Devices WHERE devMac = ?", (test_mac,))
            device = cur.fetchone()
            conn.close()

            self.assertIsNotNone(device, "Device was not created")
            self.assertEqual(device["devName"], "Test Device")

            # Verify source tracking was set
            self.assertEqual(device["devMacSource"], "NEWDEV")
            self.assertEqual(device["devNameSource"], "NEWDEV")

    def test_update_device_with_source_tracking_atomicity(self):
        """
        Test that device update and source-tracking are atomic.
        If source tracking fails, the device update should be rolled back.
        """
        device_instance = DeviceInstance()
        test_mac = normalize_mac("aa:bb:cc:dd:ee:ff")

        # Create initial device
        conn = self._get_test_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Devices (
                devMac, devName, devOwner, devType,
                                devNameSource, devTypeSource
            ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (test_mac, "Old Name", "Old Owner", "Desktop", "PLUGIN", "PLUGIN"))
        conn.commit()
        conn.close()

        # Patch database connection
        with patch('models.device_instance.get_temp_db_connection', self._get_test_db_connection):
            with patch('models.device_instance.enforce_source_on_user_update') as mock_enforce:
                mock_enforce.return_value = None
                data = {
                    "createNew": False,
                    "devMac": test_mac,
                    "devName": "New Name",
                    "devOwner": "New Owner",
                }

                result = device_instance.setDeviceData(test_mac, data)

            # Verify success
            self.assertTrue(result["success"], f"Device update failed: {result}")

            # Verify device was updated
            conn = self._get_test_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM Devices WHERE devMac = ?", (test_mac,))
            device = cur.fetchone()
            conn.close()

            self.assertEqual(device["devName"], "New Name")
            self.assertEqual(device["devOwner"], "New Owner")

    def test_source_tracking_failure_rolls_back_device(self):
        """
        Test that if enforce_source_on_user_update fails, the entire
        transaction is rolled back (device and sources).
        """
        device_instance = DeviceInstance()
        test_mac = normalize_mac("aa:bb:cc:dd:ee:ff")

        # Create initial device
        conn = self._get_test_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Devices (
                devMac, devName, devOwner, devType,
                                devNameSource, devTypeSource
            ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (test_mac, "Original Name", "Original Owner", "Desktop", "PLUGIN", "PLUGIN"))
        conn.commit()
        conn.close()

        # Patch database connection and mock source enforcement failure
        with patch('models.device_instance.get_temp_db_connection', self._get_test_db_connection):
            with patch('models.device_instance.enforce_source_on_user_update') as mock_enforce:
                # Simulate source tracking failure
                mock_enforce.side_effect = Exception("Source tracking error")

                data = {
                    "createNew": False,
                    "devMac": test_mac,
                    "devName": "Failed Update",
                    "devOwner": "Failed Owner",
                }

                result = device_instance.setDeviceData(test_mac, data)

            # Verify error response
            self.assertFalse(result["success"])
            self.assertIn("Source tracking failed", result["error"])

            # Verify device was NOT updated (rollback successful)
            conn = self._get_test_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM Devices WHERE devMac = ?", (test_mac,))
            device = cur.fetchone()
            conn.close()

            self.assertEqual(device["devName"], "Original Name", "Device should not have been updated on source tracking failure")
            self.assertEqual(device["devOwner"], "Original Owner", "Device should not have been updated on source tracking failure")


if __name__ == "__main__":
    unittest.main()
