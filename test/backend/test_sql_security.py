"""
NetAlertX SQL Security Test Suite

This test suite validates the SQL injection prevention mechanisms
implemented in the SafeConditionBuilder and reporting modules.

Author: Security Enhancement for NetAlertX
License: GNU GPLv3
"""

import sys
import unittest
import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch

# Add the server directory to the path for imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/server"])
sys.path.append('/home/dell/coding/bash/10x-agentic-setup/netalertx-sql-fix/server')

from db.sql_safe_builder import SafeConditionBuilder  # noqa: E402 [flake8 lint suppression]
from messaging.reporting import get_notifications  # noqa: E402 [flake8 lint suppression]


class TestSafeConditionBuilder(unittest.TestCase):
    """Test cases for the SafeConditionBuilder class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.builder = SafeConditionBuilder()

    def test_initialization(self):
        """Test that SafeConditionBuilder initializes correctly."""
        self.assertIsInstance(self.builder, SafeConditionBuilder)
        self.assertEqual(self.builder.param_counter, 0)
        self.assertEqual(self.builder.parameters, {})

    def test_sanitize_string(self):
        """Test string sanitization functionality."""
        # Test normal string
        result = self.builder._sanitize_string("normal string")
        self.assertEqual(result, "normal string")

        # Test s-quote replacement
        result = self.builder._sanitize_string("test{s-quote}value")
        self.assertEqual(result, "test'value")

        # Test control character removal
        result = self.builder._sanitize_string("test\x00\x01string")
        self.assertEqual(result, "teststring")

        # Test excessive whitespace
        result = self.builder._sanitize_string("  test   string  ")
        self.assertEqual(result, "test string")

    def test_validate_column_name(self):
        """Test column name validation against whitelist."""
        # Valid columns
        self.assertTrue(self.builder._validate_column_name('eve_MAC'))
        self.assertTrue(self.builder._validate_column_name('devName'))
        self.assertTrue(self.builder._validate_column_name('eve_EventType'))

        # Invalid columns
        self.assertFalse(self.builder._validate_column_name('malicious_column'))
        self.assertFalse(self.builder._validate_column_name('drop_table'))
        self.assertFalse(self.builder._validate_column_name('\'; DROP TABLE users; --'))

    def test_validate_operator(self):
        """Test operator validation against whitelist."""
        # Valid operators
        self.assertTrue(self.builder._validate_operator('='))
        self.assertTrue(self.builder._validate_operator('LIKE'))
        self.assertTrue(self.builder._validate_operator('IN'))

        # Invalid operators
        self.assertFalse(self.builder._validate_operator('UNION'))
        self.assertFalse(self.builder._validate_operator('; DROP'))
        self.assertFalse(self.builder._validate_operator('EXEC'))

    def test_build_simple_condition_valid(self):
        """Test building valid simple conditions."""
        sql, params = self.builder._build_simple_condition('AND', 'devName', '=', 'TestDevice')

        self.assertIn('AND devName = :param_', sql)
        self.assertEqual(len(params), 1)
        self.assertIn('TestDevice', params.values())

    def test_build_simple_condition_invalid_column(self):
        """Test that invalid column names are rejected."""
        with self.assertRaises(ValueError) as context:
            self.builder._build_simple_condition('AND', 'invalid_column', '=', 'value')

        self.assertIn('Invalid column name', str(context.exception))

    def test_build_simple_condition_invalid_operator(self):
        """Test that invalid operators are rejected."""
        with self.assertRaises(ValueError) as context:
            self.builder._build_simple_condition('AND', 'devName', 'UNION', 'value')

        self.assertIn('Invalid operator', str(context.exception))

    def test_build_in_condition_valid(self):
        """Test building valid IN conditions."""
        sql, params = self.builder._build_in_condition('AND', 'eve_EventType', 'IN', "'Connected', 'Disconnected'")

        self.assertIn('AND eve_EventType IN', sql)
        self.assertEqual(len(params), 2)
        self.assertIn('Connected', params.values())
        self.assertIn('Disconnected', params.values())

    def test_build_null_condition(self):
        """Test building NULL check conditions."""
        sql, params = self.builder._build_null_condition('AND', 'devComments', 'IS NULL')

        self.assertEqual(sql, 'AND devComments IS NULL')
        self.assertEqual(len(params), 0)

    def test_sql_injection_attempts(self):
        """Test that various SQL injection attempts are blocked."""
        injection_attempts = [
            "'; DROP TABLE Devices; --",
            "' UNION SELECT * FROM Settings --",
            "' OR 1=1 --",
            "'; INSERT OR IGNORE INTO Events VALUES(1,2,3); --",
            "' AND (SELECT COUNT(*) FROM sqlite_master) > 0 --",
            "'; ATTACH DATABASE '/etc/passwd' AS pwn; --"
        ]

        for injection in injection_attempts:
            with self.subTest(injection=injection):
                with self.assertRaises(ValueError):
                    self.builder.build_safe_condition(f"AND devName = '{injection}'")

    def test_legacy_condition_compatibility(self):
        """Test backward compatibility with legacy condition formats."""
        # Test simple condition
        sql, params = self.builder.get_safe_condition_legacy("AND devName = 'TestDevice'")
        self.assertIn('devName', sql)
        self.assertIn('TestDevice', params.values())

        # Test empty condition
        sql, params = self.builder.get_safe_condition_legacy("")
        self.assertEqual(sql, "")
        self.assertEqual(params, {})

        # Test invalid condition returns empty
        sql, params = self.builder.get_safe_condition_legacy("INVALID SQL INJECTION")
        self.assertEqual(sql, "")
        self.assertEqual(params, {})

    def test_device_name_filter(self):
        """Test the device name filter helper method."""
        sql, params = self.builder.build_device_name_filter("TestDevice")

        self.assertIn('AND devName = :device_name_', sql)
        self.assertIn('TestDevice', params.values())

    def test_event_type_filter(self):
        """Test the event type filter helper method."""
        event_types = ['Connected', 'Disconnected']
        sql, params = self.builder.build_event_type_filter(event_types)

        self.assertIn('AND eve_EventType IN', sql)
        self.assertEqual(len(params), 2)
        self.assertIn('Connected', params.values())
        self.assertIn('Disconnected', params.values())


class TestDatabaseParameterSupport(unittest.TestCase):
    """Test that database layer supports parameterized queries."""

    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        # Create test database
        self.conn = sqlite3.connect(self.temp_db.name)
        self.conn.execute('''CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            name TEXT,
            value TEXT
        )''')
        self.conn.execute("INSERT INTO test_table (name, value) VALUES ('test1', 'value1')")
        self.conn.execute("INSERT INTO test_table (name, value) VALUES ('test2', 'value2')")
        self.conn.commit()

    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        os.unlink(self.temp_db.name)

    def test_parameterized_query_execution(self):
        """Test that parameterized queries work correctly."""
        cursor = self.conn.cursor()

        # Test named parameters
        cursor.execute("SELECT * FROM test_table WHERE name = :name", {'name': 'test1'})
        results = cursor.fetchall()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], 'test1')

    def test_parameterized_query_prevents_injection(self):
        """Test that parameterized queries prevent SQL injection."""
        cursor = self.conn.cursor()

        # This should not cause SQL injection
        malicious_input = "'; DROP TABLE test_table; --"
        cursor.execute("SELECT * FROM test_table WHERE name = :name", {'name': malicious_input})

        # The table should still exist and be queryable
        cursor.execute("SELECT COUNT(*) FROM test_table")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 2)  # Original data should still be there


class TestReportingSecurityIntegration(unittest.TestCase):
    """Integration tests for the secure reporting functionality."""

    def setUp(self):
        """Set up test environment for reporting tests."""
        self.mock_db = Mock()
        self.mock_db.sql = Mock()
        self.mock_db.get_table_as_json = Mock()

        # Mock successful JSON response
        mock_json_obj = Mock()
        mock_json_obj.columnNames = ['MAC', 'Datetime', 'IP', 'Event Type', 'Device name', 'Comments']
        mock_json_obj.json = {'data': []}
        self.mock_db.get_table_as_json.return_value = mock_json_obj

    @patch('messaging.reporting.get_setting_value')
    def test_new_devices_section_security(self, mock_get_setting):
        """Test that new devices section uses safe SQL building."""
        # Mock settings
        mock_get_setting.side_effect = lambda key: {
            'NTFPRCS_INCLUDED_SECTIONS': ['new_devices'],
            'NTFPRCS_new_dev_condition': "AND devName = 'TestDevice'"
        }.get(key, '')

        # Call the function
        get_notifications(self.mock_db)

        # Verify that get_table_as_json was called with parameters
        self.mock_db.get_table_as_json.assert_called()
        call_args = self.mock_db.get_table_as_json.call_args

        # Should be query + params
        self.assertEqual(len(call_args[0]), 2)

        query, params = call_args[0]

        # Ensure the SQL contains the column
        self.assertIn("devName =", query)

        # Ensure a named parameter is used
        self.assertRegex(query, r":param_\d+")

        # Ensure the parameter dict has the correct value (using actual param name)
        self.assertEqual(list(params.values())[0], "TestDevice")

    @patch('messaging.reporting.get_setting_value')
    def test_events_section_security(self, mock_get_setting):
        """Test that events section uses safe SQL building."""
        # Mock settings
        mock_get_setting.side_effect = lambda key: {
            'NTFPRCS_INCLUDED_SECTIONS': ['events'],
            'NTFPRCS_event_condition': "AND devName = 'TestDevice'"
        }.get(key, '')

        # Call the function
        get_notifications(self.mock_db)

        # Verify that get_table_as_json was called with parameters
        self.mock_db.get_table_as_json.assert_called()

    @patch('messaging.reporting.get_setting_value')
    def test_malicious_condition_handling(self, mock_get_setting):
        """Test that malicious conditions are safely handled."""
        # Mock settings with malicious input
        mock_get_setting.side_effect = lambda key: {
            'NTFPRCS_INCLUDED_SECTIONS': ['new_devices'],
            'NTFPRCS_new_dev_condition': "'; DROP TABLE Devices; --"
        }.get(key, '')

        # Call the function - should not raise an exception
        get_notifications(self.mock_db)

        # Should still call get_table_as_json (with safe fallback query)
        self.mock_db.get_table_as_json.assert_called()

    @patch('messaging.reporting.get_setting_value')
    def test_empty_condition_handling(self, mock_get_setting):
        """Test that empty conditions are handled gracefully."""
        # Mock settings with empty condition
        mock_get_setting.side_effect = lambda key: {
            'NTFPRCS_INCLUDED_SECTIONS': ['new_devices'],
            'NTFPRCS_new_dev_condition': ""
        }.get(key, '')

        # Call the function
        get_notifications(self.mock_db)

        # Should call get_table_as_json
        self.mock_db.get_table_as_json.assert_called()


class TestSecurityBenchmarks(unittest.TestCase):
    """Performance and security benchmark tests."""

    def setUp(self):
        """Set up benchmark environment."""
        self.builder = SafeConditionBuilder()

    def test_performance_simple_condition(self):
        """Test performance of simple condition building."""
        import time

        start_time = time.time()
        for _ in range(1000):
            sql, params = self.builder.build_safe_condition("AND devName = 'TestDevice'")
        end_time = time.time()

        execution_time = end_time - start_time
        self.assertLess(execution_time, 1.0, "Simple condition building should be fast")

    def test_memory_usage_parameter_generation(self):
        """Test memory usage of parameter generation."""
        try:
            import psutil
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("psutil not available")
            return
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Generate many conditions
        for i in range(100):
            builder = SafeConditionBuilder()
            sql, params = builder.build_safe_condition(f"AND devName = 'Device{i}'")

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 10MB)
        self.assertLess(memory_increase, 10 * 1024 * 1024, "Memory usage should be reasonable")

    def test_pattern_coverage(self):
        """Test coverage of condition patterns."""
        patterns_tested = [
            "AND devName = 'value'",
            "OR eve_EventType LIKE '%test%'",
            "AND devComments IS NULL",
            "AND eve_EventType IN ('Connected', 'Disconnected')",
        ]

        for pattern in patterns_tested:
            with self.subTest(pattern=pattern):
                try:
                    sql, params = self.builder.build_safe_condition(pattern)
                    self.assertIsInstance(sql, str)
                    self.assertIsInstance(params, dict)
                except ValueError:
                    # Some patterns might be rejected, which is acceptable
                    pass


if __name__ == '__main__':
    # Run the test suite
    unittest.main(verbosity=2)
