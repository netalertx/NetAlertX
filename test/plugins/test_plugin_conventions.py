"""
Repo-wide convention checks for `server/plugins/*/config.json`.

These enforce the "Conventions Checklist" in docs/PLUGINS_DEV.md so a plugin
PR fails CI instead of relying on a reviewer noticing by hand.

    pytest test/plugins/test_plugin_conventions.py -v
"""

import ast
import glob
import json
import os
import re

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_PLUGINS_DIR = os.path.join(_ROOT, 'server', 'plugins')

# Core/maintenance plugins that intentionally run on a schedule out of the box
# (see docs/PLUGINS_DEV.md#conventions-checklist) instead of defaulting to
# "disabled" like every optional/import-style plugin.
_ALLOWED_NON_DISABLED_RUN_DEFAULTS = {
    "csv_backup": "schedule",
    "db_cleanup": "schedule",
    "maintenance": "schedule",
    "vendor_update": "schedule",
    "sync": "unused",
}

# Settings UI real-estate: descriptions render directly in Settings, not a
# README. Cap chosen well above every current plugin's length (longest is
# ~135 chars) so it only catches a genuine outlier, not routine phrasing.
_MAX_DESCRIPTION_LENGTH = 200


def _discover_plugin_dirs():
    """Every plugin folder with a config.json, skipping __-prefixed folders
    and any folder carrying an `ignore_plugin` marker (same rules the app's
    own loader uses - see server/utils/plugin_utils.py:get_plugins_configs)."""
    names = []
    for entry in sorted(os.listdir(_PLUGINS_DIR)):
        plugin_dir = os.path.join(_PLUGINS_DIR, entry)
        if not os.path.isdir(plugin_dir) or entry.startswith('__'):
            continue
        if os.path.isfile(os.path.join(plugin_dir, 'ignore_plugin')):
            continue
        if os.path.isfile(os.path.join(plugin_dir, 'config.json')):
            names.append(entry)
    return names


_PLUGIN_NAMES = _discover_plugin_dirs()


def _load_config(plugin_name):
    path = os.path.join(_PLUGINS_DIR, plugin_name, 'config.json')
    with open(path) as f:
        return json.load(f)


def _plugin_py_files(plugin_name):
    return glob.glob(os.path.join(_PLUGINS_DIR, plugin_name, '*.py'))


@pytest.mark.parametrize('plugin_name', _PLUGIN_NAMES)
def test_config_json_is_valid_json(plugin_name):
    path = os.path.join(_PLUGINS_DIR, plugin_name, 'config.json')
    with open(path) as f:
        content = f.read()
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        pytest.fail(f'{plugin_name}/config.json is not valid JSON: {e}')


@pytest.mark.parametrize('plugin_name', _PLUGIN_NAMES)
def test_array_object_default_value_parses(plugin_name):
    """A setting declared `dataType: "array"` or `"object"` must have a
    `default_value` that actually parses as that type - the same
    `json.loads()` `setting_value_to_python_type()` (server/helper.py)
    performs on it at runtime. A bare-string default_value (e.g. "default"
    instead of the JSON literal '["default"]' or '"default"') fails silently:
    the JSONDecodeError is caught, logged, and [] is returned - this is the
    exact bug fixed for devParentRelType/UI_theme/UI_TOPOLOGY_ORDER (all three
    declared dataType:"array" with a plain-string default_value)."""
    config = _load_config(plugin_name)
    for setting in config.get('settings', []):
        dtype = (setting.get('type') or {}).get('dataType')
        if dtype not in ('array', 'object'):
            continue
        default = setting.get('default_value')
        if default is None:
            continue
        try:
            json.loads(str(default).replace("'", '"'))
        except json.JSONDecodeError as e:
            pytest.fail(
                f"{plugin_name}: setting '{setting.get('function')}' declares "
                f"dataType={dtype!r} but default_value={default!r} does not "
                f"parse as {dtype} ({e}). Either fix default_value to a real "
                f"{dtype} literal, or change dataType to 'string' if the "
                f"setting is actually always scalar (check whether "
                f"elementOptions already says multiple/orderable:false - if "
                f"so that's a strong signal it should be 'string', not 'array')."
            )


