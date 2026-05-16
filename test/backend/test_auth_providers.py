"""
Unit tests for the NetAlertX auth provider stack.

These tests use unittest.mock.patch so they can run without a live database,
LDAP server, or running Flask application.
"""

from __future__ import annotations

import hashlib
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

@pytest.fixture(autouse=True)
def mock_all_mylogs():
    with patch("auth.local_provider.mylog"), \
         patch("auth.ldap_provider.mylog"), \
         patch("auth.manager.mylog"), \
         patch("helper.mylog"), \
         patch("logger.mylog"):
        yield

# Register NetAlertX server directory so bare module imports resolve
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ===========================================================================
# AuthResult
# ===========================================================================

class TestAuthResult:
    def test_ok_factory(self):
        from auth.base import AuthResult
        r = AuthResult.ok("alice", "local")
        assert r.success is True
        assert r.username == "alice"
        assert r.provider == "local"
        assert r.error == ""

    def test_fail_factory(self):
        from auth.base import AuthResult
        r = AuthResult.fail("ldap", "bad creds")
        assert r.success is False
        assert r.provider == "ldap"
        assert r.error == "bad creds"


# ===========================================================================
# LocalProvider
# ===========================================================================

class TestLocalProvider:
    def test_correct_password(self):
        from auth.local_provider import LocalProvider
        pw = "correct_horse"
        with patch("auth.local_provider.get_setting_value", return_value=_sha256(pw)):
            result = LocalProvider().authenticate("admin", pw)
        assert result.success is True
        assert result.provider == "local"
        assert result.username == "admin"

    def test_wrong_password(self):
        from auth.local_provider import LocalProvider
        pw = "correct_horse"
        with patch("auth.local_provider.get_setting_value", return_value=_sha256(pw)):
            result = LocalProvider().authenticate("admin", "wrong_password")
        assert result.success is False
        assert result.provider == "local"

    def test_empty_password_rejected(self):
        from auth.local_provider import LocalProvider
        with patch("auth.local_provider.get_setting_value", return_value=_sha256("abc")):
            result = LocalProvider().authenticate("admin", "")
        assert result.success is False

    def test_missing_stored_hash(self):
        from auth.local_provider import LocalProvider
        with patch("auth.local_provider.get_setting_value", return_value=""), \
             patch("auth.local_provider.mylog"):
            result = LocalProvider().authenticate("admin", "anything")
        assert result.success is False

    def test_default_password_hash(self):
        """The shipped default password '123456' must authenticate correctly."""
        from auth.local_provider import LocalProvider
        default_hash = "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92"
        with patch("auth.local_provider.get_setting_value", return_value=default_hash):
            result = LocalProvider().authenticate("admin", "123456")
        assert result.success is True

    def test_any_username_accepted(self):
        """Local provider does not validate username — any value should work."""
        from auth.local_provider import LocalProvider
        pw = "secret"
        with patch("auth.local_provider.get_setting_value", return_value=_sha256(pw)):
            result = LocalProvider().authenticate("anyone", pw)
        assert result.success is True
        assert result.username == "anyone"


# ===========================================================================
# LdapProvider
# ===========================================================================

