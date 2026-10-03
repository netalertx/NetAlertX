# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

NetAlertX is a network visibility / asset-intelligence platform: continuous device discovery, presence/intruder detection, IPAM drift tracking, notifications, and multi-site sync, aimed at homelabs, MSPs, and NOCs. Backend is Python, frontend is PHP/JS served by Nginx, data lives in SQLite plus flat config files.

## Commands

Almost everything must run **inside the devcontainer** (Docker) — the host machine lacks the runtime environment (DB, `/data/config`, dependencies). Check with `ls -d /workspaces/NetAlertX`; if absent, you're on the host.

```bash
# Full test suite (default — comprehensive coverage over speed, don't optimize for time unless asked)
cd /workspaces/NetAlertX; pytest test/

# One file or directory
pytest test/plugins/test_adguard_export.py
pytest test/plugins/

# Fast/unit-only (only when explicitly asked for "fast"/"quick" tests)
pytest test/ -m 'not docker and not feature_complete'

# Reset the environment / pick up code changes / get a fresh API_TOKEN
bash /workspaces/NetAlertX/.devcontainer/scripts/setup.sh
sleep 5
python3 -c "from helper import get_setting_value; print(get_setting_value('API_TOKEN'))"

# Lint (matches CI in .github/workflows/code-checks.yml)
flake8 . --max-line-length=180 --ignore=E221,E222,E251,E203

# Full CI-equivalent run (regenerates devcontainer Dockerfile, rebuilds, runs everything)
./scripts/run_tests_in_docker_environment.sh
```

Rebuild the test image (`docker buildx build -t netalertx-test .`) only if the Dockerfile or dependencies changed — otherwise skip it, it's slow.

Outside the container, most plugin unit tests (`test/plugins/test_*.py`) still run standalone — they stub NetAlertX modules into `sys.modules` before importing the plugin script. See the stubbing pitfall below before adding one.

## Architecture

### Backend layout

