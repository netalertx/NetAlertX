"""
NetAlertX SQL Safe Builder Module

This module provides safe SQL condition building functionality to prevent
SQL injection vulnerabilities. It validates inputs against whitelists,
sanitizes data, and returns parameterized queries.

Author: Security Enhancement for NetAlertX
License: GNU GPLv3
"""

import re
import sys
import os
from typing import Dict, List, Tuple, Any, Optional

# Register NetAlertX directories
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/server"])

from logger import mylog  # noqa: E402 [flake8 lint suppression]


class SafeConditionBuilder:
    """
    A secure SQL condition builder that validates inputs against whitelists
    and generates parameterized SQL snippets to prevent SQL injection.
    """

    # Whitelist of allowed column names for filtering
    ALLOWED_COLUMNS = {
        "eveMac",
        "eveDateTime",
        "eveIp",
        "eveEventType",
        "devName",
        "devComments",
        "devLastIP",
        "devVendor",
        "devAlertEvents",
        "devAlertDown",
        "devIsArchived",
        "devPresentLastScan",
        "devFavorite",
        "devIsNew",
        "plugin",
        "objectPrimaryId",
        "objectSecondaryId",
        "dateTimeChanged",
        "watchedValue1",
        "watchedValue2",
        "watchedValue3",
        "watchedValue4",
        "status",
    }

    # Whitelist of allowed comparison operators
    ALLOWED_OPERATORS = {
        "=",
        "!=",
        "<>",
        "<",
        ">",
        "<=",
        ">=",
        "LIKE",
        "NOT LIKE",
        "IN",
        "NOT IN",
        "IS NULL",
        "IS NOT NULL",
    }

    # Whitelist of allowed logical operators
    ALLOWED_LOGICAL_OPERATORS = {"AND", "OR"}

    # Whitelist of allowed event types
    ALLOWED_EVENT_TYPES = {
        "New Device",
        "Connected",
        "Disconnected",
        "Device Down",
        "Down Reconnected",
        "IP Changed",
    }

    def __init__(self):
        """Initialize the SafeConditionBuilder."""
        self.parameters = {}
        self.param_counter = 0

    def _generate_param_name(self, prefix: str = "param") -> str:
        """Generate a unique parameter name for SQL binding."""
        self.param_counter += 1
        return f"{prefix}_{self.param_counter}"

    def _sanitize_string(self, value: str) -> str:
        """
        Sanitize string input by removing potentially dangerous characters.

        Args:
            value: String to sanitize

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value)

        # Replace {s-quote} placeholder with single quote (maintaining compatibility)
        value = value.replace("{s-quote}", "'")

        # Remove any null bytes, control characters, and excessive whitespace
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]", "", value)
        value = re.sub(r"\s+", " ", value.strip())

        return value

    def _validate_column_name(self, column: str) -> bool:
        """
        Validate that a column name is in the whitelist.

        Args:
            column: Column name to validate

        Returns:
            True if valid, False otherwise
        """
        return column in self.ALLOWED_COLUMNS

    def _validate_operator(self, operator: str) -> bool:
        """
        Validate that an operator is in the whitelist.

        Args:
            operator: Operator to validate

        Returns:
            True if valid, False otherwise
        """
        return operator.upper() in self.ALLOWED_OPERATORS

    def _validate_logical_operator(self, logical_op: str) -> bool:
        """
        Validate that a logical operator is in the whitelist.

        Args:
            logical_op: Logical operator to validate

        Returns:
            True if valid, False otherwise
        """
        return logical_op.upper() in self.ALLOWED_LOGICAL_OPERATORS

    def build_safe_condition(self, condition_string: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse and build a safe SQL condition from a user-provided string.
        This method attempts to parse common condition patterns and convert
        them to parameterized queries.

        Args:
            condition_string: User-provided condition string

        Returns:
            Tuple of (safe_sql_snippet, parameters_dict)

        Raises:
            ValueError: If the condition contains invalid or unsafe elements
        """
        if not condition_string or not condition_string.strip():
            return "", {}

        # Sanitize the input
        condition_string = self._sanitize_string(condition_string)

        # Reset parameters for this condition
        self.parameters = {}
        self.param_counter = 0

        try:
            return self._parse_condition(condition_string)
        except Exception as e:
            mylog("verbose", f"[SafeConditionBuilder] Error parsing condition: {e}")
            raise ValueError(f"Invalid condition format: {condition_string}")

    def _parse_condition(self, condition: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse a condition string into safe SQL with parameters.

        This method handles both single and compound conditions:
        - Single: AND devName = 'value'
        - Compound: AND devName = 'value' AND devVendor = 'Apple'
        - Multiple clauses with AND/OR operators

        Args:
            condition: Condition string to parse

        Returns:
            Tuple of (safe_sql_snippet, parameters_dict)
        """
        condition = condition.strip()

        # Handle empty conditions
        if not condition:
            return "", {}

        # Check if this is a compound condition (multiple clauses)
        if self._is_compound_condition(condition):
            return self._parse_compound_condition(condition)

        # Single condition: extract leading logical operator if present
        logical_op = None
        clause_text = condition

        # Check for leading AND
        if condition.upper().startswith("AND ") or condition.upper().startswith(
            "AND\t"
        ):
            logical_op = "AND"
            clause_text = condition[3:].strip()
        # Check for leading OR
        elif condition.upper().startswith("OR ") or condition.upper().startswith(
            "OR\t"
        ):
            logical_op = "OR"
            clause_text = condition[2:].strip()

        # Parse the single condition
        return self._parse_single_condition(clause_text, logical_op)

    def _is_compound_condition(self, condition: str) -> bool:
        """
        Determine if a condition contains multiple clauses (compound condition).

        A compound condition has multiple logical operators (AND/OR) connecting
        separate comparison clauses.

        Args:
            condition: Condition string to check

        Returns:
            True if compound (multiple clauses), False if single clause
        """
        # Track if we're inside quotes to avoid counting operators in quoted strings
        in_quotes = False
        logical_op_count = 0
        i = 0

        while i < len(condition):
            char = condition[i]

            # Toggle quote state
            if char == "'":
                in_quotes = not in_quotes
                i += 1
                continue

            # Only count logical operators outside of quotes
            if not in_quotes:
                # Look for AND or OR as whole words
                remaining = condition[i:].upper()

                # Check for AND (must be word boundary)
                if remaining.startswith("AND ") or remaining.startswith("AND\t"):
                    logical_op_count += 1
                    i += 3
                    continue

                # Check for OR (must be word boundary)
                if remaining.startswith("OR ") or remaining.startswith("OR\t"):
                    logical_op_count += 1
                    i += 2
                    continue

            i += 1

        # A compound condition has more than one logical operator
        # (first AND/OR starts the condition, subsequent ones connect clauses)
        return logical_op_count > 1

    def _parse_compound_condition(self, condition: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse a compound condition with multiple clauses.

        Splits the condition into individual clauses, parses each one,
        and reconstructs the full condition with all parameters.

        Args:
            condition: Compound condition string

        Returns:
            Tuple of (safe_sql_snippet, parameters_dict)
        """
        # Split the condition into individual clauses while preserving logical operators
        clauses = self._split_by_logical_operators(condition)

        # Parse each clause individually
        parsed_parts = []
        all_params = {}

        for clause_text, logical_op in clauses:
            # Parse this single clause
            sql_part, params = self._parse_single_condition(clause_text, logical_op)

            if sql_part:
                parsed_parts.append(sql_part)
                all_params.update(params)

        if not parsed_parts:
            raise ValueError("No valid clauses found in compound condition")

        # Join all parsed parts
        final_sql = " ".join(parsed_parts)

        return final_sql, all_params

    def _split_by_logical_operators(
        self, condition: str
    ) -> List[Tuple[str, Optional[str]]]:
        """
        Split a compound condition into individual clauses.

        Returns a list of tuples: (clause_text, logical_operator)
        The logical operator is the AND/OR that precedes the clause.

        Args:
            condition: Compound condition string

        Returns:
            List of (clause_text, logical_op) tuples
        """
        clauses = []
        current_clause = []
        current_logical_op = None
        in_quotes = False
        i = 0

        while i < len(condition):
            char = condition[i]

            # Toggle quote state
            if char == "'":
                in_quotes = not in_quotes
                current_clause.append(char)
                i += 1
                continue

            # Only look for logical operators outside of quotes
            if not in_quotes:
                remaining = condition[i:].upper()

                # Check if we're at a word boundary (start of string or after whitespace)
                at_word_boundary = i == 0 or condition[i - 1] in " \t"

                # Check for AND (must be at word boundary)
                if at_word_boundary and (
                    remaining.startswith("AND ") or remaining.startswith("AND\t")
                ):
                    # Save current clause if we have one
                    if current_clause:
                        clause_text = "".join(current_clause).strip()
                        if clause_text:
                            clauses.append((clause_text, current_logical_op))
                        current_clause = []

                    # Set the logical operator for the next clause
                    current_logical_op = "AND"
                    i += 3  # Skip 'AND'

                    # Skip whitespace after AND
                    while i < len(condition) and condition[i] in " \t":
                        i += 1
                    continue

                # Check for OR (must be at word boundary)
                if at_word_boundary and (
                    remaining.startswith("OR ") or remaining.startswith("OR\t")
                ):
                    # Save current clause if we have one
                    if current_clause:
                        clause_text = "".join(current_clause).strip()
                        if clause_text:
                            clauses.append((clause_text, current_logical_op))
                        current_clause = []

                    # Set the logical operator for the next clause
                    current_logical_op = "OR"
                    i += 2  # Skip 'OR'

                    # Skip whitespace after OR
                    while i < len(condition) and condition[i] in " \t":
                        i += 1
                    continue

            # Add character to current clause
            current_clause.append(char)
            i += 1

        # Don't forget the last clause
        if current_clause:
            clause_text = "".join(current_clause).strip()
            if clause_text:
                clauses.append((clause_text, current_logical_op))

        return clauses

    def _parse_single_condition(
        self, condition: str, logical_op: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Parse a single condition clause into safe SQL with parameters.

        This method handles basic patterns like:
        - devName = 'value' (with optional AND/OR prefix)
        - devComments LIKE '%value%'
        - eveEventType IN ('type1', 'type2')

        Args:
            condition: Single condition string to parse
            logical_op: Optional logical operator (AND/OR) to prepend

        Returns:
            Tuple of (safe_sql_snippet, parameters_dict)
        """
        condition = condition.strip()

        # Handle empty conditions
        if not condition:
            return "", {}

        # Simple pattern matching for common conditions
        # Pattern 1: [AND/OR] column operator value (supporting Unicode in quoted strings)
        pattern1 = r"^\s*(\w+)\s+(=|!=|<>|<|>|<=|>=|LIKE|NOT\s+LIKE)\s+\'([^\']*)\'\s*$"
        match1 = re.match(pattern1, condition, re.IGNORECASE | re.UNICODE)

        if match1:
            column, operator, value = match1.groups()
            return self._build_simple_condition(logical_op, column, operator, value)

        # Pattern 2: [AND/OR] column IN ('val1', 'val2', ...)
        pattern2 = r"^\s*(\w+)\s+(IN|NOT\s+IN)\s+\(([^)]+)\)\s*$"
        match2 = re.match(pattern2, condition, re.IGNORECASE)

        if match2:
            column, operator, values_str = match2.groups()
            return self._build_in_condition(logical_op, column, operator, values_str)

        # Pattern 3: [AND/OR] column IS NULL/IS NOT NULL
        pattern3 = r"^\s*(\w+)\s+(IS\s+NULL|IS\s+NOT\s+NULL)\s*$"
        match3 = re.match(pattern3, condition, re.IGNORECASE)

        if match3:
            column, operator = match3.groups()
            return self._build_null_condition(logical_op, column, operator)

        # If no patterns match, reject the condition for security
        raise ValueError(f"Unsupported condition pattern: {condition}")

    def _build_simple_condition(
        self, logical_op: Optional[str], column: str, operator: str, value: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Build a simple condition with parameter binding."""
        # Validate components
        if not self._validate_column_name(column):
            raise ValueError(f"Invalid column name: {column}")

        if not self._validate_operator(operator):
            raise ValueError(f"Invalid operator: {operator}")

        if logical_op and not self._validate_logical_operator(logical_op):
            raise ValueError(f"Invalid logical operator: {logical_op}")

        # Generate parameter name and store value
        param_name = self._generate_param_name()
        self.parameters[param_name] = value

        # Build the SQL snippet
        sql_parts = []
        if logical_op:
            sql_parts.append(logical_op.upper())

        sql_parts.extend([column, operator.upper(), f":{param_name}"])

        return " ".join(sql_parts), self.parameters

    def _build_in_condition(
        self, logical_op: Optional[str], column: str, operator: str, values_str: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Build an IN condition with parameter binding."""
        # Validate components
        if not self._validate_column_name(column):
            raise ValueError(f"Invalid column name: {column}")

        if logical_op and not self._validate_logical_operator(logical_op):
            raise ValueError(f"Invalid logical operator: {logical_op}")

        # Simple regex to extract quoted values
        value_pattern = r"'([^']*)'"
        matches = re.findall(value_pattern, values_str)

        if not matches:
            raise ValueError("No valid values found in IN clause")

        # Generate parameters for each value
        param_names = []
        for value in matches:
            param_name = self._generate_param_name()
            self.parameters[param_name] = value
            param_names.append(f":{param_name}")

        # Build the SQL snippet
        sql_parts = []
        if logical_op:
            sql_parts.append(logical_op.upper())

        sql_parts.extend([column, operator.upper(), f"({', '.join(param_names)})"])

        return " ".join(sql_parts), self.parameters

    def _build_null_condition(
        self, logical_op: Optional[str], column: str, operator: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Build a NULL check condition."""
        # Validate components
        if not self._validate_column_name(column):
            raise ValueError(f"Invalid column name: {column}")

        if logical_op and not self._validate_logical_operator(logical_op):
            raise ValueError(f"Invalid logical operator: {logical_op}")

        # Build the SQL snippet (no parameters needed for NULL checks)
        sql_parts = []
        if logical_op:
            sql_parts.append(logical_op.upper())

        sql_parts.extend([column, operator.upper()])

        return " ".join(sql_parts), {}

    def build_device_name_filter(self, device_name: str) -> Tuple[str, Dict[str, Any]]:
        """
        Build a safe device name filter condition.

        Args:
            device_name: Device name to filter for

        Returns:
            Tuple of (safe_sql_snippet, parameters_dict)
        """
        if not device_name:
            return "", {}

        device_name = self._sanitize_string(device_name)
        param_name = self._generate_param_name("device_name")
        self.parameters[param_name] = device_name

        return f"AND devName = :{param_name}", self.parameters

    def build_condition(
        self, conditions: List[Dict[str, str]], logical_operator: str = "AND"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a safe SQL condition from a list of condition dictionaries.

        Args:
            conditions: List of condition dicts with 'column', 'operator', 'value' keys
            logical_operator: Logical operator to join conditions (AND/OR)

        Returns:
            Tuple of (safe_sql_snippet, parameters_dict)
        """
        if not conditions:
            return "", {}

        if not self._validate_logical_operator(logical_operator):
            return "", {}

        condition_parts = []
        all_params = {}

        for condition_dict in conditions:
            try:
                column = condition_dict.get("column", "")
                operator = condition_dict.get("operator", "")
                value = condition_dict.get("value", "")

                # Validate each component
                if not self._validate_column_name(column):
                    mylog("verbose", [f"[SafeConditionBuilder] Invalid column: {column}"])
                    return "", {}

                if not self._validate_operator(operator):
                    mylog("verbose", [f"[SafeConditionBuilder] Invalid operator: {operator}"])
                    return "", {}

                # Create parameter binding
                param_name = self._generate_param_name()
                all_params[param_name] = self._sanitize_string(str(value))

                # Build condition part
                condition_part = f"{column} {operator} :{param_name}"
                condition_parts.append(condition_part)

            except Exception as e:
                mylog("verbose", [f"[SafeConditionBuilder] Error processing condition: {e}"],)
                return "", {}

        if not condition_parts:
            return "", {}

        # Join all parts with the logical operator
        final_condition = f" {logical_operator} ".join(condition_parts)
        self.parameters.update(all_params)

        return final_condition, self.parameters

    def build_event_type_filter(
        self, event_types: List[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a safe event type filter condition.

        Args:
            event_types: List of event types to filter for

        Returns:
            Tuple of (safe_sql_snippet, parameters_dict)
        """
        if not event_types:
            return "", {}

        # Validate event types against whitelist
        valid_types = []
        for event_type in event_types:
            event_type = self._sanitize_string(event_type)
            if event_type in self.ALLOWED_EVENT_TYPES:
                valid_types.append(event_type)
            else:
                mylog("verbose", f"[SafeConditionBuilder] Invalid event type filtered out: {event_type}",)

        if not valid_types:
            return "", {}

        # Generate parameters for each valid event type
        param_names = []
        for event_type in valid_types:
            param_name = self._generate_param_name("event_type")
            self.parameters[param_name] = event_type
            param_names.append(f":{param_name}")

        sql_snippet = f"AND eveEventType IN ({', '.join(param_names)})"
        return sql_snippet, self.parameters

    def get_safe_condition_legacy(
        self, condition_setting: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Convert legacy condition settings to safe parameterized queries.
        This method provides backward compatibility for existing condition formats.

        Args:
            condition_setting: The condition string from settings

        Returns:
            Tuple of (safe_sql_snippet, parameters_dict)
        """
        if not condition_setting or not condition_setting.strip():
            return "", {}

        try:
            return self.build_safe_condition(condition_setting)
        except ValueError as e:
            # Log the error and return empty condition for safety
            mylog("verbose", f"[SafeConditionBuilder] Unsafe condition rejected: {condition_setting}, Error: {e}",)
            return "", {}


def create_safe_condition_builder() -> SafeConditionBuilder:
    """
    Factory function to create a new SafeConditionBuilder instance.

    Returns:
        New SafeConditionBuilder instance
    """
    return SafeConditionBuilder()
