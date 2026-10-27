'''
Tests for 99-ports-available.sh entrypoint script.
This script checks for port conflicts and availability.

This is a Shell-based pre-flight check that runs before the main application.
It ensures that the configured ports are valid and available, preventing
hard-to-debug binding errors later in the startup process.
'''

import os
import pathlib
import subprocess
import time
import pytest

IMAGE = os.environ.get("NETALERTX_TEST_IMAGE", "netalertx-test")
GRACE_SECONDS = float(os.environ.get("NETALERTX_TEST_GRACE", "2"))

CONTAINER_TARGETS = {
    "data": "/data",
    "app_db": "/data/db",
    "app_config": "/data/config",
    "app_log": "/tmp/log",
    "app_api": os.environ.get("NETALERTX_API", "/tmp/api"),
    "nginx_conf": "/tmp/nginx/active-config",
    "services_run": "/tmp/run",
}

pytestmark = [pytest.mark.docker, pytest.mark.feature_complete, pytest.mark.allow_socket]


@pytest.fixture(scope="function")
def dummy_container(tmp_path):
    """Fixture that starts a dummy container to occupy ports for testing."""
    # Create a simple docker-compose file for the dummy container
    compose_file = tmp_path / "docker-compose-dummy.yml"
    with open(compose_file, 'w') as f:
        f.write("version: '3.8'\n")
        f.write("services:\n")
        f.write("  dummy:\n")
        f.write("    image: alpine:latest\n")
        f.write("    network_mode: host\n")
        f.write("    userns_mode: host\n")
        f.write("    command: sh -c \"while true; do nc -l -p 20211 < /dev/null > /dev/null; done & while true; do nc -l -p 20212 < /dev/null > /dev/null; done & sleep 30\"\n")

    # Start the dummy container
    import subprocess
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        pytest.fail(f"Failed to start dummy container: {result.stderr}")

    # Wait a bit for the container to start listening
    time.sleep(3)

    yield "dummy"

    # Cleanup
    subprocess.run(["docker", "compose", "-f", str(compose_file), "down"], capture_output=True)


def _setup_mount_tree(tmp_path: pathlib.Path, label: str) -> dict[str, pathlib.Path]:
    """Set up mount tree for testing."""
    import shutil

    base = tmp_path / f"{label}_mount_root"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)

    paths: dict[str, pathlib.Path] = {}

    data_root = base / f"{label}_DATA_INTENTIONAL_NETALERTX_TEST"
    data_root.mkdir(parents=True, exist_ok=True)
    data_root.chmod(0o777)
    paths["data"] = data_root

    db_dir = data_root / "db"
    db_dir.mkdir(exist_ok=True)
    db_dir.chmod(0o777)
    paths["app_db"] = db_dir

    config_dir = data_root / "config"
    config_dir.mkdir(exist_ok=True)
    config_dir.chmod(0o777)
    paths["app_config"] = config_dir

    # Seed config and database from repository defaults when available
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    config_src = repo_root / "back" / "app.conf"
    db_src = repo_root / "db" / "app.db"

    if config_src.exists():
        shutil.copyfile(config_src, config_dir / "app.conf")
        (config_dir / "app.conf").chmod(0o600)
    if db_src.exists():
        shutil.copyfile(db_src, db_dir / "app.db")
        (db_dir / "app.db").chmod(0o600)

    return paths


def _build_volume_args(paths: dict[str, pathlib.Path]) -> list[tuple[str, str, bool]]:
    """Build volume arguments for docker run."""
    return [(str(paths["data"]), CONTAINER_TARGETS["data"], False)]


