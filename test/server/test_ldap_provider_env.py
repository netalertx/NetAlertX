import os
import unittest
from unittest.mock import patch, MagicMock

from server.auth.ldap_provider import LdapProvider


class TestLdapProviderEnv(unittest.TestCase):
    @patch("server.auth.ldap_provider.get_setting_value")
    @patch.dict(os.environ, {}, clear=True)
    def test_read_config_no_env(self, mock_get_setting):
        """Test that settings are read from the database if no ENV is set."""
        mock_get_setting.side_effect = lambda k: {
            "LDAP_server": "db.example.com",
            "LDAP_port": "3890",
            "LDAP_use_ssl": "true",
            "LDAP_tls_verify_cert": "1",
            "LDAP_disable_local_admin": "false"
        }.get(k, None)

        provider = LdapProvider()
        cfg = provider._read_config()

        self.assertEqual(cfg["server"], "db.example.com")
        self.assertEqual(cfg["port"], 3890)
        self.assertEqual(cfg["use_ssl"], True)
        self.assertEqual(cfg["tls_verify_cert"], True)
        self.assertEqual(cfg["disable_local_admin"], False)

    @patch("server.auth.ldap_provider.get_setting_value")
    @patch.dict(os.environ, {
        "LDAP_SERVER": "env.example.com",
        "LDAP_PORT": "6360",
        "LDAP_USE_SSL": "false",
        "LDAP_TLS_VERIFY_CERT": "0",
        "LDAP_DISABLE_LOCAL_ADMIN": "true",
        "LDAP_BIND_DN": "cn=admin,dc=env,dc=com",
        "LDAP_BIND_PASSWORD": "envpassword"
    }, clear=True)
    def test_read_config_with_env(self, mock_get_setting):
        """Test that ENV variables override database settings."""
        # Database has different values
        mock_get_setting.side_effect = lambda k: {
            "LDAP_server": "db.example.com",
            "LDAP_port": "3890",
            "LDAP_use_ssl": "true",
            "LDAP_tls_verify_cert": "1",
            "LDAP_disable_local_admin": "false",
            "LDAP_bind_dn": "cn=dbadmin,dc=db,dc=com"
        }.get(k, None)

        provider = LdapProvider()
        cfg = provider._read_config()

        self.assertEqual(cfg["server"], "env.example.com")
        self.assertEqual(cfg["port"], 6360)
        self.assertEqual(cfg["use_ssl"], False)
        self.assertEqual(cfg["tls_verify_cert"], False)
        self.assertEqual(cfg["disable_local_admin"], True)
        self.assertEqual(cfg["bind_dn"], "cn=admin,dc=env,dc=com")
        self.assertEqual(cfg["bind_password"], "envpassword")

if __name__ == '__main__':
    unittest.main()
