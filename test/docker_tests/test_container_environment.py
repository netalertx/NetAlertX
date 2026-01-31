"""
This set of tests requires netalertx-test image built. Ensure netalertx-test image is built prior
to starting these tests or they will fail.  netalertx-test image is generally rebuilt using the
Build Unit Test Docker Image task. but can be created manually with the following command executed
in the workspace:
docker buildx build -t netalertx-test .

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
"""

import os
import pathlib
import shutil
import subprocess
import uuid
import re
import pytest

IMAGE = os.environ.get("NETALERTX_TEST_IMAGE", "netalertx-test")
GRACE_SECONDS = float(os.environ.get("NETALERTX_TEST_GRACE", "2"))
DEFAULT_CAPS = ["NET_RAW", "NET_ADMIN", "NET_BIND_SERVICE"]
SUBPROCESS_TIMEOUT_SECONDS = float(os.environ.get("NETALERTX_TEST_SUBPROCESS_TIMEOUT", "30"))

CONTAINER_TARGETS: dict[str, str] = {
    "data": "/data",
    "app_db": "/data/db",
    "data_db": "/data/db",
    "app_config": "/data/config",
    "data_config": "/data/config",
    "app_log": "/tmp/log",
    "log": "/tmp/log",
    "app_api": os.environ.get("NETALERTX_API", "/tmp/api"),
    "api": os.environ.get("NETALERTX_API", "/tmp/api"),
    "nginx_conf": "/tmp/nginx/active-config",
    "nginx_active": "/tmp/nginx/active-config",
    "services_run": "/tmp/run",
}

DATA_SUBDIR_KEYS = ("app_db", "app_config")
OPTIONAL_TMP_KEYS = ("app_log", "app_api", "nginx_conf", "services_run")

VOLUME_MAP = CONTAINER_TARGETS

pytestmark = [pytest.mark.docker, pytest.mark.feature_complete]


def _unique_label(prefix: str) -> str:
    return f"{prefix.upper()}__NETALERTX_INTENTIONAL__{uuid.uuid4().hex[:6]}"


def _repo_root() -> pathlib.Path:
    env = os.environ.get("NETALERTX_REPO_ROOT")
    if env:
        return pathlib.Path(env)
    cur = pathlib.Path(__file__).resolve()
    for parent in cur.parents:
        if any(
            [
                (parent / "pyproject.toml").exists(),
                (parent / ".git").exists(),
                (parent / "back").exists() and (parent / "db").exists(),
            ]
        ):
            return parent
    return cur.parents[2]


def _docker_visible_tmp_root() -> pathlib.Path:
    """Return a docker-daemon-visible scratch directory for bind mounts.

    Pytest's default tmp_path lives under /tmp inside the devcontainer, which may
    not be visible to the Docker daemon that evaluates bind mount source paths.
    We use a directory under the repo root which is guaranteed to be shared.
    """

    # Use a directory inside the workspace to ensure visibility to Docker daemon
    root = _repo_root() / "test_mounts"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o777)
    except PermissionError:
        # Best-effort; the directory only needs to be writable by the current user.
        pass
    return root


def _docker_visible_path(path: pathlib.Path) -> pathlib.Path:
    """Map a path into `_docker_visible_tmp_root()` when it lives under /tmp."""

    try:
        if str(path).startswith("/tmp/"):
            return _docker_visible_tmp_root() / path.name
    except Exception:
        pass
    return path


def _setup_mount_tree(
    tmp_path: pathlib.Path,
    prefix: str,
    *,
    seed_config: bool = True,
    seed_db: bool = True,
) -> dict[str, pathlib.Path]:
    """Create a compose-like host tree with permissive perms for arbitrary UID/GID."""

    label = _unique_label(prefix)
    base = _docker_visible_tmp_root() / f"{label}_MOUNT_ROOT"
    base.mkdir()
    base.chmod(0o777)

    paths: dict[str, pathlib.Path] = {}

    data_root = base / f"{label}_DATA_INTENTIONAL_NETALERTX_TEST"
    data_root.mkdir(parents=True, exist_ok=True)
    data_root.chmod(0o777)
    paths["data"] = data_root

    db_dir = data_root / "db"
    db_dir.mkdir(exist_ok=True)
    db_dir.chmod(0o777)
    paths["app_db"] = db_dir
    paths["data_db"] = db_dir

    config_dir = data_root / "config"
    config_dir.mkdir(exist_ok=True)
    config_dir.chmod(0o777)
    paths["app_config"] = config_dir
    paths["data_config"] = config_dir

    for key in OPTIONAL_TMP_KEYS:
        folder_name = f"{label}_{key.upper()}_INTENTIONAL_NETALERTX_TEST"
        host_path = base / folder_name
        host_path.mkdir(parents=True, exist_ok=True)
        host_path.chmod(0o777)
        paths[key] = host_path
        if key == "app_log":
            paths["log"] = host_path
        elif key == "app_api":
            paths["api"] = host_path
        elif key == "nginx_conf":
            paths["nginx_active"] = host_path

    repo_root = _repo_root()
    if seed_config:
        config_src = repo_root / "back" / "app.conf"
        config_dst = paths["app_config"] / "app.conf"
        if config_src.exists():
            shutil.copyfile(config_src, config_dst)
            config_dst.chmod(0o666)
    if seed_db:
        db_src = repo_root / "db" / "app.db"
        db_dst = paths["app_db"] / "app.db"
        if db_src.exists():
            shutil.copyfile(db_src, db_dst)
            db_dst.chmod(0o666)

    # Ensure every mount point is world-writable so arbitrary UID/GID can write
    for p in paths.values():
        if p.is_dir():
            p.chmod(0o777)
            for child in p.iterdir():
                if child.is_dir():
                    child.chmod(0o777)
                else:
                    child.chmod(0o666)
        else:
            p.chmod(0o666)

    return paths


