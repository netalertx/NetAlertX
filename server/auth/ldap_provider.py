"""
LDAP authentication provider for NetAlertX.

Uses the *search-then-bind* pattern which is compatible with both OpenLDAP and
Microsoft Active Directory:

1. Connect to the LDAP server (optionally over TLS/StartTLS).
2. Bind with a read-only service account (``LDAP_bind_dn`` / ``LDAP_bind_password``).
3. Search for the user entry whose ``LDAP_user_filter`` matches *username*.
4. Re-bind as that user with the supplied *password*.
5. A successful re-bind means the credentials are valid.

Configuration settings (via NetAlertX plugin ``auth_ldap``)
-------------------------------------------------------------
- ``LDAP_server``              – hostname or IP of the LDAP/AD server
- ``LDAP_port``                – default 389 (636 for LDAPS)
- ``LDAP_use_ssl``             – True → LDAPS (port 636), False → plain / StartTLS
- ``LDAP_use_start_tls``       – True → issue StartTLS on a plain-text connection
- ``LDAP_bind_dn``             – service-account DN for the initial search bind
- ``LDAP_bind_password``       – service-account password
- ``LDAP_base_dn``             – base DN for the user search
- ``LDAP_user_filter``         – search filter template; ``{username}`` is replaced at
                                 runtime.  Examples:
                                 OpenLDAP : ``(uid={username})``
                                 Active Directory: ``(sAMAccountName={username})``
- ``LDAP_username_attribute``  – attribute that holds the login name (default ``uid``)
"""

from __future__ import annotations

import re
import ssl
from typing import Optional

from helper import get_setting_value
from logger import mylog
from auth.base import AuthProvider, AuthResult


def _sanitize_for_log(value: str) -> str:
    """Strip control characters from a string before logging."""
    return value.encode("unicode_escape").decode("ascii") if value else ""


# ---------------------------------------------------------------------------
# LDAP filter escaping (RFC 4515)
# ---------------------------------------------------------------------------

_LDAP_ESCAPE_RE = re.compile(r'[\\*()\x00/]')
_LDAP_ESCAPE_MAP = {
    '\\': r'\5c',
    '*':  r'\2a',
    '(':  r'\28',
    ')':  r'\29',
    '\x00': r'\00',
    '/':  r'\2f',
}


def _escape_ldap_filter(value: str) -> str:
    """Escape special characters in an LDAP filter value (RFC 4515 §4)."""
    return _LDAP_ESCAPE_RE.sub(lambda m: _LDAP_ESCAPE_MAP[m.group(0)], value)


# ---------------------------------------------------------------------------
# DN value escaping (RFC 4514)
# ---------------------------------------------------------------------------

_DN_ESCAPE_RE = re.compile(r'[,+\"\\<>;#=]')


def _escape_dn_value(value: str) -> str:
    """Escape special characters in an LDAP DN attribute value (RFC 4514 Section 2.4)."""
    escaped = _DN_ESCAPE_RE.sub(lambda m: '\\' + m.group(0), value)
    if escaped.startswith(' '):
        escaped = '\\ ' + escaped[1:]
    if escaped.endswith(' ') and not escaped.endswith('\\ '):
        escaped = escaped[:-1] + '\\ '
    if escaped.startswith('#'):
        escaped = '\\#' + escaped[1:]
    return escaped


