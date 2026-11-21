'''
Tests for the NetAlertX entrypoint.sh script.

These tests verify the behavior of the entrypoint script under various conditions,
such as environment variable settings and check skipping.
'''

import json
import os
import subprocess
import uuid
import pytest
import shutil

IMAGE = "netalertx-test"


def _run_entrypoint(env: dict[str, str] | None = None, check_only: bool = True) -> subprocess.CompletedProcess[str]:
    """Run the entrypoint script in the test container with given environment."""
    name = f"netalertx-test-entrypoint-{uuid.uuid4().hex[:8]}".lower()
    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "host", "--userns", "host",
        "--tmpfs", "/tmp:mode=777",
        "--cap-add", "CHOWN",
        "--cap-add", "NET_RAW", "--cap-add", "NET_ADMIN", "--cap-add", "NET_BIND_SERVICE",
    ]
    if env:
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
    if check_only:
        cmd.extend(["-e", "NETALERTX_CHECK_ONLY=1"])
    cmd.extend([
        "--entrypoint", "/bin/sh", IMAGE, "-c",
        "sh /root-entrypoint.sh"
    ])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


@pytest.mark.docker
@pytest.mark.feature_complete
def test_skip_tests_env_var():
    # If SKIP_TESTS=1 is set, the entrypoint should skip all startup checks and print a
    # message indicating checks are skipped.
    # There should be no check output, and the script should exit successfully.
    result = _run_entrypoint(env={"SKIP_TESTS": "1"}, check_only=True)
    assert "Skipping startup checks as SKIP_TESTS is set." in result.stdout
    assert " --> " not in result.stdout  # No check outputs
    assert result.returncode == 0


@pytest.mark.docker
@pytest.mark.feature_complete
def test_app_conf_override_from_graphql_port():
    # If GRAPHQL_PORT is set and APP_CONF_OVERRIDE is not set, the entrypoint should set
    # APP_CONF_OVERRIDE to a JSON string containing the GRAPHQL_PORT value.
    # The script should exit successfully.
    result = _run_entrypoint(env={"GRAPHQL_PORT": "20212", "SKIP_TESTS": "1"}, check_only=True)
    assert 'Setting APP_CONF_OVERRIDE to' not in result.stdout
    assert 'APP_CONF_OVERRIDE detected' in result.stderr
    assert result.returncode == 0


@pytest.mark.docker
@pytest.mark.feature_complete
def test_app_conf_override_file_written_from_graphql_port(tmp_path):
    # Regression test: a bare GRAPHQL_PORT (no APP_CONF_OVERRIDE set) must result in
    # app_conf_override.json actually being written by entrypoint.d/35-apply-conf-override.sh,
    # which server/initialise.py reads to override the persisted GRAPHQL_PORT setting.
    # This requires the GRAPHQL_PORT->APP_CONF_OVERRIDE derivation in entrypoint.sh to run
    # BEFORE the entrypoint.d loop - it previously ran after, so on a fresh volume the
    # derived value never reached the file and the setting silently stayed at its default.
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    os.chmod(config_dir, 0o777)

    name = f"netalertx-test-entrypoint-{uuid.uuid4().hex[:8]}".lower()
    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "host", "--userns", "host",
        "--tmpfs", "/tmp:mode=777",
        "--cap-add", "CHOWN",
        "--cap-add", "NET_RAW", "--cap-add", "NET_ADMIN", "--cap-add", "NET_BIND_SERVICE",
        "-v", f"{config_dir}:/data/config",
        "-e", "GRAPHQL_PORT=20322",
        "-e", "NETALERTX_DEBUG=1",
        "-e", "NETALERTX_CHECK_ONLY=1",
        "--entrypoint", "/bin/sh", IMAGE, "-c",
        "sh /root-entrypoint.sh"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        override_file = config_dir / "app_conf_override.json"
        assert override_file.exists(), (
            "app_conf_override.json was never written by entrypoint.d/35-apply-conf-override.sh - "
            "the GRAPHQL_PORT->APP_CONF_OVERRIDE derivation in entrypoint.sh must run before the "
            f"entrypoint.d loop.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert json.loads(override_file.read_text()) == {"GRAPHQL_PORT": "20322"}
    finally:
        # The container writes app_conf_override.json as its own runtime UID, which the
        # host test process doesn't own - reopen permissions via a throwaway container so
        # pytest's tmp_path fixture teardown can actually delete config_dir afterwards.
        subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "chmod",
             "-v", f"{config_dir}:/data/config", IMAGE,
             "-R", "a+rwX", "/data/config"],
            capture_output=True, text=True, timeout=30,
        )


