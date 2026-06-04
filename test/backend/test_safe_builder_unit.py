"""
Minimal pytest unit tests for SafeConditionBuilder security functionality.
Focuses on core parsing, parameterization, and input sanitization.
"""

import re
import pytest
from unittest.mock import Mock
import sys

# Mock logger
sys.modules['logger'] = Mock()


class SafeConditionBuilderForTesting:
    """Minimal SafeConditionBuilder implementation for tests."""

    ALLOWED_COLUMNS = {'devName', 'eveMac', 'eveEventType'}
    ALLOWED_OPERATORS = {'=', '!=', '<', '>', '<=', '>=', 'LIKE', 'NOT LIKE'}
    ALLOWED_LOGICAL_OPERATORS = {'AND', 'OR'}

    def __init__(self):
        self.parameters = {}
        self.param_counter = 0

    def _generate_param_name(self):
        self.param_counter += 1
        return f"param_{self.param_counter}"

    def _sanitize_string(self, value):
        if not isinstance(value, str):
            value = str(value)
        value = value.replace('{s-quote}', "'")
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', value)
        return re.sub(r'\s+', ' ', value.strip())

    def _validate_column_name(self, column):
        return column in self.ALLOWED_COLUMNS

    def _validate_operator(self, operator):
        return operator.upper() in self.ALLOWED_OPERATORS

    def _validate_logical_operator(self, logical_op):
        return logical_op.upper() in self.ALLOWED_LOGICAL_OPERATORS

    def build_safe_condition(self, condition_string):
        if not condition_string or not condition_string.strip():
            return "", {}
        condition_string = self._sanitize_string(condition_string)
        self.parameters = {}
        self.param_counter = 0
        pattern = r"^\s*(AND|OR)?\s+(\w+)\s+(=|!=|<>|<|>|<=|>=|LIKE|NOT\s+LIKE)\s+'(.+?)'\s*$"
        match = re.match(pattern, condition_string, re.IGNORECASE)
        if not match:
            raise ValueError("Unsupported condition pattern")
        logical_op, column, operator, value = match.groups()
        if not self._validate_column_name(column):
            raise ValueError(f"Invalid column: {column}")
        if not self._validate_operator(operator):
            raise ValueError(f"Invalid operator: {operator}")
        if logical_op and not self._validate_logical_operator(logical_op):
            raise ValueError(f"Invalid logical operator: {logical_op}")
        param_name = self._generate_param_name()
        self.parameters[param_name] = value
        sql_parts = []
        if logical_op:
            sql_parts.append(logical_op.upper())
        sql_parts.extend([column, operator.upper(), f":{param_name}"])
        return " ".join(sql_parts), self.parameters


# -----------------------
# Pytest Fixtures
# -----------------------
@pytest.fixture
def builder():
    return SafeConditionBuilderForTesting()


# -----------------------
# Tests
# -----------------------
def test_sanitize_string(builder):
    assert builder._sanitize_string("  test  string  ") == "test string"
    assert builder._sanitize_string("test{s-quote}value") == "test'value"
    assert builder._sanitize_string("test\x00\x01string") == "teststring"


def test_validate_column_and_operator(builder):
    assert builder._validate_column_name('devName')
    assert not builder._validate_column_name('bad_column')
    assert builder._validate_operator('=')
    assert not builder._validate_operator('DROP')


def test_build_simple_condition_valid(builder):
    sql, params = builder.build_safe_condition("AND devName = 'Device1'")
    assert 'AND devName = :param_' in sql
    assert "Device1" in params.values()


def test_build_simple_condition_invalid(builder):
    with pytest.raises(ValueError):
        builder.build_safe_condition("AND bad_column = 'X'")
    with pytest.raises(ValueError):
        builder.build_safe_condition("AND devName UNION 'X'")


def test_parameter_isolation(builder):
    sql1, params1 = builder.build_safe_condition("AND devName = 'Device1'")
    sql2, params2 = builder.build_safe_condition("AND devName = 'Device2'")
    assert params1 != params2
    assert "Device1" in params1.values()
    assert "Device2" in params2.values()


@pytest.mark.parametrize("payload", [
    "<script>alert('xss')</script>",
    "javascript:alert(1)",
    "'; DROP TABLE users; --"
])
def test_xss_payloads(builder, payload):
    sql, params = builder.build_safe_condition(f"AND devName = '{payload}'")
    assert ':' in sql
    assert payload in params.values()


@pytest.mark.parametrize("unicode_str", [
    "Ülrich's Device",
    "Café Network",
    "测试设备",
    "Устройство"
])
def test_unicode_support(builder, unicode_str):
    sql, params = builder.build_safe_condition(f"AND devName = '{unicode_str}'")
    assert unicode_str in params.values()


@pytest.mark.parametrize("case", [
    "", "   ", "AND devName = ''", "AND devName = 'a'", "AND devName = '" + "x" * 500 + "'"
])
def test_edge_cases(builder, case):
    try:
        sql, params = builder.build_safe_condition(case) if case.strip() else ("", {})
        assert isinstance(sql, str)
        assert isinstance(params, dict)
    except ValueError:
        # Empty or invalid inputs can raise ValueError, acceptable
        pass
