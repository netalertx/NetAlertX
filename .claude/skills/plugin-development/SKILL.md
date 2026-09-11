---
name: plugin-development
description: Create and run NetAlertX plugins. Use this when asked to create a plugin, run a plugin, test a plugin, or develop plugin functionality.
---

# Plugin Development

## Expected Workflow

1. Read this skill and `docs/PLUGINS_DEV.md` for full context.
2. Find or create the plugin in `server/plugins/<code_name>/`.
3. Read the plugin's `config.json` and script to understand its functionality and settings.
4. Run: `python3 server/plugins/<code_name>/script.py`
5. Retrieve the result from `/tmp/log/plugins/last_result.<PREF>.log` quickly — the backend processes and deletes it almost immediately.

## Plugin Structure

```text
server/plugins/<code_name>/
├── config.json      # Manifest: settings, data contract, DB column mapping
├── script.py         # Main script (or equivalent, depending on data_source)
└── README.md         # Setup/usage docs
```

- `code_name` must match the folder name.
- `unique_prefix` drives every setting key and filename (e.g. `ARPSCAN` → `ARPSCAN_RUN`, `last_result.ARPSCAN.log`). Uppercase letters only, no underscores/numbers, must be unique across all plugins.
- Ensure `sys.path` includes `/app/server/plugins` and `/app/server` (as in `server/plugins/__template/rename_me.py`).

## Settings Pattern

- `<PREF>_RUN`: execution phase (see below). Should default to `"disabled"` for any non-core plugin.
- `<PREF>_RUN_SCHD`: cron-like schedule — check a similar existing plugin for precedent (e.g. `pihole_api_scan` uses `*/5 * * * *`) rather than inventing a new cadence.
- `<PREF>_CMD`: script path.
- `<PREF>_RUN_TIMEOUT`: timeout in seconds — **enforced by the core plugin runner as the whole script's kill-timeout** (`server/plugin.py` passes it straight to `subprocess(..., timeout=...)`). Not a safe per-HTTP-call timeout — don't reuse it for individual network calls in a loop, or one slow call can burn the whole budget and get the process killed before it writes its result file. Two correct alternatives: `config.json`'s `"timeoutMultiplier": true` on a `params[]` entry for a config-declared, known-length loop (see `arp_scan`); `plugin_helper.per_item_timeout()` for a runtime-variable-length loop (see the `_publisher_*` plugins).
- `<PREF>_WATCH`: columns to watch for changes.
- `<PREF>_IMPORT_ON`: optional — gates whether this run's rows get promoted into `CurrentScan` (only relevant if `mapped_to_table: "CurrentScan"`). See `docs/PLUGINS_IMPORT_BEHAVIOR.md` for the related per-row `scanCreatesDevice`/`scanNotificationMode`/`scanPresence` columns.

## Data Contract

```python
from plugin_helper import Plugin_Objects

plugin_objects = Plugin_Objects(RESULT_FILE)
plugin_objects.add_object(...)       # once per discovered item
plugin_objects.write_result_file()   # exactly once, at the end
```

Full column spec: `docs/PLUGINS_DEV_DATA_CONTRACT.md`. Note `helpVal1-4`/`watchedValue1-4` both preserve a real `0`/`False` you pass explicitly — only an omitted (`None`) value defaults to `""`.

## Execution Phases

| Phase | Trigger |
|-------|---------|
| `once` | Once at startup |
| `schedule` | On cron schedule |
| `always_after_scan` | After every scan |
| `before_name_updates` | Before name resolution |
| `on_new_device` | When new device detected |
| `on_notification` | When notification triggered |

## Plugin Formats

| Format | Purpose | Phase |
|--------|---------|-------|
| publisher | Send notifications | `on_notification` |
| dev scanner | Create/manage devices | `schedule` |
| name discovery | Discover device names | `before_name_updates` |
| importer | Import from services | `schedule` |
| system | Core functionality | `schedule` |

## Before Opening a PR

Check the plugin against the [Conventions Checklist](../../../docs/PLUGINS_DEV.md#conventions-checklist) — `RUN` default, schedule precedent, `RUN_TIMEOUT` semantics, reusing core settings instead of duplicating them, description length (renders in the Settings UI — keep it short), and the multi-instance settings pattern (nested array + popup-form, see `rest_import`, not a hardcoded "primary"/"secondary" pair). Most plugin PR review comments trace back to one of these, and `test/plugins/test_plugin_conventions.py` mechanically enforces the RUN-default, description-length, hardcoded-default-drift, and RUN_TIMEOUT-reuse-in-loop items — run it after touching a plugin.

## Starting Point

Copy `server/plugins/__template/` and customize. Read `docs/PLUGINS_DEV.md` for the full development guide.
