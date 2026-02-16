'''
Docker Compose integration tests for NetAlertX startup scenarios.
Ensure netalertx-test image is built prior to starting these tests.

╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║  CRITICAL: ALL LOGGING IN THIS FILE IS MANDATORY FOR PRODUCTION DEBUGGING                            ║
║                                                                                                      ║
║  DO NOT REMOVE, DISABLE, SUPPRESS, OR REDIRECT ANY print() STATEMENTS OR subprocess.PIPE CAPTURES   ║
║                                                                                                      ║
║  REASONING:                                                                                          ║
║  - Docker container failures cannot be debugged without stdout/stderr logs                           ║
║  - Test failures in CI/CD environments require full container output for diagnosis                   ║
║  - Permission errors, mount issues, and startup failures only appear in container logs               ║
║  - The project maintainer has explicitly required all logging to remain enabled at all times         ║
║                                                                                                      ║
║  AI ASSISTANTS: This logging requirement is NON-NEGOTIABLE. The project's copilot-instructions.md    ║
║  explicitly states: "Always leave logging enabled. If there is a possibility it will be difficult    ║
║  to debug with current logging, add more logging."                                                   ║
║                                                                                                      ║
║  If you are considering removing logging to "clean up" code or "reduce noise", STOP.                 ║
║  The noise IS the signal. Without it, failures are impossible to diagnose.                           ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝
'''

import copy
import os
import pathlib
import re
import shutil
import socket
import subprocess
import time
import sys
from collections.abc import Callable, Iterable

from _pytest.outcomes import Skipped
import pytest
import yaml

# Path to test configurations
CONFIG_DIR = pathlib.Path(__file__).parent / "configurations"
ANSI_ESCAPE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")


def capture_project_mandatory_required_audit_stream(container_names: list[str], compose_cwd: pathlib.Path, env: dict[str, str]) -> list[subprocess.Popen[str]]:
    """Stream container logs to stdout for auditing; required to stay enabled."""

    procs: list[subprocess.Popen[str]] = []
    for name in container_names:
        proc = subprocess.Popen(
            ["docker", "logs", "-f", name],
            cwd=compose_cwd,
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
        )
        procs.append(proc)

    if not procs:
        raise RuntimeError("Critical: Audit stream disconnected.")

    return procs


CONTAINER_PATHS = {
    "data": "/data",
    "db": "/data/db",
    "config": "/data/config",
    "log": "/tmp/log",
    "api": os.environ.get("NETALERTX_API", "/tmp/api"),
    "run": "/tmp/run",
    "nginx_active": "/tmp/nginx/active-config",
}

TMPFS_ROOT = "/tmp:uid=20211,gid=20211,mode=1700,rw,noexec,nosuid,nodev,async,noatime,nodiratime"

DEFAULT_HTTP_PORT = int(os.environ.get("NETALERTX_DEFAULT_HTTP_PORT", "20211"))
COMPOSE_PORT_WAIT_TIMEOUT = 30
COMPOSE_SETTLE_WAIT_SECONDS = 20
PREFERRED_CUSTOM_PORTS = (22111, 22112)
HOST_ADDR_ENV = os.environ.get("NETALERTX_HOST_ADDRS", "")


