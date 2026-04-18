import os
import pathlib
import subprocess
import time
import yaml
import pytest
import socket
if hasattr(socket, "_original_socket"):
    socket.socket = socket._original_socket


# Add docker_tests to sys.path to import helpers
import sys
sys.path.insert(0, os.path.dirname(__file__))

from test_docker_compose_scenarios import (
    _create_test_data_dirs,
    _run_docker_compose,
    CONTAINER_PATHS,
    TMPFS_ROOT,
    IMAGE,
    _select_custom_ports,
    _wait_for_ports,
)

pytestmark = [pytest.mark.docker, pytest.mark.compose, pytest.mark.feature_complete]

LDIF_CONTENT = """dn: ou=users,dc=example,dc=org
objectClass: organizationalUnit
ou: users

dn: uid=testuser,ou=users,dc=example,dc=org
objectClass: top
objectClass: account
objectClass: posixAccount
objectClass: shadowAccount
cn: testuser
uid: testuser
uidNumber: 10000
gidNumber: 10000
homeDirectory: /home/testuser
userPassword: testpassword
loginShell: /bin/bash
"""

def test_ldap_ui_login(tmp_path: pathlib.Path):
    """
    Spins up an LDAP server and NetAlertX container using Docker Compose,
    configures LDAP in NetAlertX, and runs a Selenium UI test to log in.
    """
    project_name = f"netalertx-ldap-{int(time.time())}"
    
    # Create test data directories for NetAlertX
    _create_test_data_dirs(tmp_path)
    
    # Configure app.conf with LDAP settings
    config_file = tmp_path / "test_data" / "data" / "config" / "app.conf"
    with open(config_file, "a") as f:
        f.write("\n")
        f.write("LDAP_enabled=True\n")
        f.write("LDAP_server=\"ldap\"\n")
        f.write("LDAP_port=389\n")
        f.write("LDAP_base_dn=\"dc=example,dc=org\"\n")
        f.write("LDAP_user_filter=\"(uid={username})\"\n")
        f.write("LDAP_login_attribute=\"uid\"\n")
        f.write("LDAP_bind_dn=\"cn=admin,dc=example,dc=org\"\n")
        f.write("LDAP_bind_password=\"admin\"\n")
        f.write("LDAP_use_ssl=False\n")
        f.write("LDAP_use_starttls=False\n")
    
    # Create LDAP bootstrap directory
    ldap_bootstrap_dir = tmp_path / "test_data" / "ldap_bootstrap"
    ldap_bootstrap_dir.mkdir(parents=True, exist_ok=True)
    ldif_file = ldap_bootstrap_dir / "users.ldif"
    ldif_file.write_text(LDIF_CONTENT)
    ldif_file.chmod(0o666)

    # Choose a port
    http_port = _select_custom_ports()
    graphql_port = _select_custom_ports({http_port})
    
    data_volume_name = f"{project_name}_data"
    
    compose_config = {
        "version": "3.8",
        "volumes": {
            data_volume_name: {}
        },
        "services": {
            "ldap": {
                "image": "osixia/openldap:1.5.0",
                "environment": {
                    "LDAP_ORGANISATION": "Example Inc.",
                    "LDAP_DOMAIN": "example.org",
                    "LDAP_ADMIN_PASSWORD": "admin"
                },
                "volumes": [
                    f"{ldap_bootstrap_dir.absolute()}:/container/service/slapd/assets/config/bootstrap/ldif/custom"
                ]
            },
            "netalertx": {
                "image": IMAGE,
                "read_only": True,
                "cap_drop": ["ALL"],
                "cap_add": ["NET_RAW", "NET_ADMIN", "NET_BIND_SERVICE"],
                "user": "20211:20211",
                "tmpfs": [TMPFS_ROOT],
                "ports": [
                    f"{http_port}:20211",
                    f"{graphql_port}:20212"
                ],
                "depends_on": ["ldap"],
                "volumes": [
                    f"{tmp_path / 'test_data' / 'data'}:{CONTAINER_PATHS['data']}",
                    f"{tmp_path / 'test_data' / 'log'}:{CONTAINER_PATHS['log']}",
                    f"{tmp_path / 'test_data' / 'api'}:{CONTAINER_PATHS['api']}",
                    f"{tmp_path / 'test_data' / 'nginx_conf'}:{CONTAINER_PATHS['nginx_active']}",
                    f"{tmp_path / 'test_data' / 'run'}:{CONTAINER_PATHS['run']}"
                ],
                "environment": {
                    "TZ": "UTC",
                    "NETALERTX_CHECK_ONLY": "0",  # We want the container to stay running
                    "SKIP_STARTUP_CHECKS": "host optimization"
                }
            }
        }
    }
    
    compose_file = tmp_path / "docker-compose.yml"
    with open(compose_file, "w") as f:
        yaml.dump(compose_config, f)
        
    print(f"Starting docker-compose for {project_name} on HTTP port {http_port}...")
    
    try:
        # Start detached
        _run_docker_compose(
            compose_file=compose_file,
            project_name=project_name,
            timeout=60,
            detached=True
        )
        
        print("Waiting for ports and settling...")
        # Give LDAP and NetAlertX a few seconds to come up
        time.sleep(10)
        _wait_for_ports([http_port, graphql_port], timeout=45)
        
        # Now, the netalertx container should be up. Let's run the selenium test INSIDE the container.
        # Note: In devcontainers/GitHub Actions, `docker exec` can be invoked to run tests.
        container_name = f"{project_name}-netalertx-1"
        
        # Give PHP/Nginx extra time to fully bootstrap UI
        time.sleep(10)
        
        print(f"Running UI test inside {container_name}...")
        cmd = [
            "docker", "exec", container_name,
            "pytest", "/app/test/ui/test_ui_ldap_login.py", "-v"
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("--- UI Test STDOUT ---")
        print(result.stdout)
        print("--- UI Test STDERR ---")
        print(result.stderr)
        
        if result.returncode != 0:
            # If test fails, try to fetch python/nginx logs from the container
            logs_cmd = ["docker", "logs", container_name]
            logs_res = subprocess.run(logs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print("--- NETALERTX LOGS ---")
            print(logs_res.stdout)
            print(logs_res.stderr)
            
            ldap_logs_cmd = ["docker", "logs", f"{project_name}-ldap-1"]
            ldap_logs_res = subprocess.run(ldap_logs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print("--- LDAP LOGS ---")
            print(ldap_logs_res.stdout)
            print(ldap_logs_res.stderr)
            
        assert result.returncode == 0, "LDAP UI test failed!"
        
    finally:
        print("Tearing down docker compose stack...")
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "-p", project_name, "down", "-v"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            check=False
        )