@pytest.mark.parametrize('plugin_name', _PLUGIN_NAMES)
def test_run_defaults_to_disabled(plugin_name):
    config = _load_config(plugin_name)
    run_setting = next(
        (s for s in config.get('settings', []) if s.get('function') == 'RUN'),
        None,
    )
    if run_setting is None:
        return  # no RUN setting (e.g. a config-only plugin) - nothing to check

    default = run_setting.get('default_value')
    allowed = _ALLOWED_NON_DISABLED_RUN_DEFAULTS.get(plugin_name)
    if allowed is not None:
        assert default == allowed, (
            f'{plugin_name}: expected the allow-listed RUN default {allowed!r}, got {default!r}. '
            'If this plugin no longer needs an exception, remove it from '
            '_ALLOWED_NON_DISABLED_RUN_DEFAULTS.'
        )
    else:
        assert default == 'disabled', (
            f'{plugin_name}: RUN defaults to {default!r}, expected "disabled". '
            'Non-core plugins must load disabled until the user configures them - '
            'see docs/PLUGINS_DEV.md#conventions-checklist. If this is a core/maintenance '
            'plugin that legitimately needs to run out of the box, add it to '
            '_ALLOWED_NON_DISABLED_RUN_DEFAULTS in this test.'
        )


@pytest.mark.parametrize('plugin_name', _PLUGIN_NAMES)
def test_description_is_concise(plugin_name):
    config = _load_config(plugin_name)
    for desc in config.get('description', []):
        if desc.get('language_code') != 'en_us':
            continue
        text = desc.get('string', '')
        assert len(text) <= _MAX_DESCRIPTION_LENGTH, (
            f'{plugin_name}: description is {len(text)} chars (max {_MAX_DESCRIPTION_LENGTH}). '
            'This renders directly in the Settings UI - keep it short and move '
            'implementation rationale to the README instead. '
            'See docs/PLUGINS_DEV.md#conventions-checklist.'
        )


# ---------------------------------------------------------------------------
# Hardcoded fallback vs. config.json default_value drift
#
# Deliberately narrow: only matches the exact `get_setting_value("X") or
# <literal>` shape every real drift found in this repo actually used. A
# fallback expressed any other way (a named constant, a function call, ...)
# is silently skipped rather than flagged - false negatives are fine here,
# false positives aren't.
# ---------------------------------------------------------------------------
_HARDCODED_DEFAULT_RE = re.compile(
    r'''get_setting_value\(\s*["']([A-Za-z0-9_]+)["']\s*\)\s*or\s+
        (?P<literal>
            "[^"\\]*"
          | '[^'\\]*'
          | -?\d+(?:\.\d+)?
          | True|False
          | \[\]
        )''',
    re.VERBOSE,
)