def _run_container(
    label: str,
    volumes: list[tuple[str, str, bool]] | None = None,
    *,
    env: dict[str, str] | None = None,
    user: str | None = None,
    network_mode: str | None = "host",
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a container and return the result."""
    import uuid
    import re

    name = f"netalertx-test-{label}-{uuid.uuid4().hex[:8]}".lower()
    cmd = ["docker", "run", "--rm", "--name", name]

    if network_mode:
        cmd.extend(["--network", network_mode])
    cmd.extend(["--userns", "host"])
    cmd.extend(["--tmpfs", "/tmp:mode=777"])
    if user:
        cmd.extend(["--user", user])
    if env:
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
    if extra_args:
        cmd.extend(extra_args)
    for host_path, target, readonly in volumes or []:
        mount = f"{host_path}:{target}"
        if readonly:
            mount += ":ro"
        cmd.extend(["-v", mount])

    # Copy the script content and run it
    script_path = pathlib.Path("install/production-filesystem/entrypoint.d/99-ports-available.sh")
    with script_path.open('r', encoding='utf-8') as f:
        script_cont = f.read()

    # Use printf to avoid shell interpretation issues
    script = f"printf '%s\\n' '{script_cont.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}' > /tmp/ports-check.sh && chmod +x /tmp/ports-check.sh && sh /tmp/ports-check.sh"  # noqa: E501 - inline script
    cmd.extend(["--entrypoint", "/bin/sh", IMAGE, "-c", script])

    print(f"\n--- DOCKER CMD ---\n{' '.join(cmd)}\n--- END CMD ---\n")
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )

    # Combine and clean stdout and stderr
    stdouterr = (
        re.sub(r'\x1b\[[0-9;]*m', '', result.stdout or '') + re.sub(r'\x1b\[[0-9;]*m', '', result.stderr or '')
    )
    result.output = stdouterr
    print(f"\n--- CONTAINER stdout ---\n{result.stdout}")
    print(f"\n--- CONTAINER stderr ---\n{result.stderr}")
    print(f"\n--- CONTAINER combined ---\n{result.output}")

    return result


def _assert_contains(result, snippet: str, cmd: list[str] = None) -> None:
    """Assert that the result output contains the given snippet."""
    if snippet not in result.output:
        cmd_str = " ".join(cmd) if cmd else ""
        raise AssertionError(
            f"Expected to find '{snippet}' in container output.\n"
            f"Got:\n{result.output}\n"
            f"Container command:\n{cmd_str}"
        )


def _assert_not_contains(result, snippet: str, cmd: list[str] = None) -> None:
    """Assert that the result output does not contain the given snippet."""
    if snippet in result.output:
        cmd_str = " ".join(cmd) if cmd else ""
        raise AssertionError(
            f"Expected NOT to find '{snippet}' in container output.\n"
            f"Got:\n{result.output}\n"
            f"Container command:\n{cmd_str}"
        )


def test_ports_available_normal_case(tmp_path: pathlib.Path) -> None:
    """Test ports available script with default ports (should pass without warnings).

    99. Ports Available Check: Tests that the script runs without warnings
    when ports 20211 and 20212 are available and not conflicting.
    Expected: No warnings about port conflicts or ports in use.

    Check script: 99-ports-available.sh
    """
    paths = _setup_mount_tree(tmp_path, "ports_normal")
    volumes = _build_volume_args(paths)
    result = _run_container("ports-normal", volumes, user="20211:20211", env={"PORT": "99991", "GRAPHQL_PORT": "99992"})

    # Should not contain any port warnings
    _assert_not_contains(result, "Configuration Warning: Both ports are set to")
    _assert_not_contains(result, "Port Warning: Application port")
    _assert_not_contains(result, "Port Warning: GraphQL API port")
    assert result.returncode == 0


def test_ports_conflict_same_number(tmp_path: pathlib.Path) -> None:
    """Test ports available script when both ports are set to the same number.

    99. Ports Available Check: Tests warning when PORT and GRAPHQL_PORT
    are configured to the same value.
    Expected: Warning about port conflict.

    Check script: 99-ports-available.sh
    """
    paths = _setup_mount_tree(tmp_path, "ports_conflict")
    volumes = _build_volume_args(paths)
    result = _run_container(
        "ports-conflict",
        volumes,
        user="20211:20211",
        env={"PORT": "20211", "GRAPHQL_PORT": "20211"}
    )

    _assert_contains(result, "Configuration Warning: Both ports are set to 20211")
    _assert_contains(result, "The Application port ($PORT) and the GraphQL API port")
    _assert_contains(result, "are configured to use the")
    _assert_contains(result, "same port. This will cause a conflict.")
    assert result.returncode == 0


def test_ports_in_use_warning(dummy_container, tmp_path: pathlib.Path) -> None:
    """Test ports available script when ports are already in use.

    99. Ports Available Check: Tests warning when configured ports
    are already bound by another process.
    Expected: Warning about ports being in use.

    Check script: 99-ports-available.sh
    """
    paths = _setup_mount_tree(tmp_path, "ports_in_use")
    volumes = _build_volume_args(paths)
    result = _run_container(
        "ports-in-use",
        volumes,
        user="20211:20211",
        env={"PORT": "20211", "GRAPHQL_PORT": "20212"}
    )

    _assert_contains(result, "Port Warning: Application port 20211 is already in use")
    _assert_contains(result, "Port Warning: GraphQL API port 20212 is already in use")
    assert result.returncode == 0
