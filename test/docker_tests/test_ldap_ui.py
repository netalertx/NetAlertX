import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import pytest
import yaml

if hasattr(socket, "_original_socket"):
    socket.socket = socket._original_socket

# Add docker_tests to sys.path to import helpers
sys.path.insert(0, os.path.dirname(__file__))

from test_docker_compose_scenarios import (  # noqa: E402
    _create_test_data_dirs,
    CONTAINER_PATHS,
    IMAGE,
    _select_custom_ports,
)

pytestmark = [pytest.mark.docker, pytest.mark.compose, pytest.mark.feature_complete, pytest.mark.allow_socket]

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

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    base_dir = tmp_path

    # Create test data directories for NetAlertX
    _create_test_data_dirs(base_dir)
    subprocess.run(["chmod", "-R", "777", str(base_dir / "test_data")], check=True)

    # Create LDAP bootstrap directory
    ldap_bootstrap_dir = base_dir / "ldap_bootstrap"
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
                    "LDAP_ADMIN_PASSWORD": "admin",
                    "LDAP_REMOVE_CONFIG_AFTER_SETUP": "false"
                }
            },
            "netalertx": {
                "image": IMAGE,
                "cap_drop": ["ALL"],
                "cap_add": ["NET_RAW", "NET_ADMIN", "NET_BIND_SERVICE"],
                "tmpfs": ["/tmp:mode=777"],
                "ports": [
                    f"{http_port}:20211",
                    f"{graphql_port}:20212"
                ],
                "depends_on": ["ldap"],
                "volumes": [
                    {
                        "type": "volume",
                        "source": data_volume_name,
                        "target": CONTAINER_PATHS["data"],
                        "read_only": False,
                    }
                ],
                "environment": {
                    "TZ": "UTC",
                    "NETALERTX_DEBUG": "1",
                    "NETALERTX_CHECK_ONLY": "0",  # We want the container to stay running
                    "SKIP_STARTUP_CHECKS": "host optimization",
                    "LOADED_PLUGINS": (
                        "['ARPSCAN', 'AVAHISCAN', 'INTRNT', 'NBTSCAN', 'NSLOOKUP', 'DIGSCAN', "
                        "'SMTP', 'LDAP', 'CSVBCKP', 'CUSTPROP', 'DBCLNP', 'MAINT', 'NEWDEV', "
                        "'NTFPRCS', 'SETPWD', 'SYNC', 'UI', 'VNDRPDT', 'WORKFLOWS']"
                    ),
                    "APP_CONF_OVERRIDE": json.dumps({
                        "LDAP_enabled": True,
                        "LDAP_server": "ldap",
                        "LDAP_port": 389,
                        "LDAP_base_dn": "dc=example,dc=org",
                        "LDAP_user_filter": "(uid={username})",
                        "LDAP_username_attribute": "uid",
                        "LDAP_bind_dn": "cn=admin,dc=example,dc=org",
                        "LDAP_bind_password": "admin",
                        "LDAP_use_ssl": False,
                        "LDAP_use_start_tls": False,
                        "SETPWD_enable_password": True
                    })
                }
            }
        }
    }

    compose_file = base_dir / "docker-compose.yml"
    with open(compose_file, "w") as f:
        yaml.dump(compose_config, f)

    print(f"Starting docker-compose for {project_name} on HTTP port {http_port}...")

    def get_container_name(service):
        try:
            cmd = [
                "docker", "ps",
                "--filter", f"label=com.docker.compose.project={project_name}",
                "--filter", f"label=com.docker.compose.service={service}",
                "--format", "{{.Names}}",
            ]
            return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10).stdout.strip().split('\n')[0]
        except Exception:
            return f"{project_name}-{service}-1"

    try:
        # Start detached using subprocess directly to avoid test_docker_compose_scenarios.py's auto-teardown
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "-p", project_name, "up", "-d"],
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
            timeout=180
        )

        container_name = get_container_name("netalertx")
        ldap_container = get_container_name("ldap")

        # Connect the test container to the compose network to access the internal IPs directly
        is_container = False
        test_container_id = None

        try:
            with open("/proc/self/cpuset", "r") as f:
                content = f.read().strip()
                if "docker" in content:
                    is_container = True
                    test_container_id = content.split("/")[-1].strip()
        except Exception:
            pass

        if not is_container:
            try:
                with open("/proc/1/cpuset", "r") as f:
                    content = f.read().strip()
                    if "docker" in content:
                        is_container = True
                        test_container_id = content.split("/")[-1].strip()
            except Exception:
                pass

        if not test_container_id:
            try:
                with open("/etc/hostname", "r") as f:
                    test_container_id = f.read().strip()
            except Exception:
                test_container_id = socket.gethostname()

        network_name = f"{project_name}_default"
        if is_container:
            print(f"Connecting test container {test_container_id} to network {network_name}...")
            res = subprocess.run(
                ["docker", "network", "connect", network_name, test_container_id],
                check=False,
                capture_output=True,
                text=True,
            )
            if res.returncode != 0 and "already exists" not in res.stderr:
                raise RuntimeError(f"Failed to connect to network {network_name}: {res.stderr}")

            # Check host resolution
            try:
                socket.getaddrinfo(container_name, 20211)
            except socket.gaierror:
                # Some environments take a second to propagate DNS
                time.sleep(2)
                try:
                    socket.getaddrinfo(container_name, 20211)
                except socket.gaierror as e:
                    print(f"Warning: Could not resolve hostname {container_name} after connecting to network: {e}")

        # Wait for LDAP to become ready
        print("Waiting for LDAP server to accept connections...")
        for _ in range(30):
            try:
                subprocess.run(
                    ["docker", "exec", ldap_container, "ldapwhoami", "-x", "-D", "cn=admin,dc=example,dc=org", "-w", "admin"],
                    capture_output=True, check=True, timeout=5
                )
                print("LDAP server is ready!")
                break
            except Exception:
                time.sleep(2)
        else:
            print("Warning: LDAP server did not become ready, proceeding anyway to attempt seeding.")

        target_host = container_name if is_container else "127.0.0.1"
        target_port = 20211 if is_container else http_port

        print(f"Waiting for NetAlertX internal container on {target_host}:{target_port}...")
        for _ in range(45):
            try:
                with socket.create_connection((target_host, target_port), timeout=2):
                    print("Port is ready!")
                    break
            except OSError:
                time.sleep(2)
        else:
            print(f"Warning: NetAlertX port {target_port} on {target_host} did not become ready for socket check, but we will proceed to selenium.")
            print("\n--- BEGIN CONTAINER LOGS ---")
            subprocess.run(["docker", "logs", container_name], check=False, timeout=10)
            print("\n--- BEGIN PYTHON STDERR ---")
            subprocess.run(["docker", "exec", container_name, "cat", "/tmp/log/stderr.log"], check=False, timeout=10)
            print("--- END LOGS ---\n")

        # Seed LDAP via docker exec
        print(f"Seeding LDAP users into {ldap_container}...")
        subprocess.run(
            ["docker", "exec", "-i", ldap_container, "ldapadd", "-x", "-D", "cn=admin,dc=example,dc=org", "-w", "admin"],
            input=LDIF_CONTENT,
            text=True,
            check=True,
            timeout=10
        )

        # Now, the netalertx container should be up. Let's run the selenium test INSIDE the container.
        # Give PHP/Nginx extra time to fully bootstrap UI
        time.sleep(5)

        # Force LDAP_enabled and password protection in app.conf so the PHP UI detects it
        print("Forcing LDAP_enabled to true in app.conf for the UI...")
        sed_script = (
            "sed '/LDAP_enabled/d' /data/config/app.conf | sed '/SETPWD_enable_password/d' > /tmp/app.conf "
            "&& echo 'LDAP_enabled=True' >> /tmp/app.conf "
            "&& echo 'SETPWD_enable_password=True' >> /tmp/app.conf "
            "&& cat /tmp/app.conf > /data/config/app.conf"
        )
        subprocess.run(
            ["docker", "exec", "-u", "root", container_name, "/bin/sh", "-c", sed_script],
            check=True,
            timeout=10,
        )

        # Run the selenium test directly targeting the compose stack's accessible address
        print(f"Running UI test against {target_host} on port {target_port}...")
        ldap_ui_test = repo_root / "test" / "ui" / "test_ui_ldap_login.py"
        cmd = [
            sys.executable, "-m", "pytest", str(ldap_ui_test), "-v", "-s"
        ]

        env = os.environ.copy()
        env["BASE_URL"] = f"http://{target_host}:{target_port}"
        env["UI_BASE_URL"] = f"http://{target_host}:{target_port}"

        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180
        )

        print("--- UI Test STDOUT ---")
        print(result.stdout)
        print("--- UI Test STDERR ---")
        print(result.stderr)

        if result.returncode != 0:
            print("--- PHP ERROR LOG ---")
            subprocess.run(["docker", "exec", container_name, "cat", "/tmp/log/app.php_errors.log"], check=False)
            print("--- NGINX ERROR LOG ---")
            subprocess.run(["docker", "exec", container_name, "cat", "/tmp/log/nginx-error.log"], check=False)
            print("--- APP LOG (LAST 50) ---")
            subprocess.run(["docker", "exec", container_name, "tail", "-n", "50", "/tmp/log/app.log"], check=False)
            print("--- APP.CONF ---")
            subprocess.run(["docker", "exec", container_name, "cat", "/data/config/app.conf"], check=False)

            # If test fails, try to fetch python/nginx logs from the container
            logs_cmd = ["docker", "logs", container_name]
            logs_res = subprocess.run(logs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            print("--- NETALERTX LOGS ---")
            print(logs_res.stdout)
            print(logs_res.stderr)

            ldap_logs_cmd = ["docker", "logs", f"{project_name}-ldap-1"]
            ldap_logs_res = subprocess.run(ldap_logs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
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
            check=False,
            timeout=60
        )