def _normalize_default_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '[]' if not value else repr(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped.lower() if stripped.lower() in ('true', 'false') else stripped
    return str(value)


def _normalize_code_literal(text):
    text = text.strip()
    if text in ('True', 'False'):
        return text.lower()
    if text == '[]':
        return '[]'
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        return text[1:-1]
    return text  # bare number, left as-is


def _setting_defaults(config):
    prefix = config.get('unique_prefix', '')
    return {
        f"{prefix}_{s['function']}": s.get('default_value')
        for s in config.get('settings', [])
        if s.get('function')
    }


@pytest.mark.parametrize('plugin_name', _PLUGIN_NAMES)
def test_hardcoded_default_matches_config(plugin_name):
    defaults = _setting_defaults(_load_config(plugin_name))
    if not defaults:
        return

    mismatches = []
    for py_file in _plugin_py_files(plugin_name):
        with open(py_file) as f:
            source = f.read()
        for match in _HARDCODED_DEFAULT_RE.finditer(source):
            setting_key = match.group(1)
            if setting_key not in defaults:
                continue  # not one of this plugin's own settings (e.g. a core setting)
            literal_text = match.group('literal')
            code_value = _normalize_code_literal(literal_text)
            config_value = _normalize_default_value(defaults[setting_key])
            if code_value != config_value:
                mismatches.append(
                    f"{os.path.basename(py_file)}: get_setting_value('{setting_key}') or {literal_text} "
                    f"(-> {code_value!r}) does not match config.json's default_value {config_value!r}"
                )

    assert not mismatches, (
        f"{plugin_name}: hardcoded fallback(s) drifted from config.json's declared default - "
        "a missing/empty setting should fall back to the documented default, not a stale one:\n"
        + "\n".join(mismatches)
    )


# ---------------------------------------------------------------------------
# RUN_TIMEOUT reused as a per-call timeout inside a loop
#
# RUN_TIMEOUT is enforced by the core plugin runner (server/plugin.py) as
# the whole script's kill-timeout, not a safe per-call budget - see
# docs/PLUGINS_DEV.md#conventions-checklist. Correct patterns, either of
# which exempts a plugin from this check:
#   - config.json's "timeoutMultiplier": true on a params[] entry, for a
#     config-declared, known-length loop (see arp_scan).
#   - plugin_helper.per_item_timeout(), for a runtime-variable-length loop
#     (see the publisher plugins).
# ---------------------------------------------------------------------------
def _has_timeout_multiplier(config):
    return any(p.get('timeoutMultiplier') for p in config.get('params', []))


def _resolve_int_literal(node, tree):
    """Best-effort: resolve `node` to a literal int, either directly or via
    a same-module variable assigned a literal int elsewhere. Returns None if
    it can't be resolved (treated as "could be anything" - i.e. risky)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Name):
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == node.id for t in n.targets):
                if isinstance(n.value, ast.Constant) and isinstance(n.value.value, int):
                    return n.value.value
    return None


def _loop_always_runs_at_most_once(loop_node, tree):
    """`for _ in range(1):` (or a variable statically known to be 1) can
    never exceed a single-call budget, unlike `for x in <a real collection>:`
    - not the bug shape this check targets."""
    if not isinstance(loop_node, ast.For):
        return False
    it = loop_node.iter
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range' and len(it.args) == 1:
        count = _resolve_int_literal(it.args[0], tree)
        return count is not None and count <= 1
    return False


def _collect_run_timeout_vars(tree, source):
    run_timeout_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value_src = ast.get_source_segment(source, node.value) or ''
            if 'get_setting_value' in value_src and 'RUN_TIMEOUT' in value_src:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        run_timeout_vars.add(target.id)
    return run_timeout_vars


def _call_reuses_run_timeout(call_node, source, run_timeout_vars):
    for kw in call_node.keywords:
        if kw.arg != 'timeout':
            continue
        kw_src = ast.get_source_segment(source, kw.value) or ''
        references_var = any(
            isinstance(n, ast.Name) and n.id in run_timeout_vars
            for n in ast.walk(kw.value)
        )
        if references_var or 'RUN_TIMEOUT' in kw_src:
            return kw_src
    return None


def _run_timeout_loop_issues(py_file):
    with open(py_file) as f:
        source = f.read()

    if 'per_item_timeout(' in source:
        return []

    try:
        tree = ast.parse(source, filename=py_file)
    except SyntaxError:
        return []  # a real syntax error is caught elsewhere (py_compile in CI)

    run_timeout_vars = _collect_run_timeout_vars(tree, source)

    # Functions whose OWN body (anywhere inside it) makes a risky timeout=
    # call - a loop calling one of these by name is just as exposed as a
    # loop making the risky call directly (this is the actual shape of the
    # nmap_dev_scan bug: the loop calls a per-interface helper, and the
    # helper - not the loop itself - is the one passing timeout=).
    risky_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for call_node in ast.walk(node):
                if isinstance(call_node, ast.Call) and _call_reuses_run_timeout(call_node, source, run_timeout_vars):
                    risky_functions.add(node.name)
                    break

    issues = []
    for loop_node in ast.walk(tree):
        if not isinstance(loop_node, (ast.For, ast.While)):
            continue
        if _loop_always_runs_at_most_once(loop_node, tree):
            continue
        for call_node in ast.walk(loop_node):
            if not isinstance(call_node, ast.Call):
                continue
            kw_src = _call_reuses_run_timeout(call_node, source, run_timeout_vars)
            if kw_src:
                issues.append(f"{os.path.basename(py_file)}:{call_node.lineno}: timeout={kw_src}")
            elif isinstance(call_node.func, ast.Name) and call_node.func.id in risky_functions:
                issues.append(
                    f"{os.path.basename(py_file)}:{call_node.lineno}: "
                    f"calls {call_node.func.id}(), which reuses RUN_TIMEOUT as a per-call timeout"
                )

    return issues


@pytest.mark.parametrize('plugin_name', _PLUGIN_NAMES)
def test_run_timeout_not_reused_in_loop(plugin_name):
    config = _load_config(plugin_name)
    if _has_timeout_multiplier(config):
        return

    issues = []
    for py_file in _plugin_py_files(plugin_name):
        issues.extend(_run_timeout_loop_issues(py_file))

    assert not issues, (
        f"{plugin_name}: RUN_TIMEOUT appears reused as a per-call timeout inside a loop. "
        "RUN_TIMEOUT is the whole script's kill-timeout, not a safe per-call budget - use "
        'config.json\'s "timeoutMultiplier" for a config-declared, known-length loop, or '
        'plugin_helper.per_item_timeout() for a runtime-variable-length one. '
        "See docs/PLUGINS_DEV.md#conventions-checklist:\n" + "\n".join(issues)
    )


# Column types where the rendered value is never HTML-interpreted and a plugin
# legitimately needs to show raw text (e.g. an API response body) - the only
# types allowed to opt out of the default sanitize-on-persist pass via
# "allow_raw_text": true. See docs/PLUGINS_DEV.md#conventions-checklist.
_ALLOW_RAW_TEXT_TYPES = {"textarea_readonly"}


@pytest.mark.parametrize('plugin_name', _PLUGIN_NAMES)
def test_allow_raw_text_only_on_safe_types(plugin_name):
    config = _load_config(plugin_name)
    for col in config.get('database_column_definitions', []):
        if not col.get('allow_raw_text'):
            continue
        col_type = col.get('type')
        assert col_type in _ALLOW_RAW_TEXT_TYPES, (
            f"{plugin_name}: column {col.get('column')!r} sets \"allow_raw_text\": true "
            f"but has type {col_type!r}, not one of {sorted(_ALLOW_RAW_TEXT_TYPES)}. "
            'allow_raw_text skips HTML/control-char stripping for this field - only safe '
            'on a type that is never rendered as HTML (e.g. a read-only textarea), and '
            'still requires the renderer to escape on display - see '
            'docs/PLUGINS_DEV.md#conventions-checklist.'
        )


@pytest.mark.parametrize('plugin_name', _PLUGIN_NAMES)
def test_scan_source_plugin_matches_unique_prefix(plugin_name):
    """A CurrentScan-mapped plugin's static scanSourcePlugin value must equal
    its own unique_prefix exactly. update_devices_data_from_scan()
    (server/scan/device_handling.py) reads this value straight out of
    CurrentScan and uses it verbatim to build the '<value>_SET_ALWAYS' /
    '<value>_SET_EMPTY' settings keys (server/db/authoritative_handler.py) -
    any mismatch (wrong case, a friendly display name, punctuation) means
    those settings silently never match, so the plugin's SET_ALWAYS/SET_EMPTY
    overrides are quietly ignored. There's no legitimate reason for this
    value to differ from unique_prefix; it's never shown to the user."""
    config = _load_config(plugin_name)
    if config.get('mapped_to_table') != 'CurrentScan':
        return

    prefix = config.get('unique_prefix')
    for col in config.get('database_column_definitions', []):
        if col.get('mapped_to_column') != 'scanSourcePlugin':
            continue
        value = (col.get('mapped_to_column_data') or {}).get('value')
        assert value is not None, (
            f"{plugin_name}: column {col.get('column')!r} maps to scanSourcePlugin "
            f"but has no static \"mapped_to_column_data\": {{\"value\": ...}} - scanSourcePlugin "
            f"identifies which plugin produced a CurrentScan row and must be a single static "
            f"value (its own unique_prefix, {prefix!r}), not a per-row value from another "
            f"field. Mapping a per-row field here (e.g. a free-text detail column) writes "
            f"that field's actual value into scanSourcePlugin instead, breaking "
            f"update_devices_data_from_scan()'s per-plugin grouping the same way a wrong "
            f"static value does."
        )
        assert value == prefix, (
            f"{plugin_name}: scanSourcePlugin's static value is {value!r}, but "
            f"unique_prefix is {prefix!r}. These must match exactly - "
            f"update_devices_data_from_scan() uses scanSourcePlugin's value verbatim "
            f"to look up '{value}_SET_ALWAYS'/'{value}_SET_EMPTY', which silently never "
            f"resolves to the real '{prefix}_SET_ALWAYS'/'{prefix}_SET_EMPTY' settings "
            "if the two differ."
        )