class LdapProvider(AuthProvider):
    """Authenticate against an LDAP / Active Directory server."""

    name = "ldap"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> AuthResult:
        if not username or not password:
            return AuthResult.fail(self.name, "Username and password are required")

        try:
            import ldap3  # noqa: PLC0415 (deferred to avoid hard dep at import time)
        except ImportError:
            mylog("none", ["[auth.ldap] ldap3 package is not installed"])
            return AuthResult.fail(self.name, "LDAP library not available")

        cfg = self._read_config()
        if not cfg.get("server"):
            return AuthResult.fail(self.name, "LDAP server not configured")

        if not cfg["use_ssl"] and not cfg["use_start_tls"]:
            mylog("warning", ["[auth.ldap] WARNING: Neither LDAPS nor StartTLS is enabled. "
                               "Credentials will be sent in cleartext."])

        tls_obj = None
        if cfg["use_ssl"] or cfg["use_start_tls"]:
            validate = ssl.CERT_REQUIRED if cfg["tls_verify_cert"] else ssl.CERT_NONE
            ca_certs_file = cfg["ca_cert_path"] if cfg["ca_cert_path"] else None
            tls_obj = ldap3.Tls(validate=validate, ca_certs_file=ca_certs_file)

        server_obj = ldap3.Server(
            cfg["server"],
            port=cfg["port"],
            use_ssl=cfg["use_ssl"],
            tls=tls_obj,
            connect_timeout=cfg["timeout"],
            get_info=ldap3.NONE,
        )

        try:
            if cfg.get("direct_bind_format"):
                safe_username = _escape_dn_value(username)
                user_dn = cfg["direct_bind_format"].replace("{username}", safe_username)
            else:
                user_dn = self._resolve_user_dn(ldap3, server_obj, cfg, username)

            if user_dn is None:
                return AuthResult.fail(self.name, "User not found")

            return self._bind_as_user(ldap3, server_obj, cfg, user_dn, username, password)

        except Exception as exc:
            mylog("none", [f"[auth.ldap] Unexpected error for user '{_sanitize_for_log(username)}': {exc}"])
            raise exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_server_obj(self, ldap3, cfg: dict):
        import ssl
        tls_obj = None
        if cfg["use_ssl"] or cfg["use_start_tls"]:
            validate = ssl.CERT_REQUIRED if cfg.get("tls_verify_cert", True) else ssl.CERT_NONE
            ca_certs_file = cfg.get("ca_cert_path") if cfg.get("ca_cert_path") else None
            tls_obj = ldap3.Tls(validate=validate, ca_certs_file=ca_certs_file)

        return ldap3.Server(
            cfg["server"],
            port=cfg["port"],
            use_ssl=cfg["use_ssl"],
            tls=tls_obj,
            connect_timeout=cfg["timeout"],
            get_info=ldap3.NONE,
        )

    def _read_config(self) -> dict:
        import os
        
        def get_env_or_setting(key_name: str, default_value, type_cast):
            env_val = os.environ.get(key_name.upper())
            if env_val is not None and env_val != "":
                if type_cast is bool:
                    return str(env_val).lower() in ("true", "1", "yes")
                try:
                    return type_cast(env_val)
                except ValueError:
                    mylog("warning", [f"[auth.ldap] Invalid {type_cast.__name__} in environment variable {key_name.upper()}: {env_val}"])
                    return default_value
            
            db_val = get_setting_value(key_name)
            if db_val is not None and db_val != "":
                if type_cast is bool:
                    return str(db_val).lower() in ("true", "1", "yes") if isinstance(db_val, str) else bool(db_val)
                try:
                    return type_cast(db_val)
                except ValueError:
                    mylog("warning", [f"[auth.ldap] Invalid {type_cast.__name__} in database setting {key_name}: {db_val}"])
                    return default_value
                    
            return default_value

        def get_secret(key_name: str) -> str:
            env_val = os.environ.get(key_name.upper())
            if env_val:
                return env_val
            secret_path = f"/run/secrets/{key_name.lower()}"
            if os.path.isfile(secret_path):
                with open(secret_path, "r") as f:
                    return f.read().strip()
            value = str(get_setting_value(key_name) or "").strip()
            if value:
                mylog("warning", [f"[auth.ldap] {key_name} is stored in app.conf (plaintext). "
                                  "Consider using the environment variable or Docker secrets instead."])
            return value

        # IMPORTANT: never pass the returned dict to a log function — it contains bind_password.
        cfg = {
            "enabled":      get_env_or_setting("LDAP_enabled", False, bool),
            "server":       get_env_or_setting("LDAP_server", "", str).strip(),
            "port":         get_env_or_setting("LDAP_port", 389, int),
            "use_ssl":      get_env_or_setting("LDAP_use_ssl", False, bool),
            "use_start_tls": get_env_or_setting("LDAP_use_start_tls", False, bool),
            "tls_verify_cert": get_env_or_setting("LDAP_tls_verify_cert", True, bool),
            "ca_cert_path": get_env_or_setting("LDAP_ca_cert_path", "", str).strip(),
            "disable_local_admin": get_env_or_setting("LDAP_disable_local_admin", False, bool),
            "direct_bind_format": get_env_or_setting("LDAP_direct_bind_format", "", str).strip(),
            "bind_dn":      get_env_or_setting("LDAP_bind_dn", "", str).strip(),
            "bind_password": get_secret("LDAP_bind_password"),
            "base_dn":      get_env_or_setting("LDAP_base_dn", "", str).strip(),
            "user_filter":  get_env_or_setting("LDAP_user_filter", "(uid={username})", str).strip(),
            "username_attr": get_env_or_setting("LDAP_username_attribute", "uid", str).strip(),
            "timeout":      5,
        }

        server = cfg["server"]
        if server and not re.match(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*'
            r'|\d{1,3}(?:\.\d{1,3}){3}'
            r'|\[[\da-fA-F:]+\])$',
            server
        ):
            mylog("warning", [f"[auth.ldap] LDAP_server value '{_sanitize_for_log(server)}' does not look like a valid hostname or IP"])

        return cfg

    def _create_secure_connection(self, ldap3, server_obj, cfg: dict, user: Optional[str], password: Optional[str], authentication):
        """
        Creates a secure LDAP connection, handling the StartTLS sequence
        correctly before binding.
        """
        conn = ldap3.Connection(
            server_obj,
            user=user,
            password=password,
            auto_bind=ldap3.AUTO_BIND_NONE,
            authentication=authentication,
        )

        if cfg["use_start_tls"] and not cfg["use_ssl"]:
            if not conn.start_tls():
                mylog("warning", [f"[auth.ldap] StartTLS negotiation failed: {conn.result}"])
                conn.unbind()
                return conn, False

        if not conn.bind():
            return conn, False

        return conn, True

    def _resolve_user_dn(self, ldap3, server_obj, cfg: dict, username: str) -> Optional[str]:
        """
        Bind with the service account and search for the user's DN.
        Returns the DN string on success, None if user is not found.
        Raises if the connection itself fails.
        """
        safe_username = _escape_ldap_filter(username)
        search_filter = cfg["user_filter"].replace("{username}", safe_username)

        authentication = ldap3.SIMPLE if cfg["bind_dn"] else ldap3.ANONYMOUS
        conn, bind_success = self._create_secure_connection(
            ldap3, server_obj, cfg,
            user=cfg["bind_dn"] or None,
            password=cfg["bind_password"] or None,
            authentication=authentication
        )

        try:
            if not bind_success:
                mylog("none", [f"[auth.ldap] Service-account bind failed: {conn.result}"])
                raise ConnectionError(f"LDAP service-account bind failed: {conn.result}")

            conn.search(
                search_base=cfg["base_dn"],
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=[cfg["username_attr"]],
                size_limit=2,
            )

            entries = conn.entries
            if len(entries) != 1:
                mylog("verbose", [
                    f"[auth.ldap] User '{username}' not found "
                    f"(got {len(entries)} entries for filter {search_filter})"
                ])
                return None

            return entries[0].entry_dn

        finally:
            conn.unbind()

    def _bind_as_user(
        self, ldap3, server_obj, cfg: dict,
        user_dn: str, username: str, password: str,
    ) -> AuthResult:
        """
        Attempt to bind as *user_dn* using the supplied *password*.
        A successful bind confirms valid credentials.
        """
        conn, bind_success = self._create_secure_connection(
            ldap3, server_obj, cfg,
            user=user_dn,
            password=password,
            authentication=ldap3.SIMPLE
        )

        try:
            if bind_success:
                return AuthResult.ok(username, self.name)

            mylog("verbose", [f"[auth.ldap] User bind failed for DN '{user_dn}': {conn.result}"])
            return AuthResult.fail(self.name)

        finally:
            conn.unbind()
