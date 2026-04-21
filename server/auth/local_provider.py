"""
Local password authentication provider.

Validates the incoming password by comparing its SHA-256 digest against the
hash stored in the ``SETPWD_password`` setting — the same value that the PHP
login page checks.  This provider is always available as a fallback regardless
of whether LDAP is enabled.

Password handling
-----------------
- The stored value is the hex-encoded SHA-256 digest of the *raw* password.
- Comparison uses :func:`hmac.compare_digest` to prevent timing attacks,
  matching PHP's ``hash_equals`` behaviour.
- No username check is performed for the local provider — any non-empty
  username is accepted (backward-compatible with the single-user model).
"""

from __future__ import annotations

import hashlib
import hmac

from helper import get_setting_value
from logger import mylog
from auth.base import AuthProvider, AuthResult


class LocalProvider(AuthProvider):
    """Authenticate against the SETPWD_password SHA-256 hash."""

    name = "local"

    @classmethod
    def is_fallback_allowed(cls, username: str) -> bool:
        """
        Determine if the given username is allowed to fall back to local authentication
        when an external provider (like LDAP) fails. Currently, only the built-in 
        'admin' account is permitted as a recovery identity.
        """
        return username == "admin"

    def authenticate(self, username: str, password: str) -> AuthResult:
        username = (username or "").strip()
        if not username:
            return AuthResult.fail(self.name, "Username must not be empty")

        if not password:
            return AuthResult.fail(self.name, "Password must not be empty")

        stored_hash: str = get_setting_value("SETPWD_password") or ""

        if not stored_hash:
            mylog("verbose", ["[auth.local] SETPWD_password is not set"])
            return AuthResult.fail(self.name, "Local password not configured")

        # NOTE: SHA-256 is used here purely to *replicate* the legacy PHP hash
        # comparison (``hash('sha256', $password)``).  The hash is computed by
        # the PHP login page and stored in SETPWD_password; this code only
        # verifies it — it does NOT use SHA-256 to *store* a new password.
        # Replacing this with bcrypt/Argon2 would require a coordinated change
        # to the PHP side and is tracked separately.
        incoming_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()  # nosec B324

        if hmac.compare_digest(stored_hash.lower(), incoming_hash.lower()):
            return AuthResult.ok(username, self.name)

        return AuthResult.fail(self.name)
