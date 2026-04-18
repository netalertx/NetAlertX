import sys
sys.path.append("server")
from unittest.mock import patch
from auth.manager import AuthManager

with patch("auth.manager.LdapProvider._read_config", return_value={"enabled": True}):
    manager = AuthManager()
    provider = manager.get_provider()
    print("Provider:", provider.name)
