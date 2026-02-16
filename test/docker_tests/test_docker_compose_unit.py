import subprocess


def test_run_docker_compose_returns_output(monkeypatch, tmp_path):
    """Unit test that verifies `_run_docker_compose` returns a CompletedProcess
    instance with an `output` attribute (combined stdout+stderr). This uses
    monkeypatched subprocess.run to avoid invoking Docker.
    """
    from test.docker_tests import test_docker_compose_scenarios as mod

    # Prepare a dummy compose file path
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}")

    # Track calls to identify what's being run
    call_log = []

    def fake_run(cmd, *args, **kwargs):
        """Return appropriate fake responses based on the command being run."""
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        call_log.append(cmd_str)

        # Identify the command type and return appropriate response
        if "down" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout="down-out\n", stderr="")
        elif "volume prune" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        elif "container prune" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        elif "ps" in cmd_str:
            # Return valid container entries with "Startup pre-checks" won't be here
            # but we need valid ps output
            return subprocess.CompletedProcess(cmd, 0, stdout="test-container Running 0\n", stderr="")
        elif "logs" in cmd_str:
            # Include "Startup pre-checks" so the retry logic exits early
            return subprocess.CompletedProcess(cmd, 0, stdout="log-out\nStartup pre-checks\n", stderr="")
        elif "up" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout="up-out\n", stderr="")
        else:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    # Monkeypatch subprocess.run used inside the module
    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    # Also patch subprocess.Popen for the audit stream (returns immediately terminating proc)
    class FakePopen:
        def __init__(self, *args, **kwargs):
            pass

        def terminate(self):
            pass

    monkeypatch.setattr(mod.subprocess, "Popen", FakePopen)

    # Call under test
    result = mod._run_docker_compose(compose_file, "proj-test", timeout=1, detached=False)

    # The returned object must have the combined `output` attribute
    assert hasattr(result, "output")
    assert "up-out" in result.output
    assert "log-out" in result.output
