import sys
import os

# Add server path to sys.path
INSTALL_PATH = os.getenv("NETALERTX_APP", "/app")
sys.path.append(f"{INSTALL_PATH}/server")

from auth.ldap_provider import LdapProvider

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test LDAP Connection")
    parser.add_argument("--test-user", help="Optional test username to resolve")
    args = parser.parse_args()

    print("[LDAP Test] Starting LDAP connection test...")
    provider = LdapProvider()
    cfg = provider._read_config()
    
    if not cfg.get("server"):
        print("[LDAP Test] ❌ ERROR: LDAP server not configured")
        sys.exit(1)
        
    try:
        import ldap3
        
        server_obj = provider._get_server_obj(ldap3, cfg)
        
        print(f"[LDAP Test] Attempting to connect to {cfg['server']}:{cfg['port']}...")
        
        authentication = ldap3.SIMPLE if cfg["bind_dn"] else ldap3.ANONYMOUS
        conn, bind_success = provider._create_secure_connection(
            ldap3, server_obj, cfg,
            user=cfg["bind_dn"] or None,
            password=cfg["bind_password"] or None,
            authentication=authentication
        )
        
        if not bind_success:
            print(f"[LDAP Test] ❌ ERROR: Service-account bind failed: {conn.result}")
            sys.exit(1)
            
        print("[LDAP Test] ✅ SUCCESS: Connected to LDAP server and successfully bound with service account.")
        print(f"[LDAP Test] Base DN: {cfg['base_dn']}")
        print(f"[LDAP Test] User Filter: {cfg['user_filter']}")
        
        if args.test_user:
            from auth.ldap_provider import _escape_ldap_filter
            safe_username = _escape_ldap_filter(args.test_user)
            search_filter = cfg["user_filter"].replace("{username}", safe_username)
            print(f"[LDAP Test] Searching for user '{args.test_user}' with filter: {search_filter}")
            
            conn.search(
                search_base=cfg["base_dn"],
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=[cfg["username_attr"]],
                size_limit=2,
            )
            
            entries = conn.entries
            exit_code = 0
            if len(entries) == 1:
                print(f"[LDAP Test] ✅ SUCCESS: Found user DN: {entries[0].entry_dn}")
            elif len(entries) == 0:
                print("[LDAP Test] ❌ ERROR: User not found")
                exit_code = 1
            else:
                print(f"[LDAP Test] ❌ ERROR: Found multiple ({len(entries)}) entries for user")
                exit_code = 1
        
        conn.unbind()
        if args.test_user and exit_code:
            sys.exit(exit_code)
        
    except Exception as e:
        print(f"[LDAP Test] ❌ ERROR: Unexpected error testing LDAP: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