@pytest.mark.docker
@pytest.mark.feature_complete
def test_app_conf_override_not_overridden():
    # If both GRAPHQL_PORT and APP_CONF_OVERRIDE are set, the entrypoint should NOT override
    # APP_CONF_OVERRIDE or print a message about it.
    # The script should exit successfully.
    result = _run_entrypoint(env={
        "GRAPHQL_PORT": "20212",
        "APP_CONF_OVERRIDE": '{"OTHER":"value"}',
        "SKIP_TESTS": "1"
    }, check_only=True)
    assert 'Setting APP_CONF_OVERRIDE to' not in result.stdout
    assert result.returncode == 0


@pytest.mark.docker
@pytest.mark.feature_complete
def test_no_app_conf_override_when_no_graphql_port():
    # If GRAPHQL_PORT is not set, the entrypoint should NOT set or print APP_CONF_OVERRIDE.
    # The script should exit successfully.
    result = _run_entrypoint(env={"SKIP_TESTS": "1"}, check_only=True)
    assert 'Setting APP_CONF_OVERRIDE to' not in result.stdout
    assert result.returncode == 0


def test_skip_startup_checks_env_var():
    # If SKIP_STARTUP_CHECKS contains the human-readable name of a check (e.g. "mandatory folders"),
    # the entrypoint should skip that specific check. We check that the "Creating NetAlertX log directory."
    # message (from the mandatory folders check) is not printed when skipped.
    result = _run_entrypoint(env={"SKIP_STARTUP_CHECKS": "mandatory folders"}, check_only=True)
    assert "Creating NetAlertX log directory" not in result.stdout
    assert result.returncode == 0


