"""
AuthManager — selects and dispatches to the correct authentication provider.

Decision logic
--------------
1. If ``LDAP_enabled`` setting is ``True`` → use :class:`LdapProvider`.
2. Otherwise → use :class:`LocalProvider`.

The manager does NOT cache the provider across requests so that toggling
``LDAP_enabled`` at runtime takes effect without a server restart.
"""

from __future__ import annotations

from helper import get_setting_value
from logger import mylog
from auth.base import AuthProvider, AuthResult
from auth.local_provider import LocalProvider
from auth.ldap_provider import LdapProvider, _sanitize_for_log


class AuthManager:
    """Thin dispatcher that picks the active :class:`AuthProvider`."""

    def get_provider(self) -> AuthProvider:
        """Return the :class:`AuthProvider` appropriate for the current config."""
        ldap_enabled = LdapProvider()._read_config().get("enabled", False)
        if ldap_enabled:
            return LdapProvider()
        return LocalProvider()

    def authenticate(self, username: str, password: str) -> AuthResult:
        """Authenticate *username* / *password* with the active provider."""
        ldap_provider = LdapProvider()
        ldap_cfg = ldap_provider._read_config()
        ldap_enabled = ldap_cfg.get("enabled", False)
        
        if ldap_enabled:
            # Check requirements
            setpwd_enabled = get_setting_value("SETPWD_enable_password")
            disable_local = ldap_cfg.get("disable_local_admin", False)
            
            if not setpwd_enabled and not disable_local:
                mylog("warning", ["[auth.manager] LDAP is enabled but SETPWD_enable_password is disabled. Local admin account is still active unless explicitly disabled in LDAP settings (not recommended)."])

            mylog("verbose", ["[auth.manager] Trying LDAP provider"])
            try:
                ldap_result = ldap_provider.authenticate(username, password)
                if ldap_result.success:
                    return ldap_result

                # If the user doesn't exist in LDAP, we can fallback to local auth
                if ldap_result.error == LdapProvider.USER_NOT_FOUND:
                    if not disable_local:
                        # Only the built-in local admin is a recovery account;
                        # all other identities must exist in LDAP.
                        if username != "admin":
                            mylog("verbose", [f"[auth.manager] Local fallback denied for non-admin user '{_sanitize_for_log(username)}'"])
                            return ldap_result
                        mylog("warning", ["[auth.manager] User not found in LDAP, falling back to local provider"])
                        local_result = LocalProvider().authenticate(username, password)
                        if not local_result.success:
                            mylog("verbose", [f"[auth.manager] Authentication failed for user '{_sanitize_for_log(username)}' via both ldap and local"])
                        return local_result
                    else:
                        mylog("verbose", ["[auth.manager] User not found in LDAP, but local fallback is disabled."])
                        return ldap_result

                # LDAP returned failure without exception, which means invalid credentials
                # We should NOT fallback if the LDAP server explicitly rejected them
                if not disable_local:
                    mylog("warning", ["[auth.manager] LDAP explicitly rejected credentials, no fallback to local provider"])
                else:
                    mylog("verbose", [f"[auth.manager] Authentication failed for user '{_sanitize_for_log(username)}' via ldap"])
                return ldap_result
            except Exception as e:
                # Infrastructure error -> fail-closed
                mylog("warning", [f"[auth.manager] LDAP infrastructure error: {e}. Authentication failed securely (fail-closed)."])
                return AuthResult.fail("ldap", "LDAP infrastructure error")

        mylog("verbose", ["[auth.manager] Using local provider"])
        local_result = LocalProvider().authenticate(username, password)
        if not local_result.success:
            mylog("verbose", [f"[auth.manager] Authentication failed for user '{_sanitize_for_log(username)}' via local"])
        return local_result