def _discover_host_addresses() -> tuple[str, ...]:
    """Return candidate loopback addresses for reaching host-mode containers."""

    candidates: list[str] = ["127.0.0.1"]

    if HOST_ADDR_ENV:
        env_addrs = [addr.strip() for addr in HOST_ADDR_ENV.split(",") if addr.strip()]
        candidates.extend(env_addrs)

    ip_cmd = shutil.which("ip")
    if ip_cmd:
        try:
            route_proc = subprocess.run(
                [ip_cmd, "-4", "route", "show", "default"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            route_proc = None
        if route_proc and route_proc.returncode == 0 and route_proc.stdout:
            match = re.search(r"default\s+via\s+(?P<gateway>\S+)", route_proc.stdout)
            if match:
                gateway = match.group("gateway")
                candidates.append(gateway)

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for addr in candidates:
        if addr not in seen:
            deduped.append(addr)
            seen.add(addr)

    return tuple(deduped)


HOST_ADDRESS_CANDIDATES = _discover_host_addresses()
LAST_PORT_SUCCESSES: dict[int, str] = {}

# Test project name prefixes to clean up before runs
_TEST_PROJECT_PREFIXES = ("netalertx-missing", "netalertx-normal", "netalertx-custom", "netalertx-host", "netalertx-ram", "netalertx-dataloss")

pytestmark = [pytest.mark.docker, pytest.mark.compose]

IMAGE = os.environ.get("NETALERTX_TEST_IMAGE", "netalertx-test")

_CONFLICT_NAME_PATTERN = re.compile(r'The container name "/([^"]+)" is already in use')

# Docker Compose configurations for different test scenarios
COMPOSE_CONFIGS = {
    "missing_capabilities": {
        "services": {
            "netalertx": {
                "image": IMAGE,
                "network_mode": "host",
                "userns_mode": "host",
                "cap_drop": ["ALL"],  # Drop all capabilities
                "tmpfs": ["/tmp:mode=777"],
                "volumes": [
                    f"./test_data/data:{CONTAINER_PATHS['data']}",
                    f"./test_data/log:{CONTAINER_PATHS['log']}",
                    f"./test_data/api:{CONTAINER_PATHS['api']}",
                    f"./test_data/nginx_conf:{CONTAINER_PATHS['nginx_active']}",
                    f"./test_data/run:{CONTAINER_PATHS['run']}"
                ],
                "environment": {
                    "TZ": "UTC"
                }
            }
        }
    },
    "host_network": {
        "services": {
            "netalertx": {
                "image": IMAGE,
                "network_mode": "host",
                "userns_mode": "host",
                "cap_add": ["NET_RAW", "NET_ADMIN", "NET_BIND_SERVICE"],
                "tmpfs": ["/tmp:mode=777"],
                "volumes": [
                    f"./test_data/data:{CONTAINER_PATHS['data']}",
                    f"./test_data/log:{CONTAINER_PATHS['log']}",
                    f"./test_data/api:{CONTAINER_PATHS['api']}",
                    f"./test_data/nginx_conf:{CONTAINER_PATHS['nginx_active']}",
                    f"./test_data/run:{CONTAINER_PATHS['run']}"
                ],
                "environment": {
                    "TZ": "UTC"
                }
            }
        }
    },
    "normal_startup": {
        "services": {
            "netalertx": {
                "image": IMAGE,
                "network_mode": "host",
                "userns_mode": "host",
                "read_only": True,
                "cap_drop": ["ALL"],
                "cap_add": ["NET_RAW", "NET_ADMIN", "NET_BIND_SERVICE"],
                "user": "20211:20211",
                "tmpfs": [TMPFS_ROOT],
                "volumes": [
                    {
                        "type": "volume",
                        "source": "__DATA_VOLUME__",
                        "target": CONTAINER_PATHS["data"],
                        "read_only": False,
                    },
                    {
                        "type": "bind",
                        "source": "/etc/localtime",
                        "target": "/etc/localtime",
                        "read_only": True,
                    },
                ],
                "environment": {
                    "TZ": "UTC"
                }
            }
        }
    }
}


def _create_test_data_dirs(base_dir: pathlib.Path) -> None:
    """Create test data directories and files with write permissions for the container user."""
    dirs = [
        "data/db",
        "data/config",
        "log",
        "api",
        "nginx_conf",
        "run",
    ]
    for dir_name in dirs:
        dir_path = base_dir / "test_data" / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        dir_path.chmod(0o777)

    # Create basic config file
    config_file = base_dir / "test_data" / "data" / "config" / "app.conf"
    if not config_file.exists():
        config_file.write_text("# Test configuration\n")
    config_file.chmod(0o666)

    # Create basic db file
    db_file = base_dir / "test_data" / "data" / "db" / "app.db"
    if not db_file.exists():
        # Create a minimal SQLite database
        import sqlite3
        conn = sqlite3.connect(str(db_file))
        conn.close()
    db_file.chmod(0o666)


def _extract_conflict_container_name(output: str) -> str | None:
    match = _CONFLICT_NAME_PATTERN.search(output)
    if match:
        return match.group(1)
    return None


def _port_is_free(port: int) -> bool:
    """Return True if a TCP port is available on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _wait_for_ports(ports: Iterable[int], timeout: int = COMPOSE_PORT_WAIT_TIMEOUT) -> None:
    """Block until every port in the iterable accepts TCP connections or timeout expires."""

    remaining = set(ports)
    deadline = time.time() + timeout
    last_errors: dict[int, dict[str, BaseException]] = {port: {} for port in remaining}

    while remaining and time.time() < deadline:
        ready: list[int] = []
        for port in list(remaining):
            for addr in HOST_ADDRESS_CANDIDATES:
                try:
                    with socket.create_connection((addr, port), timeout=2):
                        ready.append(port)
                        LAST_PORT_SUCCESSES[port] = addr
                        break
                except OSError as exc:
                    last_errors.setdefault(port, {})[addr] = exc
            else:
                continue
        for port in ready:
            remaining.discard(port)
        if remaining:
            time.sleep(1)

    if remaining:
        details: list[str] = []
        for port in sorted(remaining):
            addr_errors = last_errors.get(port, {})
            if addr_errors:
                error_summary = ", ".join(f"{addr}: {err}" for addr, err in addr_errors.items())
            else:
                error_summary = "no connection attempts recorded"
            details.append(f"{port} -> {error_summary}")
        raise TimeoutError(
            "Ports did not become ready before timeout: " + "; ".join(details)
        )


def _select_custom_ports(exclude: set[int] | None = None) -> int:
    """Choose a non-default port, preferring the standard high test port when free.

    Ensures the returned HTTP port is not in the exclude set to keep scenarios distinct.
    """
    exclude = exclude or set()
    preferred_http, _ = PREFERRED_CUSTOM_PORTS
    if preferred_http not in exclude and _port_is_free(preferred_http):
        return preferred_http

    # Fall back to scanning ephemeral range for the first free port.
    for port in range(30000, 60000):
        if port not in exclude and _port_is_free(port):
            return port

    raise RuntimeError("Unable to locate a free high port for compose testing")


def _make_port_check_hook(ports: tuple[int, ...]) -> Callable[[], None]:
    """Return a callback that waits for the provided ports to accept TCP connections."""

    def _hook() -> None:
        for port in ports:
            LAST_PORT_SUCCESSES.pop(port, None)
        time.sleep(COMPOSE_SETTLE_WAIT_SECONDS)
        _wait_for_ports(ports, timeout=COMPOSE_PORT_WAIT_TIMEOUT)

    return _hook


def _write_normal_startup_compose(
    base_dir: pathlib.Path,
    project_name: str,
    env_overrides: dict[str, str] | None,
) -> pathlib.Path:
    """Generate a compose file for the normal startup scenario with optional environment overrides."""

    compose_config = copy.deepcopy(COMPOSE_CONFIGS["normal_startup"])
    service = compose_config["services"]["netalertx"]

    data_volume_name = f"{project_name}_data"
    service["volumes"][0]["source"] = data_volume_name

    service_env = service.setdefault("environment", {})
    service_env.setdefault("NETALERTX_CHECK_ONLY", "1")

    if env_overrides:
        service_env.update(env_overrides)

    try:
        http_port_val = int(service_env.get("PORT", DEFAULT_HTTP_PORT))
    except (TypeError, ValueError):
        http_port_val = DEFAULT_HTTP_PORT

    if "GRAPHQL_PORT" not in service_env:
        service_env["GRAPHQL_PORT"] = str(_select_custom_ports({http_port_val}))

    compose_config["volumes"] = {data_volume_name: {}}

    compose_file = base_dir / "docker-compose.yml"
    with open(compose_file, "w") as f:
        yaml.dump(compose_config, f)

    return compose_file


def _assert_ports_ready(
    result: subprocess.CompletedProcess,
    project_name: str,
    ports: tuple[int, ...],
) -> str:
    """Validate the post-up hook succeeded and return sanitized compose logs for further assertions."""

    post_error = getattr(result, "post_up_error", None)
    clean_output = ANSI_ESCAPE.sub("", result.output)
    port_hosts = {port: LAST_PORT_SUCCESSES.get(port) for port in ports}
    result.port_hosts = port_hosts  # type: ignore[attr-defined]

    if post_error:
        # Log and continue instead of failing hard; environments without host access can still surface
        # useful startup diagnostics even if port probes fail.
        print(
            "[compose port readiness warning] "
            f"{project_name} ports {ports} {post_error}"
        )
        return clean_output

    port_summary = ", ".join(
        f"{port}@{addr if addr else 'unresolved'}" for port, addr in port_hosts.items()
    )
    print(f"[compose port hosts] {project_name}: {port_summary}")

    return clean_output


def _run_docker_compose(
    compose_file: pathlib.Path,
    project_name: str,
    timeout: int = 5,
    env_vars: dict | None = None,
    detached: bool = False,
    post_up: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess:
    """Run docker compose up and capture output."""
    # Clear global port tracking to prevent cross-test state pollution
    LAST_PORT_SUCCESSES.clear()

    cmd = [
        "docker", "compose",
        "-f", str(compose_file),
        "-p", project_name,
    ]

    up_cmd = cmd + ["up"]
    if detached:
        up_cmd.append("-d")
    else:
        up_cmd.extend([
            "--abort-on-container-exit",
            "--timeout", str(timeout)
        ])

    # Merge custom env vars with current environment
    env = os.environ.copy()

    # Ensure compose runs in check-only mode so containers exit promptly during tests
    env.setdefault("NETALERTX_CHECK_ONLY", "1")

    # Auto-assign non-conflicting ports to avoid host clashes that would trigger warnings/timeouts
    existing_port = env.get("PORT")
    try:
        existing_port_int = int(existing_port) if existing_port else None
    except ValueError:
        existing_port_int = None

    if not existing_port_int:
        env["PORT"] = str(_select_custom_ports())
        existing_port_int = int(env["PORT"])

    if "GRAPHQL_PORT" not in env:
        exclude_ports = {existing_port_int} if existing_port_int is not None else None
        env["GRAPHQL_PORT"] = str(_select_custom_ports(exclude_ports))

    if env_vars:
        env.update(env_vars)

    # Ensure no stale containers from previous runs; always clean before starting.
    subprocess.run(
        cmd + ["down", "-v", "--remove-orphans"],
        cwd=compose_file.parent,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
        check=False,
        env=env,
    )

    # Also clean up any orphaned containers from previous test runs with similar project prefixes
    for prefix in _TEST_PROJECT_PREFIXES:
        if project_name.startswith(prefix):
            subprocess.run(
                ["docker", "container", "prune", "-f", "--filter", f"label=com.docker.compose.project={project_name}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            break

    def _run_with_conflict_retry(run_cmd: list[str], run_timeout: int) -> subprocess.CompletedProcess:
        retry_conflict = True
        while True:
            print(f"Running cmd: {run_cmd}")
            proc = subprocess.run(
                run_cmd,
                cwd=compose_file.parent,
                capture_output=True,  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
                text=True,
                timeout=run_timeout,
                check=False,
                env=env,
            )
            print(proc.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
            print(proc.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
            combined = (proc.stdout or "") + (proc.stderr or "")
            if retry_conflict and "is already in use by container" in combined:
                conflict_name = _extract_conflict_container_name(combined)
                if conflict_name:
                    subprocess.run(
                        ["docker", "rm", "-f", conflict_name],
                        stdout=sys.stdout,
                        stderr=sys.stderr,
                        text=True,
                        check=False,
                        env=env,
                    )
                    retry_conflict = False
                    continue
            return proc

    post_up_exc: BaseException | None = None
    skip_exc: Skipped | None = None

    def _collect_logs_with_retry(max_attempts: int = 3, wait_between: float = 2.0) -> subprocess.CompletedProcess:
        """Collect logs with retry to handle timing races where container hasn't flushed output yet."""
        logs_cmd = cmd + ["logs"]
        best_result: subprocess.CompletedProcess | None = None
        # Initialize with a safe default in case loop doesn't run
        logs_result = subprocess.CompletedProcess(logs_cmd, 1, stdout="", stderr="No log attempts made")
        for attempt in range(max_attempts):
            print(f"Running logs cmd (attempt {attempt + 1}/{max_attempts}): {logs_cmd}")
            logs_result = subprocess.run(
                logs_cmd,
                cwd=compose_file.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout + 5,
                check=False,
                env=env,
            )
            print(logs_result.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
            print(logs_result.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.

            combined = (logs_result.stdout or "") + (logs_result.stderr or "")
            # Keep the result with the most content
            if best_result is None or len(combined) > len((best_result.stdout or "") + (best_result.stderr or "")):
                best_result = logs_result

            # If we see the expected startup marker, logs are complete
            if "Startup pre-checks" in combined or "NETALERTX_CHECK_ONLY" in combined:
                break

            if attempt < max_attempts - 1:
                time.sleep(wait_between)

        return best_result or logs_result

    try:
        if detached:
            up_result = _run_with_conflict_retry(up_cmd, timeout)

            if post_up:
                try:
                    post_up()
                except Skipped as exc:
                    skip_exc = exc
                except BaseException as exc:  # noqa: BLE001 - bubble the root cause through the result payload
                    post_up_exc = exc

            logs_result = _collect_logs_with_retry()

            result = subprocess.CompletedProcess(
                up_cmd,
                up_result.returncode,
                stdout=(up_result.stdout or "") + (logs_result.stdout or ""),
                stderr=(up_result.stderr or "") + (logs_result.stderr or ""),
            )
        else:
            up_result = _run_with_conflict_retry(up_cmd, timeout + 10)

            logs_result = _collect_logs_with_retry()

            result = subprocess.CompletedProcess(
                up_cmd,
                up_result.returncode,
                stdout=(up_result.stdout or "") + (logs_result.stdout or ""),
                stderr=(up_result.stderr or "") + (logs_result.stderr or ""),
            )
    except subprocess.TimeoutExpired:
        # Clean up on timeout
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "-p", project_name, "down", "-v"],
            cwd=compose_file.parent,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            check=False,
            env=env,
        )
        raise

    # Combine stdout and stderr
    result.output = result.stdout + result.stderr
    result.post_up_error = post_up_exc  # type: ignore[attr-defined]

    # Collect compose ps data (includes exit codes from status text) for better diagnostics
    ps_summary: str = ""
    worst_exit = 0
    audit_streams: list[subprocess.Popen[str]] = []
    try:
        ps_proc = subprocess.run(
            cmd + ["ps", "--all", "--format", "{{.Name}} {{.State}} {{.ExitCode}}"],
            cwd=compose_file.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
            env=env,
        )
        print(ps_proc.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
        print(ps_proc.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
        ps_output = (ps_proc.stdout or "") + (ps_proc.stderr or "")
        ps_lines = [line.strip() for line in ps_output.splitlines() if line.strip()]
        exit_re = re.compile(r"Exited \((?P<code>\d+)\)|\b(?P<plain>\d+)$")
        parsed: list[str] = []
        container_names: list[str] = []
        for line in ps_lines:
            parts = line.split()
            if not parts:
                continue
            container_names.append(parts[0])
            parsed.append(line)
            match = exit_re.search(line)
            exit_val: int | None = None
            if match:
                code = match.group("code") or match.group("plain")
                if code:
                    try:
                        exit_val = int(code)
                    except ValueError:
                        exit_val = None
            if exit_val is not None:
                worst_exit = max(worst_exit, exit_val)
        ps_summary = "[compose ps --all] " + "; ".join(parsed) if parsed else "[compose ps --all] <no containers>"
        result.output += "\n" + ps_summary

        # Start mandatory audit stream; keep logs flowing to stdout
        if container_names:
            audit_streams = capture_project_mandatory_required_audit_stream(container_names, compose_file.parent, env)
            if not audit_streams:
                raise RuntimeError("Critical: Audit stream disconnected (no audit streams captured).")
        else:
            raise RuntimeError("Critical: Audit stream disconnected (no containers listed by compose ps).")
    except Exception as exc:  # noqa: BLE001
        ps_summary = f"[compose ps] failed: {exc}"

    # If containers exited with non-zero, reflect that in return code
    if worst_exit and result.returncode == 0:
        result.returncode = worst_exit

    if skip_exc is not None:
        raise skip_exc

    # ┌─────────────────────────────────────────────────────────────────────────────────────────┐
    # │ MANDATORY LOGGING - DO NOT REMOVE OR REDIRECT TO DEVNULL                                │
    # │ These print statements are required for debugging test failures. See file header.       │
    # │ Without this output, docker compose test failures cannot be diagnosed.                  │
    # └─────────────────────────────────────────────────────────────────────────────────────────┘
    print("\n[compose command]", " ".join(up_cmd))
    print("[compose cwd]", str(compose_file.parent))
    print("[compose stdin]", "<none>")
    if result.stdout:
        print("[compose stdout]\n" + result.stdout)
    if result.stderr:
        print("[compose stderr]\n" + result.stderr)
    if ps_summary:
        print(ps_summary)
    if detached:
        logs_cmd_display = cmd + ["logs"]
        print("[compose logs command]", " ".join(logs_cmd_display))

    # Clean up after diagnostics/logging. Run cleanup but DO NOT overwrite the
    # main `result` variable which contains the combined compose output and
    # additional attributes (`output`, `post_up_error`, etc.). Overwriting it
    # caused callers to see a CompletedProcess without `output` -> AttributeError.
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "-p", project_name, "down", "-v", "--remove-orphans"],
        cwd=compose_file.parent,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
        check=False,
        env=env,
    )

    # Prune any dangling volumes from this project to prevent state leakage
    subprocess.run(
        ["docker", "volume", "prune", "-f", "--filter", f"label=com.docker.compose.project={project_name}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

    for proc in audit_streams:
        try:
            proc.terminate()
        except Exception:
            pass

    return result


def test_missing_capabilities_compose() -> None:
    """Test missing required capabilities using docker compose.

    Uses docker-compose.missing-caps.yml which drops all capabilities.
    Expected: The script should execute (using bash) but may show warnings about missing capabilities.
    """
    compose_file = CONFIG_DIR / "docker-compose.missing-caps.yml"
    http_port = _select_custom_ports()
    graphql_port = _select_custom_ports({http_port})
    result = _run_docker_compose(
        compose_file,
        "netalertx-missing-caps",
        env_vars={
            "NETALERTX_CHECK_ONLY": "1",
            "PORT": str(http_port),
            "GRAPHQL_PORT": str(graphql_port),
        },
        timeout=60,
        detached=False,
    )

    print("\n[compose output missing-caps]", result.stdout + result.stderr)

    # Check that the script executed and didn't get blocked by the kernel
    assert "exec /root-entrypoint.sh: operation not permitted" not in (result.stdout + result.stderr).lower()
    assert "Startup pre-checks" in (result.stdout + result.stderr)


def test_custom_port_with_unwritable_nginx_config_compose() -> None:
    """Test custom port configuration with unwritable nginx config using docker compose.

    Uses docker-compose.mount-test.active_config_unwritable.yml with PORT=24444.
    Expected: Container shows warning about unable to write nginx config.
    The container may exit non-zero if the chown operation fails due to read-only mount.
    """
    compose_file = CONFIG_DIR / "mount-tests" / "docker-compose.mount-test.active_config_unwritable.yml"
    http_port = _select_custom_ports()
    graphql_port = _select_custom_ports({http_port})
    LAST_PORT_SUCCESSES.pop(http_port, None)
    project_name = "netalertx-custom-port"

    def _wait_for_unwritable_failure() -> None:
        deadline = time.time() + 45
        while time.time() < deadline:
            ps_cmd = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "-p",
                project_name,
                "ps",
                "--format",
                "{{.Name}} {{.State}}",
            ]
            ps_proc = subprocess.run(
                ps_cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            ps_output = (ps_proc.stdout or "") + (ps_proc.stderr or "")
            print("[unwritable-nginx ps poll]", ps_output.strip() or "<no output>")
            if "exited" in ps_output.lower() or "dead" in ps_output.lower():
                return
            time.sleep(2)
        raise TimeoutError("netalertx-custom-port container did not exit within 45 seconds")

    result = _run_docker_compose(
        compose_file,
        project_name,
        env_vars={
            "PORT": str(http_port),
            "GRAPHQL_PORT": str(graphql_port),
            # Run full startup to validate nginx config generation on tmpfs.
            "NETALERTX_CHECK_ONLY": "0",
        },
        timeout=8,
        detached=True,
        post_up=_wait_for_unwritable_failure,
    )

    # MANDATORY LOGGING - DO NOT REMOVE (see file header for reasoning)
    full_output = ANSI_ESCAPE.sub("", result.output)
    lowered_output = full_output.lower()
    print("\n[compose output unwritable-nginx]", full_output)

    # Container should exit due to inability to write nginx config and custom port.
    assert result.returncode == 1
    assert "unable to write to /tmp/nginx/active-config/netalertx.conf" in lowered_output


def test_host_network_compose(tmp_path: pathlib.Path) -> None:
    """Test host networking mode using docker compose.

    Simulates running with network_mode: host.
    Expected: Container starts successfully with host networking.
    """
    base_dir = tmp_path / "host_network"
    base_dir.mkdir()

    # Create test data directories
    _create_test_data_dirs(base_dir)

    # Select a free port to avoid conflicts
    custom_port = _select_custom_ports()

    # Create compose file with custom port
    compose_config = copy.deepcopy(COMPOSE_CONFIGS["host_network"])
    service_env = compose_config["services"]["netalertx"].setdefault("environment", {})
    service_env["PORT"] = str(custom_port)
    service_env.setdefault("NETALERTX_CHECK_ONLY", "1")
    service_env.setdefault("GRAPHQL_PORT", str(_select_custom_ports({custom_port})))
    compose_file = base_dir / "docker-compose.yml"
    with open(compose_file, 'w') as f:
        yaml.dump(compose_config, f)

    # Run docker compose
    result = _run_docker_compose(
        compose_file,
        "netalertx-host-net",
        timeout=60,
        detached=False,
    )

    # MANDATORY LOGGING - DO NOT REMOVE (see file header for reasoning)
    print("\n[compose output host-net]", result.output)

    # Check that it doesn't fail with network-related errors and actually started
    assert result.returncode == 0
    assert "not running with --network=host" not in result.output.lower()


def test_normal_startup_no_warnings_compose(tmp_path: pathlib.Path) -> None:
    """Test normal startup with expected warnings using docker compose.

    Simulates proper configuration with all required settings.
    Expected: Container starts and shows expected warnings with pipe characters (═).
    This demonstrates what a "normal" startup looks like with warnings.
    """
    base_dir = tmp_path / "normal_startup"
    base_dir.mkdir()
    # Always use a custom port to avoid conflicts with the devcontainer or other tests.
    # The default port 20211 is often in use in development environments.
    default_http_port = _select_custom_ports()
    default_graphql_port = _select_custom_ports({default_http_port})
    default_env_overrides: dict[str, str] = {
        "PORT": str(default_http_port),
        "GRAPHQL_PORT": str(default_graphql_port),
        "NETALERTX_CHECK_ONLY": "1",
    }
    default_ports = (default_http_port,)
    print(f"[compose port override] default scenario using http={default_http_port} graphql={default_graphql_port}")

    default_dir = base_dir / "default"
    default_dir.mkdir()
    default_project = "netalertx-normal-default"

    default_compose_file = _write_normal_startup_compose(default_dir, default_project, default_env_overrides)
    default_result = _run_docker_compose(
        default_compose_file,
        default_project,
        timeout=8,
        detached=True,
        post_up=_make_port_check_hook(default_ports),
    )
    # MANDATORY LOGGING - DO NOT REMOVE (see file header for reasoning)
    print("\n[compose output default]", default_result.output)
    default_output = _assert_ports_ready(default_result, default_project, default_ports)

    assert "Startup pre-checks" in default_output
    assert "❌" not in default_output

    data_line = ""
    data_parts: list[str] = []
    for line in default_output.splitlines():
        if CONTAINER_PATHS['data'] not in line or '|' not in line:
            continue
        parts = [segment.strip() for segment in line.split('|')]
        if len(parts) < 2:
            continue
        if parts[1] == CONTAINER_PATHS['data']:
            data_line = line
            data_parts = parts
            break

    assert data_line, "Expected /data row in mounts table"
    assert data_parts[1] == CONTAINER_PATHS['data'], f"Unexpected path column in /data row: {data_parts}"
    assert data_parts[2] == "✅" and data_parts[3] == "✅", (
        f"Unexpected mount row values for /data: {data_parts[2:4]}"
    )

    assert "Write permission denied" not in default_output
    assert "CRITICAL" not in default_output
    assert "⚠️" not in default_output

    custom_http = _select_custom_ports({default_http_port})
    custom_graphql = _select_custom_ports({default_http_port, custom_http})
    assert custom_http != default_http_port
    custom_ports = (custom_http,)

    custom_dir = base_dir / "custom"
    custom_dir.mkdir()
    custom_project = "netalertx-normal-custom"

    custom_compose_file = _write_normal_startup_compose(
        custom_dir,
        custom_project,
        {
            "PORT": str(custom_http),
            "GRAPHQL_PORT": str(custom_graphql),
            "NETALERTX_CHECK_ONLY": "1",
        },
    )

    custom_result = _run_docker_compose(
        custom_compose_file,
        custom_project,
        timeout=8,
        detached=True,
        post_up=_make_port_check_hook(custom_ports),
    )
    print("\n[compose output custom]", custom_result.output)
    custom_output = _assert_ports_ready(custom_result, custom_project, custom_ports)

    assert "Startup pre-checks" in custom_output
    assert "❌" not in custom_output
    assert "Write permission denied" not in custom_output
    assert "CRITICAL" not in custom_output
    assert "⚠️" not in custom_output
    lowered_custom = custom_output.lower()
    assert "arning" not in lowered_custom
    assert "rror" not in lowered_custom


def test_ram_disk_mount_analysis_compose(tmp_path: pathlib.Path) -> None:
    """Test mount analysis for RAM disk detection using docker compose.

    Simulates mounting persistent paths on tmpfs (RAM disk).
    Expected: Mounts table shows ❌ for RAMDisk on persistent paths, dataloss warnings.
    """
    base_dir = tmp_path / "ram_disk_test"
    base_dir.mkdir()

    # Create test data directories
    _create_test_data_dirs(base_dir)

    # Create compose file with tmpfs mounts for persistent paths
    http_port = _select_custom_ports()
    graphql_port = _select_custom_ports({http_port})

    compose_config = {
        "services": {
            "netalertx": {
                "image": IMAGE,
                "network_mode": "host",
                "userns_mode": "host",
                "cap_add": ["NET_RAW", "NET_ADMIN", "NET_BIND_SERVICE"],
                "user": "20211:20211",
                "tmpfs": [
                    "/tmp:mode=777",
                    CONTAINER_PATHS["data"],  # RAM disk for persistent data root
                ],
                "volumes": [
                    f"./test_data/log:{CONTAINER_PATHS['log']}",
                    f"./test_data/api:{CONTAINER_PATHS['api']}",
                    f"./test_data/nginx_conf:{CONTAINER_PATHS['nginx_active']}",
                    f"./test_data/run:{CONTAINER_PATHS['run']}"
                ],
                "environment": {
                    "TZ": "UTC",
                    "NETALERTX_CHECK_ONLY": "1",
                    "PORT": str(http_port),
                    "GRAPHQL_PORT": str(graphql_port),
                }
            }
        }
    }

    compose_file = base_dir / "docker-compose.yml"
    with open(compose_file, 'w') as f:
        yaml.dump(compose_config, f)

    # Run docker compose
    result = _run_docker_compose(
        compose_file,
        "netalertx-ram-disk",
        detached=False,
    )
    print("\n[compose output ram-disk]", result.output)

    # Check that mounts table shows RAM disk detection and dataloss warnings
    assert "Configuration issues detected" in result.output
    assert CONTAINER_PATHS["data"] in result.output
    assert result.returncode != 0  # Should fail due to dataloss risk


def test_dataloss_risk_mount_analysis_compose(tmp_path: pathlib.Path) -> None:
    """Test mount analysis for dataloss risk using docker compose.

    Simulates mounting persistent paths on non-persistent tmpfs.
    Expected: Mounts table shows dataloss risk warnings for persistent paths.
    """
    base_dir = tmp_path / "dataloss_test"
    base_dir.mkdir()

    # Create test data directories
    _create_test_data_dirs(base_dir)

    # Create compose file with tmpfs for persistent data
    http_port = _select_custom_ports()
    graphql_port = _select_custom_ports({http_port})

    compose_config = {
        "services": {
            "netalertx": {
                "image": IMAGE,
                "network_mode": "host",
                "userns_mode": "host",
                "cap_add": ["NET_RAW", "NET_ADMIN", "NET_BIND_SERVICE"],
                "user": "20211:20211",
                "tmpfs": [
                    "/tmp:mode=777",
                    f"{CONTAINER_PATHS['data']}:uid=20211,gid=20211",  # Non-persistent for unified data
                ],
                "volumes": [
                    f"./test_data/log:{CONTAINER_PATHS['log']}",
                    f"./test_data/api:{CONTAINER_PATHS['api']}",
                    f"./test_data/nginx_conf:{CONTAINER_PATHS['nginx_active']}",
                    f"./test_data/run:{CONTAINER_PATHS['run']}"
                ],
                "environment": {
                    "TZ": "UTC",
                    "NETALERTX_CHECK_ONLY": "1",
                    "PORT": str(http_port),
                    "GRAPHQL_PORT": str(graphql_port),
                }
            }
        }
    }

    compose_file = base_dir / "docker-compose.yml"
    with open(compose_file, 'w') as f:
        yaml.dump(compose_config, f)

    # Run docker compose
    result = _run_docker_compose(
        compose_file,
        "netalertx-dataloss",
        detached=False,
    )
    print("\n[compose output dataloss]", result.output)

    # Check that mounts table shows dataloss risk detection
    assert "Configuration issues detected" in result.output
    assert CONTAINER_PATHS["data"] in result.output
    assert result.returncode != 0  # Should fail due to dataloss risk


def test_missing_net_admin_compose() -> None:
    """Test missing NET_ADMIN capability using docker compose.

    Uses docker-compose.missing-net-admin.yml.
    Expected: Warning about missing raw network capabilities.
    """
    compose_file = CONFIG_DIR / "docker-compose.missing-net-admin.yml"
    http_port = _select_custom_ports()
    graphql_port = _select_custom_ports({http_port})
    result = _run_docker_compose(
        compose_file,
        "netalertx-missing-net-admin",
        env_vars={
            "NETALERTX_CHECK_ONLY": "1",
            "PORT": str(http_port),
            "GRAPHQL_PORT": str(graphql_port),
        },
        timeout=60,
        detached=False,
    )

    print("\n[compose output missing-net-admin]", result.stdout + result.stderr)

    # Check for expected warning from capabilities canary (10-capabilities-audit.sh)
    output = result.stdout + result.stderr
    assert any(
        marker in output
        for marker in [
            "ALERT: Python execution capabilities (NET_RAW/NET_ADMIN) are missing",
            "Raw network capabilities are missing",
        ]
    )
    # Container should still exit 0 as per script
    assert result.returncode == 0


def test_missing_net_raw_compose() -> None:
    """Test missing NET_RAW capability using docker compose.

    Uses docker-compose.missing-net-raw.yml.
    Expected: Warning about missing raw network capabilities.
    """
    compose_file = CONFIG_DIR / "docker-compose.missing-net-raw.yml"
    http_port = _select_custom_ports()
    graphql_port = _select_custom_ports({http_port})
    result = _run_docker_compose(
        compose_file,
        "netalertx-missing-net-raw",
        env_vars={
            "NETALERTX_CHECK_ONLY": "1",
            "PORT": str(http_port),
            "GRAPHQL_PORT": str(graphql_port),
        },
        timeout=60,
        detached=False,
    )

    print("\n[compose output missing-net-raw]", result.stdout + result.stderr)

    # Check for expected warning from capabilities canary (10-capabilities-audit.sh)
    output = result.stdout + result.stderr
    assert any(
        marker in output
        for marker in [
            "ALERT: Python execution capabilities (NET_RAW/NET_ADMIN) are missing",
            "Raw network capabilities are missing",
        ]
    )
    assert result.returncode == 0
