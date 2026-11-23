"""
Tests for install/production-filesystem/services/start-backend.sh's
kill-sweep: it matches python3 processes by NAME (killall -x python3), not by
the specific PID that died - so a recovery restart (triggered by
entrypoint.sh after an unexpected backend crash) collaterally kills any
unrelated python3 process in the container, such as a currently-running
plugin subprocess, even though only the crashed backend needed replacing.
"""

import subprocess
import time
import uuid
import pytest

IMAGE = "netalertx-test"


def _run_sweep_test(skip_sweep: bool) -> bool:
    """Start a container, launch a decoy python3 process (standing in for an
    unrelated plugin subprocess), run start-backend.sh's kill-sweep (with or
    without the skip flag), and return whether the decoy survived."""
    name = f"netalertx-test-backend-sweep-{uuid.uuid4().hex[:8]}".lower()
    cmd = [
        "docker", "run", "-d", "--name", name,
        "--network", "host", "--userns", "host",
        "--tmpfs", "/tmp:mode=777",
        "--cap-add", "CHOWN", "--cap-add", "NET_RAW", "--cap-add", "NET_ADMIN", "--cap-add", "NET_BIND_SERVICE",
        "--entrypoint", "sleep",
        IMAGE, "infinity",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)

        subprocess.run(
            ["docker", "exec", "-d", name, "python3", "-c", "import time; time.sleep(60)"],
            capture_output=True, text=True, timeout=10,
        )
        time.sleep(1)

        env_prefix = "NETALERTX_SKIP_BACKEND_KILL_SWEEP=1 " if skip_sweep else ""
        # timeout caps the real server's exec tail - only the kill-sweep
        # portion (which runs first) matters for this test.
        subprocess.run(
            ["docker", "exec", name, "timeout", "2", "bash", "-c",
             f"{env_prefix}/services/start-backend.sh"],
            capture_output=True, text=True, timeout=15,
        )

        # pgrep -f treats its pattern as a regex - unescaped parens in
        # "time.sleep(60)" would be grouping syntax, not literal characters,
        # so match on the paren-free prefix instead.
        result = subprocess.run(
            ["docker", "exec", name, "pgrep", "-f", "time.sleep"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=30)


@pytest.mark.docker
@pytest.mark.feature_complete
def test_default_sweep_kills_unrelated_python3():
    """Baseline: without the skip flag, start-backend.sh's kill-sweep matches
    by process name and kills the unrelated decoy too."""
    assert _run_sweep_test(skip_sweep=False) is False, (
        "decoy python3 process should have been killed by the default sweep"
    )


@pytest.mark.docker
@pytest.mark.feature_complete
def test_skip_sweep_env_var_spares_unrelated_python3():
    """NETALERTX_SKIP_BACKEND_KILL_SWEEP=1 must skip the kill-sweep entirely,
    so a recovery restart doesn't collaterally kill an unrelated python3
    process (e.g. a currently-running plugin subprocess)."""
    assert _run_sweep_test(skip_sweep=True) is True, (
        "decoy python3 process should have survived with the skip flag set"
    )
