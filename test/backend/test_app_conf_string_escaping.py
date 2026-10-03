"""
NetAlertX app.conf String Escaping Tests

Dispatches the real front/php/server/util.php savesettings path through the PHP
CLI against a temporary config directory, then checks that the generated
app.conf compiles without warnings and parses back to the typed values (with '
mapped to {s-quote}) for both scalar string and array string settings.

License: GNU GPLv3
"""

import json
import os
import shutil
import subprocess
import warnings
from pathlib import Path

import pytest

FRONT_DIR = Path(__file__).resolve().parents[2] / "front"
PHP_BIN = shutil.which("php") or shutil.which("php83")

pytestmark = pytest.mark.skipif(PHP_BIN is None, reason="PHP CLI (php or php83) not available")

# Stands in for the web request: reads {"front": ..., "settings": [...]} from stdin,
# satisfies security.php's request-only dependencies and lets util.php dispatch savesettings.
PHP_RUNNER = (
    '$in = json_decode(stream_get_contents(STDIN), true);'
    'if (!function_exists("apache_request_headers")) { function apache_request_headers() { return []; } }'
    '$_SERVER["DOCUMENT_ROOT"] = $in["front"];'
    '$_SERVER["HTTP_HOST"] = "localhost";'
    '$_SERVER["REQUEST_URI"] = "/php/server/util.php";'
    '$_REQUEST = ["function" => "savesettings", "settings" => json_encode($in["settings"])];'
    'require $in["front"] . "/php/server/util.php";'
)

# Minimal app.conf that lets globals.php and security.php load without a password prompt.
SEED_APP_CONF = "TIMEZONE='UTC'\nSETPWD_enable_password=False\n"

CASES = {
    "ordinary_text": "hello world",
    "doc_regex": r"192\.0\.2\..*",
    "consecutive_backslashes": r"a\\b",
    "backslashes_only": "\\" * 3,
    "trailing_backslash": "trail" + "\\",
    "existing_s_quote": "x{s-quote}y",
    "literal_single_quote": "it's",
    "regex_with_quote": r"\d+\s*'",
    "backslash_before_quote": r"a\'b",
}


def scalar_key(case_id):
    """Return the app.conf key used for the scalar string setting of a case."""
    return f"S_{case_id.upper()}"


def array_key(case_id):
    """Return the app.conf key used for the array string setting of a case."""
    return f"A_{case_id.upper()}"


@pytest.fixture(scope="module")
def app_conf(tmp_path_factory):
    """Run util.php saveSettings() once for all cases and return the generated app.conf source."""
    root = tmp_path_factory.mktemp("app_conf")
    config_dir = root / "config"
    api_dir = root / "api"
    session_dir = root / "session"
    for folder in (config_dir, api_dir, session_dir):
        folder.mkdir()
    (config_dir / "app.conf").write_text(SEED_APP_CONF)

    # UI_WAIT_FOR_SETTINGS=True keeps getReloadWaitRequired() from reading the (absent) API files.
    settings = [["General", "UI_WAIT_FOR_SETTINGS", "boolean", True]]
    for case_id, typed in CASES.items():
        settings.append(["Test", scalar_key(case_id), "string", typed])
        settings.append(["Test", array_key(case_id), "array", ["plain", typed]])

    env = dict(os.environ, NETALERTX_CONFIG=str(config_dir), NETALERTX_API=str(api_dir))
    result = subprocess.run(
        [PHP_BIN, "-d", f"session.save_path={session_dir}", "-d", "display_errors=stderr", "-r", PHP_RUNNER],
        input=json.dumps({"front": str(FRONT_DIR), "settings": settings}),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=True,
    )
    assert json.loads(result.stdout)["success"] is True, result.stdout + result.stderr
    return (config_dir / "app.conf").read_text()


def setting_line(source, key):
    """Return the single app.conf line that assigns key."""
    lines = [line for line in source.splitlines() if line.startswith(f"{key}=")]
    assert len(lines) == 1, f"expected one {key}= line, got {lines}"
    return lines[0]


def parse_app_conf(source):
    """Compile source with all warnings as errors and exec it like the backend app.conf readers."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        code = compile(source, "app.conf", "exec")
    conf = {}
    exec(code, {"__builtins__": {}}, conf)
    return conf


def test_warning_check_rejects_unescaped_backslash():
    """The warnings-as-errors compile rejects the unescaped regex source that util.php emitted before escaping."""
    with pytest.raises(SyntaxError):
        parse_app_conf(r"X='192\.0\.2\..*'")


def test_generated_app_conf_compiles(app_conf):
    """The whole app.conf written by saveSettings() compiles without warnings."""
    parse_app_conf(app_conf)


@pytest.mark.parametrize("case_id", CASES.keys())
def test_scalar_string_round_trip(app_conf, case_id):
    """A scalar string setting written by saveSettings() compiles cleanly and parses back to the typed value."""
    key = scalar_key(case_id)
    conf = parse_app_conf(setting_line(app_conf, key))
    assert conf[key] == CASES[case_id].replace("'", "{s-quote}")


@pytest.mark.parametrize("case_id", CASES.keys())
def test_array_string_round_trip(app_conf, case_id):
    """An array string setting written by saveSettings() compiles cleanly and parses back to the typed values."""
    key = array_key(case_id)
    conf = parse_app_conf(setting_line(app_conf, key))
    assert conf[key] == ["plain", CASES[case_id].replace("'", "{s-quote}")]


def test_doc_regex_exact_source(app_conf):
    """The documentation regex is emitted with doubled backslashes and parses back unchanged."""
    scalar = setting_line(app_conf, scalar_key("doc_regex"))
    array = setting_line(app_conf, array_key("doc_regex"))
    assert scalar == r"S_DOC_REGEX='192\\.0\\.2\\..*'"
    assert array == r"A_DOC_REGEX=['plain','192\\.0\\.2\\..*']"
    assert parse_app_conf(scalar)["S_DOC_REGEX"] == r"192\.0\.2\..*"
    assert parse_app_conf(array)["A_DOC_REGEX"] == ["plain", r"192\.0\.2\..*"]
