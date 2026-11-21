"""
Tests for install/production-filesystem/services/healthcheck.sh's
app_state.json staleness check - the independent hang-detection backstop
that catches a main loop that's technically alive but not making progress
(a case neither the DB-lock retry wrapper nor the daemon-thread fix can
detect, since both only help when the thread actually dies).
"""

import subprocess
import uuid
import pytest

IMAGE = "netalertx-test"


def _run_healthcheck(setup_cmd: str) -> subprocess.CompletedProcess:
    """Run /services/healthcheck.sh in the test container after a setup
    command (e.g. writing a fake app_state.json with a specific mtime)."""
    name = f"netalertx-test-healthcheck-{uuid.uuid4().hex[:8]}".lower()
    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--entrypoint", "/bin/sh", IMAGE, "-c",
        f"{setup_cmd}; /services/healthcheck.sh; true",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


@pytest.mark.docker
@pytest.mark.feature_complete
def test_healthcheck_fails_on_stale_app_state():
    # Alpine's busybox `touch` doesn't understand GNU's `-d '20 minutes ago'`
    # natural-language form - it does support `-d @<epoch>` (confirmed via
    # `touch --help` inside the image), so compute the epoch instead.
    result = _run_healthcheck(
        "mkdir -p /tmp/api && touch -d @$(($(date +%s) - 1200)) /tmp/api/app_state.json"
    )
    assert "hasn't updated" in result.stderr
    assert "backend loop may be hung" in result.stderr


@pytest.mark.docker
@pytest.mark.feature_complete
def test_healthcheck_passes_on_fresh_app_state():
    result = _run_healthcheck(
        "mkdir -p /tmp/api && touch /tmp/api/app_state.json"
    )
    assert "app_state.json updated" in result.stdout
    assert "hasn't updated" not in result.stderr


@pytest.mark.docker
@pytest.mark.feature_complete
def test_healthcheck_fails_when_app_state_missing():
    result = _run_healthcheck("rm -f /tmp/api/app_state.json")
    assert "app_state.json not found" in result.stderr