class TestLdapProvider:
    """LdapProvider is tested with a fully mocked ldap3 module."""

    def _cfg(self, **overrides):
        cfg = {
            "server": "ldap.example.com",
            "port": 389,
            "use_ssl": False,
            "use_start_tls": False,
            "bind_dn": "cn=svc,dc=example,dc=com",
            "bind_password": "svc_pass",
            "base_dn": "dc=example,dc=com",
            "user_filter": "(uid={username})",
            "username_attr": "uid",
            "timeout": 5,
        }
        cfg.update(overrides)
        return cfg

    def _make_ldap3_mock(self, *, bind_success=True, search_entries=1, user_bind_success=True):
        """Build a mock ldap3 module with the minimal interface needed."""
        ldap3 = MagicMock()
        ldap3.NONE = "NONE"
        ldap3.SIMPLE = "SIMPLE"
        ldap3.ANONYMOUS = "ANONYMOUS"
        ldap3.AUTO_BIND_NONE = "AUTO_BIND_NONE"
        ldap3.SUBTREE = "SUBTREE"

        # Service account connection
        svc_conn = MagicMock()
        svc_conn.bind.return_value = bind_success
        svc_conn.result = {"description": "success"} if bind_success else {"description": "invalidCredentials"}
        fake_entries = [MagicMock(entry_dn=f"uid=alice,dc=example,dc=com") for _ in range(search_entries)]
        svc_conn.entries = fake_entries

        # User connection
        user_conn = MagicMock()
        user_conn.bind.return_value = user_bind_success
        user_conn.result = {"description": "success"} if user_bind_success else {"description": "invalidCredentials"}

        # Connection() always returns svc_conn first, then user_conn
        ldap3.Connection.side_effect = [svc_conn, user_conn]
        ldap3.Server.return_value = MagicMock()

        return ldap3, svc_conn, user_conn

    def test_successful_authentication(self):
        from auth.ldap_provider import LdapProvider
        provider = LdapProvider()
        ldap3_mock, _, _ = self._make_ldap3_mock()

        with patch("auth.ldap_provider.ldap3", ldap3_mock), \
             patch("auth.ldap_provider.get_setting_value", side_effect=lambda k: self._cfg().get(k.replace("LDAP_", ""), "")):
            provider._read_config = lambda: self._cfg()
            result = provider.authenticate("alice", "password")

        assert result.success is True
        assert result.provider == "ldap"
        assert result.username == "alice"

    def test_service_account_bind_fails(self):
        from auth.ldap_provider import LdapProvider
        provider = LdapProvider()
        ldap3_mock, _, _ = self._make_ldap3_mock(bind_success=False)

        with patch.dict("sys.modules", {"ldap3": ldap3_mock}):
            provider._read_config = lambda: self._cfg()
            with pytest.raises(ConnectionError):
                provider._resolve_user_dn(ldap3_mock, MagicMock(), self._cfg(), "alice")

    def test_user_not_found_in_ldap(self):
        from auth.ldap_provider import LdapProvider
        provider = LdapProvider()
        ldap3_mock, _, _ = self._make_ldap3_mock(search_entries=0)

        with patch.dict("sys.modules", {"ldap3": ldap3_mock}):
            provider._read_config = lambda: self._cfg()
            result = provider._resolve_user_dn(ldap3_mock, MagicMock(), self._cfg(), "unknown_user")
        assert result is None

    def test_user_password_wrong(self):
        from auth.ldap_provider import LdapProvider
        provider = LdapProvider()

        ldap3 = MagicMock()
        ldap3.SIMPLE = "SIMPLE"
        ldap3.AUTO_BIND_NONE = "AUTO_BIND_NONE"

        user_conn = MagicMock()
        user_conn.bind.return_value = False
        user_conn.result = {"description": "invalidCredentials"}
        ldap3.Connection.return_value = user_conn

        with patch.dict("sys.modules", {"ldap3": ldap3}):
            provider._read_config = lambda: self._cfg()
            result = provider._bind_as_user(
                ldap3, MagicMock(), self._cfg(),
                "uid=alice,dc=example,dc=com", "alice", "wrong"
            )
        assert result.success is False

    def test_missing_server_config(self):
        from auth.ldap_provider import LdapProvider
        provider = LdapProvider()
        with patch("auth.ldap_provider.get_setting_value", return_value=""):
            result = provider.authenticate("alice", "pw")
        assert result.success is False

    def test_ldap_filter_escaping(self):
        """Special characters in username must be escaped in the LDAP filter."""
        from auth.ldap_provider import _escape_ldap_filter
        assert _escape_ldap_filter("a*b(c)d\\e\x00f") == r"a\2ab\28c\29d\5ce\00f"

    def test_missing_ldap3_package(self):
        """Graceful failure when ldap3 is not installed."""
        from auth.ldap_provider import LdapProvider
        provider = LdapProvider()
        provider._read_config = lambda: self._cfg()

        with patch("auth.ldap_provider.ldap3", None):
            result = provider.authenticate("alice", "pw")
        assert result.success is False


# ===========================================================================
# AuthManager
# ===========================================================================

class TestAuthManager:
    def test_uses_local_when_ldap_disabled(self):
        from auth.manager import AuthManager
        with patch("auth.manager.get_setting_value", return_value=False):
            manager = AuthManager()
            provider = manager.get_provider()
        assert provider.name == "local"

    def test_uses_ldap_when_ldap_enabled(self):
        from auth.manager import AuthManager
        with patch("auth.manager.LdapProvider._read_config", return_value={"enabled": True}):
            manager = AuthManager()
            provider = manager.get_provider()
        assert provider.name == "ldap"

    def test_authenticate_uses_local_when_ldap_disabled(self):
        from auth.manager import AuthManager
        from auth.base import AuthResult
        
        manager = AuthManager()
        with patch("auth.manager.get_setting_value", return_value=False), \
             patch("auth.manager.LocalProvider.authenticate", return_value=AuthResult.ok("admin", "local")) as mock_auth:
            result = manager.authenticate("admin", "pass")
            
        mock_auth.assert_called_once_with("admin", "pass")
        assert result.success is True

    def test_authenticate_uses_ldap_when_ldap_enabled(self):
        from auth.manager import AuthManager
        from auth.base import AuthResult

        def mock_settings(key):
            if key == "SETPWD_enable_password": return True
            return False

        manager = AuthManager()
        with patch("auth.manager.LdapProvider._read_config", return_value={"enabled": True, "disable_local_admin": True}), \
             patch("auth.manager.get_setting_value", side_effect=mock_settings), \
             patch("auth.manager.LdapProvider.authenticate", return_value=AuthResult.ok("admin", "ldap")) as mock_auth:
            result = manager.authenticate("admin", "pass")
            
        mock_auth.assert_called_once_with("admin", "pass")
        assert result.success is True

    def test_authenticate_fallback_to_local(self):
        from auth.manager import AuthManager
        from auth.base import AuthResult
        from auth.ldap_provider import LdapProvider

        def mock_settings(key):
            if key == "LDAP_enabled":
                return True
            if key == "SETPWD_enable_password":
                return True
            if key == "LDAP_disable_local_admin":
                return True
            return False

        manager = AuthManager()
        with patch("auth.manager.LdapProvider._read_config", return_value={"enabled": True, "disable_local_admin": False}), \
             patch("auth.manager.get_setting_value", side_effect=mock_settings), \
             patch("auth.manager.LdapProvider.authenticate", return_value=AuthResult.fail("ldap", LdapProvider.USER_NOT_FOUND)), \
             patch("auth.manager.LocalProvider.authenticate", return_value=AuthResult.ok("admin", "local")) as mock_local_auth:
            result = manager.authenticate("admin", "pass")
            
        mock_local_auth.assert_called_once_with("admin", "pass")
        assert result.success is True
        assert result.provider == "local"

