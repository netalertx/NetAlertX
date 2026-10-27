import unittest
from unittest.mock import MagicMock, patch

from server.auth.ldap_provider import LdapProvider

class TestLdapProvider(unittest.TestCase):
    def test_start_tls_before_bind(self):
        mock_ldap3 = MagicMock()
        # Create a mock connection object
        mock_conn = MagicMock()
        mock_ldap3.Connection.return_value = mock_conn
        
        # Configure a test scenario where start_tls is enabled
        provider = LdapProvider()
        
        cfg = {
            "use_start_tls": True,
            "use_ssl": False,
            "bind_dn": "cn=admin,dc=example,dc=com",
            "bind_password": "password123",
            "base_dn": "dc=example,dc=com",
            "user_filter": "(uid={username})",
            "username_attr": "uid",
            "server": "ldap.example.com",
            "port": 389,
            "timeout": 5,
        }
        
        mock_server = MagicMock()
        
        # Call the secure connection method
        provider._create_secure_connection(
            mock_ldap3,
            mock_server,
            cfg,
            user=cfg["bind_dn"],
            password=cfg["bind_password"],
            authentication=mock_ldap3.SIMPLE
        )
        
        # Assert start_tls was called
        mock_conn.start_tls.assert_called_once()
        
        # Assert bind was called
        mock_conn.bind.assert_called_once()
        
        # Determine the order of calls
        mock_calls = mock_conn.mock_calls
        start_tls_idx = next(i for i, call in enumerate(mock_calls) if call[0] == 'start_tls')
        bind_idx = next(i for i, call in enumerate(mock_calls) if call[0] == 'bind')
        
        # The critical assertion: start_tls must happen BEFORE bind
        self.assertLess(start_tls_idx, bind_idx, "start_tls MUST be called before bind")

    @patch('server.auth.ldap_provider.ldap3')
    @patch('server.auth.ldap_provider.ssl')
    def test_tls_verify_cert(self, mock_ssl, mock_ldap3):
        provider = LdapProvider()
        
        # Mock _read_config to return our test cfg
        cfg = {
            "server": "ldap.example.com",
            "port": 636,
            "use_ssl": True,
            "use_start_tls": False,
            "tls_verify_cert": True,
            "ca_cert_path": "/path/to/ca.crt",
            "bind_dn": "",
            "bind_password": "",
            "base_dn": "dc=example,dc=com",
            "user_filter": "(uid={username})",
            "username_attr": "uid",
            "timeout": 5,
        }
        provider._read_config = MagicMock(return_value=cfg)
        
        provider._resolve_user_dn = MagicMock(return_value="uid=test,dc=example,dc=com")
        provider._bind_as_user = MagicMock(return_value=MagicMock(success=True))
        
        mock_tls_obj = MagicMock()
        mock_ldap3.Tls.return_value = mock_tls_obj
        mock_ssl.CERT_REQUIRED = 2
        
        provider.authenticate("testuser", "testpassword")
        
        # Assert Tls object created with validation and CA path
        mock_ldap3.Tls.assert_called_once_with(validate=2, ca_certs_file="/path/to/ca.crt")
        
        # Assert Server object created with tls object
        mock_ldap3.Server.assert_called_once_with(
            "ldap.example.com",
            port=636,
            use_ssl=True,
            tls=mock_tls_obj,
            connect_timeout=5,
            get_info=mock_ldap3.NONE
        )

if __name__ == '__main__':
    unittest.main()