def _backend_reachable(name: str) -> bool:
    """True if port 20212 inside the named container answers an HTTP request."""
    result = subprocess.run(
        ["docker", "exec", name, "curl", "-sf", "--max-time", "3", "http://127.0.0.1:20212/docs"],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


def _wait_until(predicate, timeout: float, interval: float = 2.0) -> bool:
    """Poll predicate() until it returns True or timeout elapses."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


@pytest.mark.docker
@pytest.mark.feature_complete
def test_backend_crash_without_marker_restarts_in_debug_mode():
    """Regression test: entrypoint.sh's debug-mode branch only restarted
    python3 when /tmp/backend_restart_pending was present (an intentional
    restart). An unexpected crash (no marker file) - exactly what a
    main-thread DB-lock-retry exhaustion produces, since the API server
    thread is a daemon and dies with it - was logged and then left dead
    forever, with nothing else noticing because cron/nginx/php-fpm keep
    running fine in debug mode. This killed python3 directly (no marker)
    and expects the monitor loop to self-heal it anyway, within a couple
    of its 10s poll
    cycles."""
    name = f"netalertx-test-crash-restart-{uuid.uuid4().hex[:8]}".lower()
    cmd = [
        "docker", "run", "-d", "--name", name,
        "--network", "host", "--userns", "host",
        "--tmpfs", "/tmp:mode=777",
        "--cap-add", "CHOWN",
        "--cap-add", "NET_RAW", "--cap-add", "NET_ADMIN", "--cap-add", "NET_BIND_SERVICE",
        "-e", "NETALERTX_DEBUG=1",
        "-e", "GRAPHQL_PORT=20212",
        IMAGE,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)

        assert _wait_until(lambda: _backend_reachable(name), timeout=90), (
            "backend never came up the first time"
        )

        kill_result = subprocess.run(
            ["docker", "exec", name, "killall", "-KILL", "python3"],
            capture_output=True, text=True, timeout=10,
        )
        assert kill_result.returncode == 0, f"failed to kill python3: {kill_result.stderr}"

        # Must go down first - otherwise a slow/duplicate python3 process
        # could mask a monitor loop that never actually noticed the kill.
        assert _wait_until(lambda: not _backend_reachable(name), timeout=10), (
            "backend still reachable right after killall -KILL python3"
        )

        assert _wait_until(lambda: _backend_reachable(name), timeout=40), (
            "backend did not come back after an unexpected (marker-less) crash "
            "in debug mode - entrypoint.sh's monitor loop left it dead"
        )
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=30)


@pytest.mark.docker
@pytest.mark.feature_complete
def test_signal_killed_service_logs_signal_number():
    """entrypoint.sh's monitor loop must record whether a dead service was
    killed by signal (status > 128) or exited normally - the one piece of
    evidence that distinguishes an external kill (OOM, SIGKILL, SIGSEGV)
    from a normal uncaught-exception exit, logged independent of whatever
    runtime the service itself is in."""
    name = f"netalertx-test-exit-status-{uuid.uuid4().hex[:8]}".lower()
    cmd = [
        "docker", "run", "-d", "--name", name,
        "--network", "host", "--userns", "host",
        "--tmpfs", "/tmp:mode=777",
        "--cap-add", "CHOWN",
        "--cap-add", "NET_RAW", "--cap-add", "NET_ADMIN", "--cap-add", "NET_BIND_SERVICE",
        "-e", "NETALERTX_DEBUG=1",
        "-e", "GRAPHQL_PORT=20212",
        IMAGE,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)

        assert _wait_until(lambda: _backend_reachable(name), timeout=90), (
            "backend never came up the first time"
        )

        subprocess.run(
            ["docker", "exec", name, "killall", "-KILL", "python3"],
            capture_output=True, text=True, timeout=10,
        )

        def _log_has_signal_9():
            result = subprocess.run(
                ["docker", "exec", name, "cat", "/tmp/log/stderr.log"],
                capture_output=True, text=True, timeout=10,
            )
            return "killed by signal 9" in result.stdout

        assert _wait_until(_log_has_signal_9, timeout=15), (
            "entrypoint.sh did not log the SIGKILL (signal 9) exit status for python3"
        )
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=30)


@pytest.mark.docker
@pytest.mark.feature_complete
def test_host_optimization_warning_matches_sysctl():
    """Validate host-optimization warning matches actual host sysctl values."""
    sysctl_bin = shutil.which("sysctl")
    if not sysctl_bin:
        pytest.skip("sysctl binary not found on host; skipping host-optimization warning check")

    ignore_proc = subprocess.run(
        [sysctl_bin, "-n", "net.ipv4.conf.all.arp_ignore"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    announce_proc = subprocess.run(
        [sysctl_bin, "-n", "net.ipv4.conf.all.arp_announce"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    if ignore_proc.returncode != 0 or announce_proc.returncode != 0:
        pytest.skip("sysctl values unavailable on host; skipping host-optimization warning check")

    arp_ignore = ignore_proc.stdout.strip()
    arp_announce = announce_proc.stdout.strip()
    expected_warning = not (arp_ignore == "1" and arp_announce == "2")

    result = _run_entrypoint(check_only=True)
    combined_output = result.stdout + result.stderr
    warning_present = "WARNING: ARP flux sysctls are not set." in combined_output

    assert warning_present == expected_warning, (
        "host-optimization warning mismatch: "
        f"arp_ignore={arp_ignore}, arp_announce={arp_announce}, "
        f"expected_warning={expected_warning}, warning_present={warning_present}"
    )