def _setup_fixed_mount_tree(base: pathlib.Path) -> dict[str, pathlib.Path]:
    base = _docker_visible_path(base)

    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    try:
        base.chmod(0o777)
    except PermissionError:
        pass

    paths: dict[str, pathlib.Path] = {}

    data_root = base / "DATA_NETALERTX_TEST"
    data_root.mkdir(parents=True, exist_ok=True)
    data_root.chmod(0o777)
    paths["data"] = data_root

    db_dir = data_root / "db"
    db_dir.mkdir(exist_ok=True)
    db_dir.chmod(0o777)
    paths["app_db"] = db_dir
    paths["data_db"] = db_dir

    config_dir = data_root / "config"
    config_dir.mkdir(exist_ok=True)
    config_dir.chmod(0o777)
    paths["app_config"] = config_dir
    paths["data_config"] = config_dir

    for key in OPTIONAL_TMP_KEYS:
        host_path = base / f"{key.upper()}_NETALERTX_TEST"
        host_path.mkdir(parents=True, exist_ok=True)
        host_path.chmod(0o777)
        paths[key] = host_path
        if key == "app_log":
            paths["log"] = host_path
        elif key == "app_api":
            paths["api"] = host_path
        elif key == "nginx_conf":
            paths["nginx_active"] = host_path
    return paths


def _build_volume_args(
    paths: dict[str, pathlib.Path],
) -> list[tuple[str, str, bool]]:
    return _build_volume_args_for_keys(paths, {"data"})


def _build_volume_args_for_keys(
    paths: dict[str, pathlib.Path],
    keys: set[str],
    read_only: set[str] | None = None,
) -> list[tuple[str, str, bool]]:
    bindings: list[tuple[str, str, bool]] = []
    read_only = read_only or set()
    for key in keys:
        if key not in CONTAINER_TARGETS:
            raise KeyError(f"Unknown mount key {key}")
        target = CONTAINER_TARGETS[key]
        if key not in paths:
            raise KeyError(f"Missing host path for key {key}")
        bindings.append((str(paths[key]), target, key in read_only))
    return bindings