- `server/__main__.py` — entry point. `server/plugin.py` — plugin runner/scheduler. `server/api_server/` — Flask + GraphQL API.
- `server/const.py` / `server/config_paths.py` — resolve the three runtime path roots. `server/conf.py` — process-wide config variables (a deliberate workaround for cross-module globals).
- `server/db/` — the only layer allowed to touch SQLite directly (`db_helper.py`). `server/models/` — domain handlers on top of it (e.g. `DeviceInstance` in `models/device_instance.py`). Never query the DB from elsewhere — go through a model or `db_helper.py`.
- `server/scan/`, `server/messaging/`, `server/workflows/`, `server/utils/` — scanning pipeline, notification dispatch, the workflow-automation engine, and shared utilities (`utils/datetime_utils.py`'s `timeNowUTC()` is the *only* place `datetime.now()` should be called — everything is stored in UTC).

### Frontend

`front/` is PHP + vanilla JS served by Nginx — no build step, no bundler, no `package.json`. Pages are top-level `.php` files; shared logic under `front/php/`.

### Data & path conventions

Three distinct roots, each with a different persistence contract — get this wrong and data silently disappears on restart:
- `dbFolderPath` (`/data/db`) — durable. Plugin-internal state (caches, "what did I already do" trackers) belongs here.
- `configPath` (`/data/config`) — durable, user-facing. `app.conf` lives here; config-like plugin artifacts (exports, backups) belong here too.
- `logPath` (`/tmp/log`, plus `/tmp/api`, `/tmp/db_is_locked`, nginx state) — **ephemeral tmpfs**, wiped on every container restart. Never put anything here you need to survive a restart. (`server/plugins/adguard_export`, `unifi_import` were both fixed this way after shipping with state files rooted in `logPath` — check any plugin that opens a file outside its `RESULT_FILE` against this before assuming it's fine.)

All three, plus `dataPath` (`/data`, the bare parent of `dbFolderPath`/`configPath` - avoid writing loose files directly under it; pick one of the two subpaths above instead), are exported from `server/const.py` and importable by any plugin.

### Plugin system (`server/plugins/*/`)

Every plugin is a folder with `config.json` (manifest: settings, data contract, DB column mapping), an optional `script.py`-equivalent, and a `README.md`. Start from `server/plugins/__template/`. Full reference: `docs/PLUGINS_DEV.md` (its "Conventions Checklist" section is CI-enforced — see below).

Non-obvious things that have caused real, shipped bugs in this codebase:

- **`RUN_TIMEOUT` is the whole subprocess's kill-timeout, enforced by `server/plugin.py`, not a safe per-call HTTP/subprocess timeout.** A plugin that loops over N things and reuses `RUN_TIMEOUT` as each individual call's timeout can have one slow call burn the whole budget and get SIGKILLed before it writes its result file — silently losing the entire run. Two correct answers depending on the loop shape:
  - Looping over a **config-declared, known-length list** (e.g. a subnets setting) → mark that `params[]` entry `"timeoutMultiplier": true` in `config.json`; the framework scales the *outer* kill-timeout by the list length. See `arp_scan/config.json`.
  - Looping over a **runtime-variable-length collection** (e.g. a notification queue) → `plugin_helper.per_item_timeout(run_timeout, item_count)` divides the *inner* per-call budget instead. See `server/plugins/_publisher_ntfy/ntfy.py`.
  - `test/plugins/test_plugin_conventions.py` mechanically checks for the unguarded reuse pattern (AST-based, including the case where the loop calls a helper function that does the risky call) — run it after touching any plugin that makes network/subprocess calls in a loop.
- **`plugin_helper.Plugin_Object`**: `helpVal1-4` and `watchedValue1-4` both preserve a real `0`/`False` you pass explicitly (checked via `is not None`) — only an actually-omitted (`None`) value defaults to `""`. Don't reintroduce a bare `x or ""` coercion here; it silently discards legitimate falsy values (this was a real, if narrowly-triggered, bug).
- A plugin's hardcoded Python fallback (`get_setting_value("X") or <literal>`) must match that setting's `config.json` `default_value` — `test_plugin_conventions.py` checks this too. `RUN` should default to `"disabled"` for every non-core plugin; description strings render directly in the Settings UI and should stay short (README is for implementation detail).
- Plugin unit tests that stub NetAlertX modules into `sys.modules` (so a script imports standalone outside the container) **must pop every stubbed name back out immediately after the one-time import** — otherwise the fake module leaks and shadows the real one for every other test file collected in the same pytest session, regardless of file/alphabetical order. See `test/plugins/test_ntfy_custom_headers.py` for the pattern, or `docs/PLUGINS_DEV.md` / the `testing-workflow` skill for the full writeup.

### Data contract (plugin → DB)

Plugins write pipe-delimited rows to `RESULT_FILE` via `plugin_helper.Plugin_Objects`/`Plugin_Object` — 9 required columns, 4 optional `helpVal*` ones. Full column spec and validation rules: `docs/PLUGINS_DEV_DATA_CONTRACT.md`.

### Skills

Procedural/how-to knowledge (running tests, resetting the DB, devcontainer management, PR analysis, etc.) lives as paired files in `.gemini/skills/<name>/` and `.github/skills/<name>/` (see `.gemini/skills/skills-index/SKILL.md` for the pairing map) — Claude Code should treat both as equally authoritative sources for the same procedures. The pairing convention is "keep body content identical"; a CI job (`check-skill-pairs` in `.github/workflows/code-checks.yml`) flags PRs that edit one side of a pair without the other, but it only checks *presence*, not content — if you edit one side, check whether the other needs the same update.

## Code conventions

- DB columns are camelCase, never snake_case (`deviceInstanceId`, not `device_instance_id`).
- Every `subprocess` call needs an explicit timeout; a nested subprocess call needs its own — an outer timeout doesn't propagate.
- Always run MACs through `normalize_mac()` (`plugin_helper.py`) before writing to DB; MAC literals in tests must be lowercase.
- No inline imports — everything at module top level.
- Reuse `test/db_test_helpers.py` for DB mocks/fixtures in tests rather than redefining `DummyDB`/`make_db` locally.
- Keep files under ~500 lines; split rather than grow.
- Every Python function/method gets a succinct docstring describing its current use and behavior — one or two sentences, not a changelog of what changed or why (that belongs in the commit/PR, not the docstring). Same rule for JS: a JSDoc `/** ... */` block, not a plain `//` line above the function. Whenever you touch a function that only has a plain description comment (Python or JS), convert it to a proper docstring as part of that edit rather than leaving the old style next to new code.
- Before adding a new key to `front/php/templates/language/en_us.json`, search it for an existing key with the same text/purpose and reuse it - prefer generic `Gen_*` keys over page-scoped names for genuinely generic UI text (e.g. `Gen_Prev`/`Gen_Next`, not `Presence_Page_Prev`). Only the English file needs a real translation; other locales fall back to it automatically at runtime for a key they don't have. After adding or changing any key in `en_us.json`, run `python3 front/php/templates/language/merge_translations.py` (plain stdlib, no deps) - it re-sorts `en_us.json` alphabetically and propagates the new key into every other locale file with an empty placeholder value, so translators see what needs translating. Skipping this leaves the other 23 locale files out of sync with `en_us.json`'s key set.
- A filterable Devices-table column is added in one place: `DEVICE_FILTER_COLUMNS` (`server/db/device_filter_columns.py`), which generates both `sql_devices_filters` (`server/const.py`) and (after running `python3 server/db/sync_device_filter_columns_config.py`) `server/plugins/ui_settings/config.json`'s `columns_filters.options[]`. Never hand-edit either generated side directly - `test/db/test_device_filter_columns.py`'s drift guard fails if the registry and `config.json` disagree. This is for the *filterable*-columns list only; the separate *displayable*-columns list (`device_columns.options[]`, `front/js/device-columns.js`) is untouched by this mechanism.
- **Search before you build.** Before writing a new check/condition/helper for something (an "is X true" computation, a UI state signal, a utility), search the codebase for an existing implementation of the same or similar logic first - the same file (read the whole file, not just the section being edited), a sibling page, the Python backend. If one exists, extract it into a shared function and call it from the new site; don't write a parallel implementation planning to deduplicate later. A real case: a new frontend indicator needed to know "is the backend still applying a settings change" - that exact check already existed inline in `settings.php`'s own polling loop (`handleLoadingDialog()`), found only after two rounds of reinventing it elsewhere (a cookie-based guess, then a duplicate PHP endpoint) instead of reading the rest of the file first.
- **No new PHP backend logic.** `front/` is being migrated away from PHP, so never add a new PHP endpoint or new server-side computation inside an existing PHP file. If a feature needs backend state or computation, add it to the Python server and expose it to the frontend through an existing read path (`app_state.json` via `query_json.php`, `table_settings.json`, a REST/GraphQL endpoint) - never re-derive logic in PHP that the Python side already knows or could easily expose. Editing existing PHP page logic (templating, bug fixes) is fine; this is about not growing the PHP surface area.
- **A stateful UI feature (survives a reload, coordinates across tabs, reacts to a backend push) is a cross-cutting mechanism, not "just a UI feature."** Treat it like one before writing code: trace every existing consumer of the data it needs (e.g. everything that already reads `app_state.json`), not just the one file being edited. The visible surface looking small (a badge, an icon) says nothing about whether the state-propagation mechanism underneath already exists elsewhere.
- **No JS/PHP test harness exists in `front/` — simulate before asking for a live test, every time, not after a live test fails.** Write a disposable Node/PHP script that runs the actual function(s) against realistic inputs (including inputs crossing from a different file than the one being edited) before calling a change ready to test. A diff review misses things a five-second script run catches - a renamed parameter still referenced by its old name, an ordering assumption that's wrong once two async steps are both in play.
