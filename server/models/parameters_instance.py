"""
Parameters Instance - Handles Parameters table operations for Remember Me tokens and other system parameters.

The Parameters table is used for temporary, ephemeral settings like Remember Me tokens.
Structure:
    parID: TEXT PRIMARY KEY (e.g., "remember_me_token_{uuid}")
    parValue: TEXT (e.g., hashed token value)
"""

import hashlib
import sqlite3
from database import get_temp_db_connection
from logger import mylog


class ParametersInstance:
    """Handler for Parameters table operations."""

    # --- helper methods (DRY pattern from DeviceInstance) ----------------------
    def _fetchall(self, query, params=()):
        """Fetch all rows and return as list of dicts."""
        conn = get_temp_db_connection()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _fetchone(self, query, params=()):
        """Fetch single row and return as dict or None."""
        conn = get_temp_db_connection()
        row = conn.execute(query, params).fetchone()
        conn.close()
        return dict(row) if row else None

    def _execute(self, query, params=()):
        """Execute write query (INSERT/UPDATE/DELETE)."""
        conn = get_temp_db_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        conn.close()

    # --- public API -----------------------------------------------------------

    def get_parameter(self, par_id):
        """
        Retrieve a parameter value by ID.

        Args:
            par_id (str): The parameter ID to retrieve

        Returns:
            str: The parameter value, or None if not found
        """
        try:
            # Try with quoted column names in case they're reserved or have special chars
            row = self._fetchone(
                'SELECT "parValue" FROM "Parameters" WHERE "parID" = ?',
                (par_id,)
            )
            return row['parValue'] if row else None
        except Exception as e:
            mylog("verbose", [f"[ParametersInstance] Error retrieving parameter {par_id}: {e}"])
            return None

    def set_parameter(self, par_id, par_value):
        """
        Store or update a parameter (INSERT OR REPLACE).

        Args:
            par_id (str): The parameter ID
            par_value (str): The parameter value

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Try with quoted column names in case they're reserved or have special chars
            self._execute(
                'INSERT OR REPLACE INTO "Parameters" ("parID", "parValue") VALUES (?, ?)',
                (par_id, par_value)
            )
            mylog("verbose", [f"[ParametersInstance] Parameter {par_id} stored successfully"])
            return True
        except Exception as e:
            mylog("verbose", [f"[ParametersInstance] Error storing parameter {par_id}: {e}"])
            return False

    def delete_parameter(self, par_id):
        """
        Delete a parameter by ID.

        Args:
            par_id (str): The parameter ID to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Try with quoted column names in case they're reserved or have special chars
            self._execute(
                'DELETE FROM "Parameters" WHERE "parID" = ?',
                (par_id,)
            )
            mylog("verbose", [f"[ParametersInstance] Parameter {par_id} deleted successfully"])
            return True
        except Exception as e:
            mylog("verbose", [f"[ParametersInstance] Error deleting parameter {par_id}: {e}"])
            return False

    def delete_parameters_by_prefix(self, prefix):
        """
        Delete all parameters matching a prefix pattern (for cleanup).

        Args:
            prefix (str): The prefix pattern (e.g., "remember_me_token_")

        Returns:
            int: Number of parameters deleted
        """
        try:
            conn = get_temp_db_connection()
            cur = conn.cursor()
            cur.execute('DELETE FROM "Parameters" WHERE "parID" LIKE ?', (f"{prefix}%",))
            deleted_count = cur.rowcount
            conn.commit()
            conn.close()
            mylog("verbose", [f"[ParametersInstance] Deleted {deleted_count} parameters with prefix '{prefix}'"])
            return deleted_count
        except Exception as e:
            mylog("verbose", [f"[ParametersInstance] Error deleting parameters with prefix '{prefix}': {e}"])
            return 0

    def validate_token(self, token):
        """
        Validate a Remember Me token against stored hash.

        Security: Compares hash(token) against stored hashes using hash_equals (timing-safe).

        Args:
            token (str): The unhashed token (from cookie)

        Returns:
            dict: {
                'valid': bool,
                'par_id': str or None  # The matching parameter ID if valid
            }

        Note:
            Returns immediately on first match. Use hash_equals() to prevent timing attacks.
        """
        if not token:
            return {'valid': False, 'par_id': None}

        try:
            # Compute hash of provided token
            computed_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()

            # Retrieve all remember_me tokens from Parameters table
            remember_tokens = self._fetchall(
                'SELECT "parID", "parValue" FROM "Parameters" WHERE "parID" LIKE ?',
                ("remember_me_token_%",)
            )

            # Check each stored token using timing-safe comparison
            for token_record in remember_tokens:
                stored_hash = token_record['parValue']
                stored_id = token_record['parID']

                # Use hash_equals() to prevent timing attacks
                if self._hash_equals(stored_hash, computed_hash):
                    mylog("verbose", [f"[ParametersInstance] Token validation successful for {stored_id}"])
                    return {'valid': True, 'par_id': stored_id}

            mylog("verbose", ["[ParametersInstance] Token validation failed: no matching token found"])
            return {'valid': False, 'par_id': None}

        except Exception as e:
            mylog("verbose", [f"[ParametersInstance] Error validating token: {e}"])
            return {'valid': False, 'par_id': None}

    @staticmethod
    def _hash_equals(known_string, user_string):
        """
        Timing-safe string comparison to prevent timing attacks.

        Args:
            known_string (str): The known value (stored hash)
            user_string (str): The user-supplied value (computed hash)

        Returns:
            bool: True if strings match, False otherwise
        """
        if not isinstance(known_string, str) or not isinstance(user_string, str):
            return False

        if len(known_string) != len(user_string):
            return False

        # Compare all characters regardless of match (timing-safe)
        result = 0
        for x, y in zip(known_string, user_string):
            result |= ord(x) ^ ord(y)

        return result == 0