def _chown_path(host_path: pathlib.Path, uid: int, gid: int) -> None:
    """Chown a host path using the test image with host user namespace."""

    if not host_path.exists():
        raise RuntimeError(f"Cannot chown missing path {host_path}")

    cmd = [
        "docker",
        "run",
        "--rm",
        "--userns",
        "host",
        "--user",
        "0:0",
        "--entrypoint",
        "/bin/chown",
        "-v",
        f"{host_path}:/mnt",
        IMAGE,
        "-R",
        f"{uid}:{gid}",
        "/mnt",
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Failed to chown {host_path} to {uid}:{gid}") from exc


def _chown_root(host_path: pathlib.Path) -> None:
    _chown_path(host_path, 0, 0)


def _chown_netalertx(host_path: pathlib.Path) -> None:
    _chown_path(host_path, 20211, 20211)


def _docker_volume_rm(volume_name: str) -> None:
    result = subprocess.run(
        ["docker", "volume", "rm", "-f", volume_name],
        check=False,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    print(result.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
    print(result.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.


def _docker_volume_create(volume_name: str) -> None:
    result = subprocess.run(
        ["docker", "volume", "create", volume_name],
        check=True,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    print(result.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
    print(result.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.


def _fresh_named_volume(prefix: str) -> str:
    name = _unique_label(prefix).lower().replace("__", "-")
    # Ensure we're exercising Docker's fresh-volume copy-up behavior.
    _docker_volume_rm(name)
    return name


def _ensure_volume_copy_up(volume_name: str) -> None:
    """Ensure a named volume is initialized from the NetAlertX image.

    If we write into the volume first (e.g., with an Alpine helper container),
    Docker will not perform the image-to-volume copy-up and the volume root may
    stay root:root 0755, breaking arbitrary UID/GID runs.
    """

    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--userns",
            "host",
            "-v",
            f"{volume_name}:/data",
            "--entrypoint",
            "/bin/sh",
            IMAGE,
            "-c",
            "true",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    print(result.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
    print(result.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.


def _seed_volume_text_file(
    volume_name: str,
    container_path: str,
    content: str,
    *,
    chmod_mode: str = "644",
    user: str | None = None,
) -> None:
    """Create/overwrite a text file inside a named volume.

    Uses a tiny helper container so we don't rely on bind mounts (which are
    resolved on the Docker daemon host).
    """

    cmd = [
        "docker",
        "run",
        "--rm",
        "--userns",
        "host",
    ]
    if user:
        cmd.extend(["--user", user])
    cmd.extend(
        [
            "-v",
            f"{volume_name}:/data",
            "alpine:3.22",
            "sh",
            "-c",
            f"set -eu; mkdir -p \"$(dirname '{container_path}')\"; cat > '{container_path}'; chmod {chmod_mode} '{container_path}'",
        ]
    )

    result = subprocess.run(
        cmd,
        input=content,
        text=True,
        check=True,
        capture_output=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    print(result.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
    print(result.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.


def _volume_has_file(volume_name: str, container_path: str) -> bool:
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--userns",
            "host",
            "-v",
            f"{volume_name}:/data",
            "alpine:3.22",
            "sh",
            "-c",
            f"test -f '{container_path}'",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    print(result.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
    print(result.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
    return result.returncode == 0


@pytest.mark.parametrize(
    "uid_gid",
    [
        (1001, 1001),
        (1502, 1502),
    ],
)
def test_nonroot_custom_uid_logs_note(
    tmp_path: pathlib.Path,
    uid_gid: tuple[int, int],
) -> None:
    """Ensure arbitrary non-root UID/GID can run with compose-like mounts."""

    uid, gid = uid_gid

    vol = _fresh_named_volume(f"note_uid_{uid}")
    try:
        # Fresh named volume at /data: matches default docker-compose UX.
        result = _run_container(
            f"note-uid-{uid}",
            volumes=None,
            volume_specs=[f"{vol}:/data"],
            user=f"{uid}:{gid}",
            sleep_seconds=5,
        )
    finally:
        _docker_volume_rm(vol)

    _assert_contains(result, f"NetAlertX note: current UID {uid} GID {gid}", result.args)
    assert "expected UID" in result.output
    assert result.returncode == 0


def test_root_then_user_20211_transition() -> None:
    """Ensure a root-initialized volume works when restarted as user 20211."""

    volume = _fresh_named_volume("root_user_transition")

    try:
        # Phase 1: run as root (default) to provision the volume.
        init_result = _run_container(
            "transition-root",
            volumes=None,
            volume_specs=[f"{volume}:/data"],
            env={"NETALERTX_CHECK_ONLY": "1"},
            sleep_seconds=8,
        )
        assert init_result.returncode == 0

        # Phase 2: restart with explicit user 20211 using the same volume.
        user_result = _run_container(
            "transition-user-20211",
            volumes=None,
            volume_specs=[f"{volume}:/data"],
            user="20211:20211",
            env={"NETALERTX_CHECK_ONLY": "1", "SKIP_TESTS": "1"},
            wait_for_exit=True,
            sleep_seconds=5,
            rm_on_exit=False,
        )

        combined_output = (user_result.output or "") + (user_result.stderr or "")
        print(combined_output)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
        assert user_result.returncode == 0, combined_output
        assert "permission denied" not in combined_output.lower()
        assert "configuration issues detected" not in combined_output.lower()
    finally:
        # On failure, surface full container logs for debugging and ensure containers are removed
        try:
            if 'user_result' in locals() and getattr(user_result, 'returncode', 0) != 0:
                cname = getattr(user_result, 'container_name', None)
                if cname:
                    logs = subprocess.run(
                        ["docker", "logs", cname],
                        capture_output=True,
                        text=True,
                        timeout=SUBPROCESS_TIMEOUT_SECONDS,
                        check=False,
                    )
                    print("--- docker logs (user container) ---")
                    print(logs.stdout or "<no stdout>")
                    if logs.stderr:
                        print("--- docker logs stderr ---")
                        print(logs.stderr)
        except Exception:
            pass

        # Best-effort cleanup of any leftover containers
        try:
            if 'init_result' in locals():
                cname = getattr(init_result, 'container_name', None)
                if cname:
                    subprocess.run(["docker", "rm", "-f", cname], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except Exception:
            pass
        try:
            if 'user_result' in locals():
                cname = getattr(user_result, 'container_name', None)
                if cname:
                    subprocess.run(["docker", "rm", "-f", cname], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except Exception:
            pass

        _docker_volume_rm(volume)


def _run_container(
    label: str,
    volumes: list[tuple[str, str, bool]] | None = None,
    *,
    env: dict[str, str] | None = None,
    user: str | None = None,
    drop_caps: list[str] | None = None,
    network_mode: str | None = "host",
    extra_args: list[str] | None = None,
    volume_specs: list[str] | None = None,
    sleep_seconds: float = GRACE_SECONDS,
    wait_for_exit: bool = False,
    rm_on_exit: bool = True,
    pre_entrypoint: str | None = None,
    userns_mode: str | None = "host",
    image: str = IMAGE,
) -> subprocess.CompletedProcess[str]:
    name = f"netalertx-test-{label}-{uuid.uuid4().hex[:8]}".lower()

    tmp_uid = 20211
    tmp_gid = 20211
    if user:
        try:
            u_str, g_str = user.split(":", 1)
            tmp_uid = int(u_str)
            tmp_gid = int(g_str)
        except Exception:
            # Keep defaults if user format is unexpected.
            tmp_uid = 20211
            tmp_gid = 20211

    # Clean up any existing container with this name
    subprocess.run(
        ["docker", "rm", "-f", name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    cmd: list[str]
    if rm_on_exit:
        cmd = ["docker", "run", "--rm", "--name", name]
    else:
        cmd = ["docker", "run", "--name", name]

    # Avoid flakiness in host-network runs when the host already uses the
    # default NetAlertX ports. Tests can still override explicitly via `env`.
    effective_env: dict[str, str] = dict(env or {})
    if network_mode == "host":
        if "PORT" not in effective_env:
            effective_env["PORT"] = str(30000 + (int(uuid.uuid4().hex[:4], 16) % 20000))
        if "GRAPHQL_PORT" not in effective_env:
            gql = 30000 + (int(uuid.uuid4().hex[4:8], 16) % 20000)
            if str(gql) == effective_env["PORT"]:
                gql = 30000 + ((gql + 1) % 20000)
            effective_env["GRAPHQL_PORT"] = str(gql)

    if network_mode:
        cmd.extend(["--network", network_mode])
    if userns_mode:
        cmd.extend(["--userns", userns_mode])
    # Match docker-compose UX: /tmp is tmpfs with 1700 and owned by the runtime UID/GID.
    cmd.extend(["--tmpfs", f"/tmp:mode=1700,uid={tmp_uid},gid={tmp_gid}"])
    if user:
        cmd.extend(["--user", user])
    if drop_caps is not None:
        for cap in drop_caps:
            cmd.extend(["--cap-drop", cap])
    else:
        cmd.extend(["--cap-drop", "ALL"])
        for cap in DEFAULT_CAPS:
            cmd.extend(["--cap-add", cap])
    if effective_env:
        for key, value in effective_env.items():
            cmd.extend(["-e", f"{key}={value}"])
    if extra_args:
        cmd.extend(extra_args)
    for host_path, target, readonly in volumes or []:
        mount = f"{host_path}:{target}"
        if readonly:
            mount += ":ro"
        cmd.extend(["-v", mount])
    if volume_specs:
        for spec in volume_specs:
            cmd.extend(["-v", spec])

    # Diagnostic wrapper: list ownership and perms of mounted targets inside
    # the container before running the real entrypoint. This helps debug
    # permission failures by capturing the container's view of the host mounts.
    mounts_ls = """
    echo "--- MOUNT PERMS (container view) ---";
    ls -ldn \
    """
    for _, target, _ in volumes or []:
        mounts_ls += f" {target}"
    mounts_ls += " || true; echo '--- END MOUNTS ---'; \n"

    setup_script = ""
    if pre_entrypoint:
        setup_script = pre_entrypoint
        if not setup_script.endswith("\n"):
            setup_script += "\n"

    if wait_for_exit:
        script = mounts_ls + setup_script + "sh /entrypoint.sh"
    else:
        script = "".join([
            mounts_ls,
            setup_script,
            "sh /entrypoint.sh & pid=$!; ",
            f"sleep {sleep_seconds}; ",
            "if kill -0 $pid >/dev/null 2>&1; then kill -TERM $pid >/dev/null 2>&1 || true; fi; ",
            "wait $pid; code=$?; if [ $code -eq 143 ]; then exit 0; fi; exit $code"
        ])
    cmd.extend(["--entrypoint", "/bin/sh", image, "-c", script])

    # ┌─────────────────────────────────────────────────────────────────────────────────────────┐
    # │ MANDATORY LOGGING - DO NOT REMOVE OR REDIRECT TO DEVNULL                                │
    # │ These print statements are required for debugging test failures. See file header.       │
    # └─────────────────────────────────────────────────────────────────────────────────────────┘
    print("\n--- DOCKER CMD ---\n", " ".join(cmd), "\n--- END CMD ---\n")
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,  # MUST capture stdout for test assertions and debugging
        stderr=subprocess.PIPE,  # MUST capture stderr for test assertions and debugging
        text=True,
        timeout=max(SUBPROCESS_TIMEOUT_SECONDS, sleep_seconds),  # Coderabbit - please stop trying to increase the length of timeout.
        check=False,
    )

    print(result.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
    print(result.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
    # Combine and clean stdout and stderr
    stdouterr = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout or "") + re.sub(
        r"\x1b\[[0-9;]*m", "", result.stderr or ""
    )
    result.output = stdouterr
    # ┌─────────────────────────────────────────────────────────────────────────────────────────┐
    # │ MANDATORY LOGGING - DO NOT REMOVE OR REDIRECT TO DEVNULL                                │
    # │ Without this output, test failures cannot be diagnosed. See file header.                │
    # └─────────────────────────────────────────────────────────────────────────────────────────┘
    print("\n--- CONTAINER OUTPUT START ---")
    print(result.output)
    print("--- CONTAINER OUTPUT END ---\n")

    # Expose the container name to callers for debug/logging/cleanup.
    try:
        result.container_name = name  # type: ignore[attr-defined]
    except Exception:
        # Be resilient if CompletedProcess is unexpectedly frozen.
        pass

    return result


def _assert_contains(result, snippet: str, cmd: list[str] = None) -> None:
    output = result.output + result.stderr
    if snippet not in output:
        cmd_str = " ".join(cmd) if cmd else ""
        raise AssertionError(
            f"Expected to find '{snippet}' in container output.\n"
            f"STDOUT:\n{result.output}\n"
            f"STDERR:\n{result.stderr}\n"
            f"Combined output:\n{output}\n"
            f"Container command:\n{cmd_str}"
        )


def _assert_contains_any(result, snippets: list[str], cmd: list[str] | None = None) -> None:
    """Assert that at least one of the provided snippets appears in output.

    This helper makes tests resilient to harmless wording changes in entrypoint
    and diagnostic messages (e.g., when SPEC wording is updated).
    """
    output = result.output + result.stderr
    for s in snippets:
        if s in output:
            return
    cmd_str = " ".join(cmd) if cmd else ""
    raise AssertionError(
        f"Expected to find one of '{snippets}' in container output.\n"
        f"STDOUT:\n{result.output}\n"
        f"STDERR:\n{result.stderr}\n"
        f"Combined output:\n{output}\n"
        f"Container command:\n{cmd_str}"
    )


def _extract_mount_rows(output: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    in_table = False
    expected_cols = 0

    for raw_line in (output or "").splitlines():
        line = raw_line.rstrip()
        if not in_table:
            if line.startswith(" Path") and "Writeable" in line:
                # Legacy format: Path | Writeable | Mount | RAMDisk | Performance | DataLoss
                in_table = True
                expected_cols = 5
            elif line.startswith(" Path") and "| R" in line and "| W" in line:
                # Current format: Path | R | W | Mount | RAMDisk | Performance | DataLoss
                in_table = True
                expected_cols = 6
            continue

        if not line.strip():
            break
        if line.lstrip().startswith("Path"):
            continue
        if set(line.strip()) <= {"-", "+"}:
            continue

        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 1 + expected_cols:
            continue
        path = parts[0].strip()
        if not path:
            continue
        rows[path] = parts[1 : 1 + expected_cols]

    return rows


def _assert_mount_row(
    result,
    path: str,
    *,
    write: str | None = None,
    mount: str | None = None,
    ramdisk: str | None = None,
    performance: str | None = None,
    dataloss: str | None = None,
) -> None:
    rows = _extract_mount_rows(result.output)
    if path not in rows:
        raise AssertionError(
            f"Mount table row for {path} not found. Rows: {sorted(rows)}\nOutput:\n{result.output}"
        )
    columns = rows[path]

    # Legacy: [Writeable, Mount, RAMDisk, Performance, DataLoss]
    # Current: [R, W, Mount, RAMDisk, Performance, DataLoss]
    if len(columns) == 5:
        label_to_value = {
            "Writeable": columns[0],
            "Mount": columns[1],
            "RAMDisk": columns[2],
            "Performance": columns[3],
            "DataLoss": columns[4],
        }
        write_label = "Writeable"
    elif len(columns) == 6:
        label_to_value = {
            "R": columns[0],
            "W": columns[1],
            "Mount": columns[2],
            "RAMDisk": columns[3],
            "Performance": columns[4],
            "DataLoss": columns[5],
        }
        write_label = "W"
    else:
        raise AssertionError(
            f"Unexpected mount table column count for {path}: {len(columns)}. Columns: {columns}\nOutput:\n{result.output}"
        )

    checks = [
        (write_label, write),
        ("Mount", mount),
        ("RAMDisk", ramdisk),
        ("Performance", performance),
        ("DataLoss", dataloss),
    ]

    for label, expected in checks:
        if expected is None:
            continue
        actual = label_to_value.get(label)
        if actual != expected:
            raise AssertionError(
                f"{path} {label} expected {expected}, got {actual}.\n"
                f"Row: {label_to_value}\nOutput:\n{result.output}"
            )


def _setup_zero_perm_dir(paths: dict[str, pathlib.Path], key: str) -> None:
    """Set up a directory with files and zero permissions for testing."""
    if key in ["app_db", "app_config"]:
        # Files already exist from _setup_mount_tree seeding
        pass
    else:
        # Create a dummy file for other directories
        (paths[key] / "dummy.txt").write_text("dummy")

    # Chmod all files in the directory to 000
    for f in paths[key].iterdir():
        f.chmod(0)

    # Chmod the directory itself to 000
    paths[key].chmod(0)


def _restore_zero_perm_dir(paths: dict[str, pathlib.Path], key: str) -> None:
    """Restore permissions after zero perm test."""
    # Chmod directory back to 700
    paths[key].chmod(0o700)

    # Chmod files back to appropriate permissions
    for f in paths[key].iterdir():
        if f.name in ["app.db", "app.conf"]:
            f.chmod(0o600)
        else:
            f.chmod(0o644)


def test_missing_capabilities_triggers_warning(tmp_path: pathlib.Path) -> None:
    """Test missing required capabilities - simulates insufficient container privileges.

    5. Missing Required Capabilities: Simulates running without NET_ADMIN, NET_RAW,
    NET_BIND_SERVICE capabilities. Required for ARP scanning and network operations.
    Expected: "exec /bin/sh: operation not permitted" error, guidance to add capabilities.

    CRITICAL CANARY TEST:
    This test verifies the Shell-based pre-flight check (10-capabilities-audit.sh).
    Since the Python binary has `setcap` applied, it will fail to launch entirely
    if capabilities are missing (kernel refuses execve). This Shell script is the
    ONLY way to warn the user gracefully before the crash.

    Check script: 10-capabilities-audit.sh
    Sample message: "ALERT: Python execution capabilities (NET_RAW/NET_ADMIN) are missing."
    """
    paths = _setup_mount_tree(tmp_path, "missing_caps")
    volumes = _build_volume_args_for_keys(paths, {"data"})
    result = _run_container(
        "missing-caps",
        volumes,
        drop_caps=["ALL"],
    )
    _assert_contains_any(
        result,
        [
            "ALERT: Python execution capabilities (NET_RAW/NET_ADMIN) are missing",
            "Python execution capabilities (NET_RAW/NET_ADMIN) are missing",
        ],
        result.args,
    )


def test_missing_host_network_warns(tmp_path: pathlib.Path) -> None:
    # No output assertion, just returncode check
    """Test missing host networking - simulates running without host network mode.

    8. Missing Host Networking: Simulates running without network_mode: host.
    Limits ARP scanning capabilities for network discovery.
    Expected: Warning about ARP scanning limitations, guidance to use host networking.

    Check script: check-network-mode.sh
    Sample message: "⚠️  ATTENTION: NetAlertX is not running with --network=host. Bridge networking..."
    """
    vol = _fresh_named_volume("missing_host_network")
    try:
        result = _run_container(
            "missing-host-network",
            volumes=None,
            volume_specs=[f"{vol}:/data"],
            network_mode=None,
            sleep_seconds=15,
        )
    finally:
        _docker_volume_rm(vol)
    _assert_contains(result, "not running with --network=host", result.args)


# NOTE: The following runtime-behavior tests depended on the entrypoint continuing even when
# /data was mounted without write permissions. With fail-fast enabled we must supply a pre-owned
# (UID/GID 20211) data volume, which this dev container cannot provide for bind mounts. Once the
# docker tests switch to compose-managed fixtures, restore these cases by moving them back to the
# top level.

def test_missing_app_conf_triggers_seed(tmp_path: pathlib.Path) -> None:
    """Test missing configuration file seeding - simulates corrupted/missing app.conf.

    9. Missing Configuration File: Simulates corrupted/missing app.conf.
    Container automatically regenerates default configuration on startup.
    Expected: Automatic regeneration of default configuration.

    Check script: /entrypoint.d/15-first-run-config.sh
    Sample message: "Default configuration written to"
    """
    vol = _fresh_named_volume("missing_app_conf")
    try:
        result = _run_container(
            "missing-app-conf",
            volumes=None,
            volume_specs=[f"{vol}:/data"],
            sleep_seconds=15,
        )

        # Verify the generated configuration contains the dynamic subnet detection
        # (check that it didn't fall back to default '--localnet')
        check_conf = subprocess.run(
            [
                "docker", "run", "--rm", "-v", f"{vol}:/data",
                "alpine:3.22", "cat", "/data/config/app.conf"
            ],
            capture_output=True, text=True
        )
        if check_conf.returncode == 0:
            match = re.search(r"SCAN_SUBNETS\s*=\s*(.*)", check_conf.stdout)
            if match:
                val = match.group(1)
                assert "interface=" in val, f"SCAN_SUBNETS should have interface: {val}"
                assert val != "['--localnet']", "SCAN_SUBNETS should not be default localnet"

    finally:
        _docker_volume_rm(vol)
    # The key assertion: config seeding happened
    _assert_contains(result, "Default configuration written to", result.args)
    # NOTE: The container may fail later in startup (e.g., nginx issues) but the seeding
    # test passes if the config file was created. Full startup success is tested elsewhere.



def test_first_run_dynamic_subnet(tmp_path: pathlib.Path) -> None:
    """Test dynamic subnet detection during first run config generation.

    Ensures that when app.conf is generated, it detects the actual network interfaces
    instead of defaulting to '--localnet'.
    """
    paths = _setup_mount_tree(tmp_path, "dynamic_subnet", seed_config=False)
    mount_args = _build_volume_args_for_keys(paths, CONTAINER_TARGETS.keys())

    _run_container(
        "dyn-subnet",
        volumes=mount_args,
        sleep_seconds=15,
    )

    # Use docker to read the file to avoid permission issues (file is 600 root:root)
    # paths["app_config"] is the host absolute path
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{paths['app_config']}:/mnt",
        "alpine:3.22",
        "cat", "/mnt/app.conf"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    assert result.returncode == 0, f"Could not read app.conf. Stderr: {result.stderr}"
    content = result.stdout

    # Check that SCAN_SUBNETS was set to something other than the default fallback
    # The default fallback in the script is ['--localnet'] if no interfaces found.
    # But in test environment (and prod), we expect interfaces.
    match = re.search(r"SCAN_SUBNETS\s*=\s*(.*)", content)
    assert match, "SCAN_SUBNETS not found in config"

    val = match.group(1)
    # verify it contains an interface definition
    assert "interface=" in val, f"SCAN_SUBNETS should contain interface spec, got: {val}"
    assert val != "['--localnet']", "SCAN_SUBNETS should not be default localnet"


def test_missing_app_db_triggers_seed(tmp_path: pathlib.Path) -> None:
    """Test missing database file seeding - simulates corrupted/missing app.db.

    10. Missing Database File: Simulates corrupted/missing app.db.
    Container automatically creates initial database schema on startup.
    Expected: Automatic creation of initial database schema.

    Check script: /entrypoint.d/20-first-run-db.sh
    Sample message: "Building initial database schema"
    """
    vol = _fresh_named_volume("missing_app_db")
    try:
        _ensure_volume_copy_up(vol)
        # Seed only app.conf; leave app.db missing to trigger first-run DB schema creation.
        _seed_volume_text_file(
            vol,
            "/data/config/app.conf",
            "TIMEZONE='UTC'\n",
            chmod_mode="644",
            user="20211:20211",
        )
        result = _run_container(
            "missing-app-db",
            volumes=None,
            volume_specs=[f"{vol}:/data"],
            user="20211:20211",
            sleep_seconds=20,
        )
        print(result.stdout)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
        print(result.stderr)  # DO NOT REMOVE OR MODIFY - MANDATORY LOGGING FOR DEBUGGING & CI.
        # The key assertion: database file was created
        _assert_contains_any(
            result,
            ["Building initial database schema", "First run detected"],
            result.args,
        )
        # The key assertion: database file was created
        assert _volume_has_file(vol, "/data/db/app.db"), "Database file should have been created"
    finally:
        _docker_volume_rm(vol)
    # NOTE: The container may fail later in startup (e.g., nginx issues) but the DB seeding
    # test passes if the database file was created. Full startup success is tested elsewhere.


def test_custom_port_without_writable_conf(tmp_path: pathlib.Path) -> None:
    """Test custom port configuration without writable nginx config mount.

    4. Custom Port Without Nginx Config Mount: Simulates setting custom LISTEN_ADDR/PORT
    without mounting nginx config. Container starts but uses default address.
    Expected: Container starts but uses default address, warning about missing config mount.

    Check script: check-nginx-config.sh
    Sample messages: "⚠️  ATTENTION: Nginx configuration mount /tmp/nginx/active-config is missing."
                        "⚠️  ATTENTION: Unable to write to /tmp/nginx/active-config/netalertx.conf."
    """
    vol = _fresh_named_volume("custom_port_ro_conf")
    extra_args = [
        "--tmpfs",
        f"{VOLUME_MAP['nginx_conf']}:uid=20211,gid=20211,mode=500",
    ]
    try:
        result = _run_container(
            "custom-port-ro-conf",
            volumes=None,
            volume_specs=[f"{vol}:/data"],
            env={"PORT": "24444", "LISTEN_ADDR": "127.0.0.1"},
            user="20211:20211",
            extra_args=extra_args,
            sleep_seconds=15,
        )
    finally:
        _docker_volume_rm(vol)
    _assert_contains(result, "Unable to write to", result.args)
    _assert_contains(
        result, f"{VOLUME_MAP['nginx_conf']}/netalertx.conf", result.args
    )
    assert result.returncode != 0


def test_excessive_capabilities_warning(tmp_path: pathlib.Path) -> None:
    """Test excessive capabilities detection - simulates container with extra capabilities.

    11. Excessive Capabilities: Simulates container with capabilities beyond the required
    NET_ADMIN, NET_RAW, and NET_BIND_SERVICE.
    Expected: Warning about excessive capabilities detected.

    Check script: 90-excessive-capabilities.sh
    Sample message: "Excessive capabilities detected"
    """
    vol = _fresh_named_volume("excessive_caps")
    try:
        result = _run_container(
            "excessive-caps",
            volumes=None,
            volume_specs=[f"{vol}:/data"],
            extra_args=["--cap-add=SYS_ADMIN", "--cap-add=NET_BROADCAST"],
            sleep_seconds=15,
        )
    finally:
        _docker_volume_rm(vol)
    _assert_contains(result, "Excessive capabilities detected", result.args)
    _assert_contains(result, "bounding caps:", result.args)


def test_appliance_integrity_read_write_mode(tmp_path: pathlib.Path) -> None:
    """Test appliance integrity - simulates running with read-write root filesystem.

    12. Appliance Integrity: Simulates running container with read-write root filesystem
    instead of read-only mode.
    Expected: Warning about running in read-write mode instead of read-only.

    Check script: 95-appliance-integrity.sh
    Sample message: "Container is running as read-write, not in read-only mode"
    """
    vol = _fresh_named_volume("appliance_integrity")
    try:
        result = _run_container(
            "appliance-integrity",
            volumes=None,
            volume_specs=[f"{vol}:/data"],
            sleep_seconds=15,
        )
    finally:
        _docker_volume_rm(vol)
    _assert_contains(
        result, "Container is running as read-write, not in read-only mode", result.args
    )


def test_zero_permissions_app_db_dir(tmp_path: pathlib.Path) -> None:
    """Test zero permissions - simulates mounting directories/files with no permissions.

    2. Zero Permissions: Simulates mounting directories/files with no permissions (chmod 000).
    Tests directories and files with no read/write/execute permissions.
    Expected: Mounts table shows ❌ for writeable status, configuration issues detected.
    """
    paths = _setup_mount_tree(tmp_path, "chmod_app_db")
    _setup_zero_perm_dir(paths, "app_db")
    volumes = _build_volume_args_for_keys(paths, {"data"})
    try:
        result = _run_container(
            "chmod-app-db",
            volumes,
            user="20211:20211",
            wait_for_exit=True,
        )
        # Check that the mounts table shows the app_db directory as not writeable
        _assert_mount_row(result, VOLUME_MAP["app_db"], write="❌")
        # Check that configuration issues are detected
        _assert_contains(result, "Configuration issues detected", result.args)
        assert result.returncode != 0
    finally:
        _restore_zero_perm_dir(paths, "app_db")


def test_zero_permissions_app_config_dir(tmp_path: pathlib.Path) -> None:
    """Test zero permissions - simulates mounting directories/files with no permissions.

    2. Zero Permissions: Simulates mounting directories/files with no permissions (chmod 000).
    Tests directories and files with no read/write/execute permissions.
    Expected: Mounts table shows ❌ for writeable status, configuration issues detected.
    """
    paths = _setup_mount_tree(tmp_path, "chmod_app_config")
    _setup_zero_perm_dir(paths, "app_config")
    volumes = _build_volume_args_for_keys(paths, {"data"})
    try:
        result = _run_container(
            "chmod-app-config",
            volumes,
            user="20211:20211",
            wait_for_exit=True,
        )
        # Check that the mounts table shows the app_config directory as not writeable
        _assert_mount_row(result, VOLUME_MAP["app_config"], write="❌")
        # Check that configuration issues are detected
        _assert_contains(result, "Configuration issues detected", result.args)
        assert result.returncode != 0
    finally:
        _restore_zero_perm_dir(paths, "app_config")


def test_mandatory_folders_creation(tmp_path: pathlib.Path) -> None:
    """Test mandatory folders creation - simulates missing plugins log directory.

    1. Mandatory Folders: Simulates missing required directories and log files.
    Container automatically creates plugins log, system services run log/tmp directories,
    and required log files on startup.
    Expected: Automatic creation of all required directories and files.

    Check script: 25-mandatory-folders.sh
    Sample message: "Creating Plugins log"
    """
    paths = _setup_mount_tree(tmp_path, "mandatory_folders")
    # Remove the plugins log directory to simulate missing mandatory folder
    plugins_log_dir = paths["app_log"] / "plugins"
    if plugins_log_dir.exists():
        shutil.rmtree(plugins_log_dir)

    # Ensure other directories are writable and owned by netalertx user so container gets past mounts.py
    for key in [
        "data",
        "app_db",
        "app_config",
        "app_log",
        "app_api",
        "services_run",
        "nginx_conf",
    ]:
        paths[key].chmod(0o777)
        _chown_netalertx(paths[key])  # Ensure all directories are owned by netalertx

    volumes = _build_volume_args_for_keys(paths, {"data"})
    result = _run_container(
        "mandatory-folders", volumes, user="20211:20211", sleep_seconds=5
    )
    _assert_contains(result, "Creating Plugins log", result.args)
    # The container will fail at writable config due to permission issues, but we just want to verify
    # that mandatory folders creation ran successfully


def test_writable_config_validation(tmp_path: pathlib.Path) -> None:
    """Test writable config validation - simulates invalid config file type.

    3. Writable Config Validation: Simulates app.conf being a non-regular file (directory).
    Container verifies it can read from and write to critical config and database files.
    Expected: "Path is not a regular file" warning for config file.

    Check script: 35-writable-config.sh
    Sample message: "Path is not a regular file"
    """
    paths = _setup_mount_tree(tmp_path, "writable_config")
    # Force a non-regular file for /data/config/app.conf to exercise the correct warning branch.
    config_path = paths["app_config"] / "app.conf"
    if config_path.exists():
        if config_path.is_dir():
            shutil.rmtree(config_path)
        else:
            config_path.unlink()
    config_path.mkdir(parents=False)
    config_path.chmod(0o777)
    _chown_netalertx(config_path)

    # Ensure directories are writable and owned by netalertx user so container gets past mounts.py
    for key in [
        "data",
        "app_db",
        "app_config",
        "app_log",
        "app_api",
        "services_run",
        "nginx_conf",
    ]:
        paths[key].chmod(0o777)
        _chown_netalertx(paths[key])

    volumes = _build_volume_args_for_keys(paths, {"data"})
    result = _run_container(
        "writable-config", volumes, user="20211:20211", sleep_seconds=5.0
    )
    _assert_contains(result, "ATTENTION: Path is not a regular file.", result.args)


def test_mount_analysis_ram_disk_performance(tmp_path: pathlib.Path) -> None:
    """Test mount analysis for RAM disk performance issues.

    Tests 10-mounts.py detection of persistent paths on RAM disks (tmpfs) which can cause
    performance issues and data loss on container restart.
    Expected: Mounts table shows ❌ for RAMDisk on persistent paths, performance warnings.

    Check script: 10-mounts.py
    Sample message: "Configuration issues detected"
    """
    paths = _setup_mount_tree(tmp_path, "ram_disk_mount")
    # Mount persistent paths (db, config) on tmpfs to simulate RAM disk
    volumes = [
        (str(paths["app_log"]), VOLUME_MAP["app_log"], False),
        (str(paths["app_api"]), VOLUME_MAP["app_api"], False),
        (str(paths["services_run"]), VOLUME_MAP["services_run"], False),
        (str(paths["nginx_conf"]), VOLUME_MAP["nginx_conf"], False),
    ]
    # Use tmpfs mounts for persistent paths with proper permissions
    extra_args = [
        "--tmpfs",
        f"{VOLUME_MAP['app_db']}:uid=20211,gid=20211,mode=755",
        "--tmpfs",
        f"{VOLUME_MAP['app_config']}:uid=20211,gid=20211,mode=755",
        "--tmpfs",
        "/tmp/nginx:uid=20211,gid=20211,mode=755",
    ]
    result = _run_container(
        "ram-disk-mount", volumes=volumes, extra_args=extra_args, user="20211:20211"
    )
    # Check that mounts table shows RAM disk detection for persistent paths
    _assert_mount_row(
        result,
        VOLUME_MAP["app_db"],
        write="✅",
        mount="✅",
        ramdisk="❌",
        performance="➖",
        dataloss="❌",
    )
    _assert_mount_row(
        result,
        VOLUME_MAP["app_config"],
        write="✅",
        mount="✅",
        ramdisk="❌",
        performance="➖",
        dataloss="❌",
    )
    # Check that configuration issues are detected due to dataloss risk
    _assert_contains(result, "Configuration issues detected", result.args)
    # NOTE: The mounts script only exits non-zero for read/write permission failures on persistent
    # paths, NOT for dataloss warnings. Dataloss is a warning, not a fatal error.
    # The container continues to run after showing the warning.
    assert result.returncode == 0


def test_mount_analysis_dataloss_risk(tmp_path: pathlib.Path) -> None:
    """Test mount analysis for dataloss risk on non-persistent filesystems.

    Tests 10-mounts.py detection when persistent database/config paths are
    mounted on non-persistent filesystems (tmpfs, ramfs).
    Expected: Mounts table shows dataloss risk warnings for persistent paths on tmpfs.

    Check script: 10-mounts.py
    Sample message: "Configuration issues detected"
    """
    paths = _setup_mount_tree(tmp_path, "dataloss_risk")
    # Mount persistent paths (db, config) on tmpfs to simulate non-persistent storage
    volumes = [
        (str(paths["app_log"]), VOLUME_MAP["app_log"], False),
        (str(paths["app_api"]), VOLUME_MAP["app_api"], False),
        (str(paths["services_run"]), VOLUME_MAP["services_run"], False),
        (str(paths["nginx_conf"]), VOLUME_MAP["nginx_conf"], False),
    ]
    # Use tmpfs mounts for persistent paths with proper permissions
    extra_args = [
        "--tmpfs",
        f"{VOLUME_MAP['app_db']}:uid=20211,gid=20211,mode=755",
        "--tmpfs",
        f"{VOLUME_MAP['app_config']}:uid=20211,gid=20211,mode=755",
        "--tmpfs",
        "/tmp/nginx:uid=20211,gid=20211,mode=755",
    ]
    result = _run_container(
        "dataloss-risk", volumes=volumes, extra_args=extra_args, user="20211:20211"
    )
    # Check that mounts table shows dataloss risk for persistent paths on tmpfs
    _assert_mount_row(
        result,
        VOLUME_MAP["app_db"],
        write="✅",
        mount="✅",
        ramdisk="❌",
        performance="➖",
        dataloss="❌",
    )
    _assert_mount_row(
        result,
        VOLUME_MAP["app_config"],
        write="✅",
        mount="✅",
        ramdisk="❌",
        performance="➖",
        dataloss="❌",
    )
    # Check that configuration issues are detected due to dataloss risk
    _assert_contains(result, "Configuration issues detected", result.args)
    # NOTE: The mounts script only exits non-zero for read/write permission failures on persistent
    # paths, NOT for dataloss warnings. Dataloss is a warning, not a fatal error.
    # The container continues to run after showing the warning.
    assert result.returncode == 0


def test_restrictive_permissions_handling(tmp_path: pathlib.Path) -> None:
    """Test handling of restrictive permissions on bind mounts.

    Simulates a user mounting a directory with restrictive permissions (e.g., 755 root:root).
    The container should either fail gracefully or handle it if running as root (which triggers fix).
    If running as non-root (default), it should fail to write if it doesn't have access.
    """
    paths = _setup_mount_tree(tmp_path, "restrictive_perms")

    # Helper to chown/chmod without userns host (workaround for potential devcontainer hang)
    def _setup_restrictive_dir(host_path: pathlib.Path) -> None:
        cmd = [
            "docker", "run", "--rm",
            # "--userns", "host", # Removed to avoid hang
            "--user", "0:0",
            "--entrypoint", "/bin/sh",
            "-v", f"{host_path}:/mnt",
            IMAGE,
            "-c", "chown -R 0:0 /mnt && chmod 755 /mnt",
        ]
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )

    # Set up a restrictive directory (root owned, 755)
    target_dir = paths["app_db"]
    _setup_restrictive_dir(target_dir)

    # Mount ALL volumes to avoid errors during permission checks
    keys = {"data", "app_db", "app_config", "app_log", "app_api", "services_run", "nginx_conf"}
    volumes = _build_volume_args_for_keys(paths, keys)

    # Run as root by default to exercise permission-fix path explicitly.
    result_root = _run_container(
        "restrictive-perms-root",
        volumes,
        user="0:0",
        sleep_seconds=5,
        network_mode=None,
        userns_mode=None
    )

    # Ensure root-based startup succeeds without permission errors before verification.
    assert result_root.returncode == 0
    assert "permission denied" not in result_root.output.lower()
    assert "unable to write" not in result_root.output.lower()

    _assert_contains(
        result_root,
        "NetAlertX startup: Running privilege check and path priming as ROOT.",
        result_root.args,
    )
    _assert_contains_any(
        result_root,
        [
            "Running as root (PUID=0). Paths will be owned by root.",
            "WARNING: Running as root (PUID=0). Prefer a non-root PUID.",
            "NetAlertX is running as ROOT",
            "NetAlertX note: current UID 0 GID 0",
        ],
        result_root.args,
    )

    check_cmd = [
        "docker", "run", "--rm",
        "--entrypoint", "/bin/sh",
        "--user", "0:0",
        IMAGE,
        "-c", "ls -ldn /data/db && touch /data/db/test_write_after_fix"
    ]
    # Add all volumes to check_cmd too
    for host_path, target, _readonly in volumes:
        check_cmd.extend(["-v", f"{host_path}:{target}"])

    check_result = subprocess.run(
        check_cmd,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    # MANDATORY LOGGING: capture the follow-up verification command output for CI debugging.
    print("\n--- PERM FIX CHECK CMD ---\n", " ".join(check_cmd), "\n--- END CHECK CMD ---\n")
    print("--- PERM FIX CHECK STDOUT ---")
    print(check_result.stdout or "<no stdout>")
    print("--- PERM FIX CHECK STDERR ---")
    print(check_result.stderr or "<no stderr>")

    if check_result.returncode != 0:
        print(f"Check command failed. Cmd: {check_cmd}")
        print(f"Stderr: {check_result.stderr}")
        print(f"Stdout: {check_result.stdout}")

    assert check_result.returncode == 0, f"Should be able to write after root fix script runs. Stderr: {check_result.stderr}. Stdout: {check_result.stdout}"
