"""
Unit tests for SafeConditionBuilder compound condition parsing.

Tests the fix for Issue #1210 - compound conditions with multiple AND/OR clauses.
"""

import sys
import pytest
import os
from unittest.mock import MagicMock

# Mock the logger module before importing SafeConditionBuilder
sys.modules['logger'] = MagicMock()

# Add parent directory to path for imports

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.db.sql_safe_builder import SafeConditionBuilder   # noqa: E402 [flake8 lint suppression]


@pytest.fixture
def builder():
    """Create a fresh builder instance for each test."""
    return SafeConditionBuilder()


def test_user_failing_filter_six_and_clauses(builder):
    """Test the exact user-reported failing filter from Issue #1210."""
    condition = (
        "AND devLastIP NOT LIKE '192.168.50.%' "
        "AND devLastIP NOT LIKE '192.168.60.%' "
        "AND devLastIP NOT LIKE '192.168.70.2' "
        "AND devLastIP NOT LIKE '192.168.70.5' "
        "AND devLastIP NOT LIKE '192.168.70.3' "
        "AND devLastIP NOT LIKE '192.168.70.4'"
    )

    sql, params = builder.build_safe_condition(condition)

    # Should successfully parse
    assert sql is not None
    assert params is not None

    # Should have 6 parameters (one per clause)
    assert len(params) == 6

    # Should contain all 6 AND operators
    assert sql.count('AND') == 6

    # Should contain all 6 NOT LIKE operators
    assert sql.count('NOT LIKE') == 6

    # Should have 6 parameter placeholders
    assert sql.count(':param_') == 6

    # Verify all IP patterns are in parameters
    param_values = list(params.values())
    assert '192.168.50.%' in param_values
    assert '192.168.60.%' in param_values
    assert '192.168.70.2' in param_values
    assert '192.168.70.5' in param_values
    assert '192.168.70.3' in param_values
    assert '192.168.70.4' in param_values


def test_multiple_and_clauses_simple(builder):
    """Test multiple AND clauses with simple equality operators."""
    condition = "AND devName = 'Device1' AND devVendor = 'Apple' AND devFavorite = '1'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 3 parameters
    assert len(params) == 3

    # Should have 3 AND operators
    assert sql.count('AND') == 3

    # Verify all values are parameterized
    param_values = list(params.values())
    assert 'Device1' in param_values
    assert 'Apple' in param_values
    assert '1' in param_values


def test_multiple_or_clauses(builder):
    """Test multiple OR clauses."""
    condition = "OR devName = 'Device1' OR devName = 'Device2' OR devName = 'Device3'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 3 parameters
    assert len(params) == 3

    # Should have 3 OR operators
    assert sql.count('OR') == 3

    # Verify all device names are parameterized
    param_values = list(params.values())
    assert 'Device1' in param_values
    assert 'Device2' in param_values
    assert 'Device3' in param_values


def test_mixed_and_or_clauses(builder):
    """Test mixed AND/OR logical operators."""
    condition = "AND devName = 'Device1' OR devName = 'Device2' AND devFavorite = '1'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 3 parameters
    assert len(params) == 3

    # Should preserve the logical operator order
    assert 'AND' in sql
    assert 'OR' in sql

    # Verify all values are parameterized
    param_values = list(params.values())
    assert 'Device1' in param_values
    assert 'Device2' in param_values
    assert '1' in param_values


def test_single_condition_backward_compatibility(builder):
    """Test that single conditions still work (backward compatibility)."""
    condition = "AND devName = 'TestDevice'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 1 parameter
    assert len(params) == 1

    # Should match expected format
    assert 'AND devName = :param_' in sql

    # Parameter should contain the value
    assert 'TestDevice' in params.values()


def test_single_condition_like_operator(builder):
    """Test single LIKE condition for backward compatibility."""
    condition = "AND devComments LIKE '%important%'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 1 parameter
    assert len(params) == 1

    # Should contain LIKE operator
    assert 'LIKE' in sql

    # Parameter should contain the pattern
    assert '%important%' in params.values()


def test_compound_with_like_patterns(builder):
    """Test compound conditions with LIKE patterns."""
    condition = "AND devLastIP LIKE '192.168.%' AND devVendor LIKE '%Apple%'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 2 parameters
    assert len(params) == 2

    # Should have 2 LIKE operators
    assert sql.count('LIKE') == 2

    # Verify patterns are parameterized
    param_values = list(params.values())
    assert '192.168.%' in param_values
    assert '%Apple%' in param_values


def test_compound_with_inequality_operators(builder):
    """Test compound conditions with various inequality operators."""
    condition = "AND eveDateTime > '2024-01-01' AND eveDateTime < '2024-12-31'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 2 parameters
    assert len(params) == 2

    # Should have both operators
    assert '>' in sql
    assert '<' in sql

    # Verify dates are parameterized
    param_values = list(params.values())
    assert '2024-01-01' in param_values
    assert '2024-12-31' in param_values


def test_empty_condition(builder):
    """Test empty condition string."""
    condition = ""

    sql, params = builder.build_safe_condition(condition)

    # Should return empty results
    assert sql == ""
    assert params == {}


def test_whitespace_only_condition(builder):
    """Test condition with only whitespace."""
    condition = "   \t\n  "

    sql, params = builder.build_safe_condition(condition)

    # Should return empty results
    assert sql == ""
    assert params == {}


def test_invalid_column_name_rejected(builder):
    """Test that invalid column names are rejected."""
    condition = "AND malicious_column = 'value'"

    with pytest.raises(ValueError):
        builder.build_safe_condition(condition)


def test_invalid_operator_rejected(builder):
    """Test that invalid operators are rejected."""
    condition = "AND devName EXECUTE 'DROP TABLE'"

    with pytest.raises(ValueError):
        builder.build_safe_condition(condition)


def test_sql_injection_attempt_blocked(builder):
    """Test that SQL injection attempts are blocked."""
    condition = "AND devName = 'value'; DROP TABLE devices; --"

    # Should either reject or sanitize the dangerous input
    # The semicolon and comment should not appear in the final SQL
    try:
        sql, params = builder.build_safe_condition(condition)
        # If it doesn't raise an error, it should sanitize the input
        assert 'DROP' not in sql.upper()
        assert ';' not in sql
    except ValueError:
        # Rejection is also acceptable
        pass


def test_quoted_string_with_spaces(builder):
    """Test that quoted strings with spaces are handled correctly."""
    condition = "AND devName = 'My Device Name' AND devComments = 'Has spaces here'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 2 parameters
    assert len(params) == 2

    # Verify values with spaces are preserved
    param_values = list(params.values())
    assert 'My Device Name' in param_values
    assert 'Has spaces here' in param_values


def test_compound_condition_with_not_equal(builder):
    """Test compound conditions with != operator."""
    condition = "AND devName != 'Device1' AND devVendor != 'Unknown'"

    sql, params = builder.build_safe_condition(condition)

    # Should have 2 parameters
    assert len(params) == 2

    # Should have != operators (or converted to <>)
    assert '!=' in sql or '<>' in sql

    # Verify values are parameterized
    param_values = list(params.values())
    assert 'Device1' in param_values
    assert 'Unknown' in param_values


def test_very_long_compound_condition(builder):
    """Test handling of very long compound conditions (10+ clauses)."""
    clauses = []
    for i in range(10):
        clauses.append(f"AND devName != 'Device{i}'")

    condition = " ".join(clauses)
    sql, params = builder.build_safe_condition(condition)

    # Should have 10 parameters
    assert len(params) == 10

    # Should have 10 AND operators
    assert sql.count('AND') == 10

    # Verify all device names are parameterized
    param_values = list(params.values())
    for i in range(10):
        assert f'Device{i}' in param_values


def test_parameters_have_unique_names(builder):
    """Test that all parameters get unique names."""
    condition = "AND devName = 'A' AND devName = 'B' AND devName = 'C'"

    sql, params = builder.build_safe_condition(condition)

    # All parameter names should be unique
    param_names = list(params.keys())
    assert len(param_names) == len(set(param_names))


def test_parameter_values_match_condition(builder):
    """Test that parameter values correctly match the condition values."""
    condition = "AND devLastIP NOT LIKE '192.168.1.%' AND devLastIP NOT LIKE '10.0.0.%'"

    sql, params = builder.build_safe_condition(condition)

    # Should have exactly the values from the condition
    param_values = sorted(params.values())
    expected_values = sorted(['192.168.1.%', '10.0.0.%'])
    assert param_values == expected_values


def test_parameters_referenced_in_sql(builder):
    """Test that all parameters are actually referenced in the SQL."""
    condition = "AND devName = 'Device1' AND devVendor = 'Apple'"

    sql, params = builder.build_safe_condition(condition)

    # Every parameter should appear in the SQL
    for param_name in params.keys():
        assert f':{param_name}' in sql
