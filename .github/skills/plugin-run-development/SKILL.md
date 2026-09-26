---
name: netalertx-plugin-run-development
description: Create and run NetAlertX plugins. Use this when asked to create plugin, run plugin, test plugin, plugin development, or execute plugin script.
---

# Plugin Development

## Expected Workflow for Running Plugins

1. Read this skill document for context and instructions.
2. Find the plugin in `server/plugins/<code_name>/`.
3. Read the plugin's `config.json` and `script.py` to understand its functionality and settings.
4. Formulate and run the command: `python3 server/plugins/<code_name>/script.py`.
5. Retrieve the result from the plugin log folder (`/tmp/log/plugins/last_result.<PREF>.log`) quickly, as the backend may delete it after processing.

## Run a Plugin Manually

```bash
python3 server/plugins/<code_name>/script.py
```

Ensure `sys.path` includes `/app/server/plugins` and `/app/server` (as in the template).

## Plugin Structure

```text
server/plugins/<code_name>/
├── config.json      # Manifest with settings
├── script.py        # Main script
└── ...
```

## Manifest Location

`server/plugins/<code_name>/config.json`

- `code_name` == folder name
- `unique_prefix` drives settings and filenames (e.g., `ARPSCAN`)

## Settings Pattern

- `<PREF>_RUN`: execution phase
- `<PREF>_RUN_SCHD`: cron-like schedule
- `<PREF>_CMD`: script path
- `<PREF>_RUN_TIMEOUT`: timeout in seconds — **this is enforced by the core plugin runner as the whole script's kill-timeout** (`server/plugin.py` passes it straight to `subprocess(..., timeout=...)`). It is not a safe per-HTTP-call timeout — don't reuse it for individual network calls in a loop, or one slow call can burn the whole budget and get the process killed before it writes its result file.
- `<PREF>_WATCH`: columns to watch for changes
- `<PREF>_IMPORT_ON`: optional — gates whether this run's rows get promoted into `CurrentScan` (only relevant if `mapped_to_table: "CurrentScan"`). See `docs/PLUGINS_IMPORT_BEHAVIOR.md` for the related per-row `scanCreatesDevice`/`scanNotificationMode`/`scanPresence` columns.
- **`dataType` and `default_value` must agree.** `dataType: "array"`/`"object"` needs a real JSON literal for `default_value` (`'["default"]'`), not a bare string (`"default"`). `setting_value_to_python_type()` (`server/helper.py`) `json.loads()`s the default at runtime; a bare string fails silently — logged, and `[]` is returned instead of your default (e.g. `devParentRelType`, `UI_theme`, `UI_TOPOLOGY_ORDER`). If `elementOptions` already sets `multiple`/`orderable: "false"`, the setting is scalar — use `dataType: "string"` instead.

## Data Contract

Scripts write to `/tmp/log/plugins/last_result.<PREF>.log`

**Important:** The backend will almost immediately process this result file and delete it after ingestion. If you need to inspect the output, run the plugin and immediately retrieve the result file before the backend processes it.

Use `server/plugins/plugin_helper.py`:

```python
from plugin_helper import Plugin_Objects

plugin_objects = Plugin_Objects()
plugin_objects.add_object(...)  # During processing
plugin_objects.write_result_file()  # Exactly once at end
```

Every mapped field (`objectPrimaryId`/`objectSecondaryId`/`watchedValue1-4`/`extra`/`helpVal1-4`) is HTML/control-char-stripped by default before it's persisted: plugin output is untrusted (network responses, device-reported names, etc.). `foreignKey` is always sanitized too, unconditionally. Only opt a column out (`"allow_raw_text": true`) if it's a display-only type (`textarea_readonly`); see `docs/PLUGINS_DEV.md#field-sanitization`.

## Execution Phases

- `once`: runs once at startup
- `schedule`: runs on cron schedule
- `always_after_scan`: runs after every scan
- `before_name_updates`: runs before name resolution
- `on_new_device`: runs when new device detected
- `on_notification`: runs when notification triggered

## Plugin Formats

| Format | Purpose | Runs |
|--------|---------|------|
| publisher | Send notifications | `on_notification` |
| dev scanner | Create/manage devices | `schedule` |
| name discovery | Discover device names | `before_name_updates` |
| importer | Import from services | `schedule` |
| system | Core functionality | `schedule` |

## Before Opening a PR

Check the plugin against the [Conventions Checklist](../../../docs/PLUGINS_DEV.md#conventions-checklist) in `docs/PLUGINS_DEV.md` — `RUN` default, schedule precedent, `RUN_TIMEOUT` semantics, reusing core settings, description length, the multi-instance settings pattern, `allow_raw_text` restricted to display-only column types, and `scanSourcePlugin`'s static value matching `unique_prefix` exactly. Most plugin PR review comments trace back to one of these.

If the plugin needs a new system package or Python dependency, mirroring it into the root `Dockerfile`/`requirements.txt` alone is not enough: see the Conventions Checklist's build-target-mirroring bullet for `.devcontainer/Dockerfile` (regenerate via `.devcontainer/scripts/generate-configs.sh`, don't hand-edit it), `Dockerfile.debian`, and `install/ubuntu24`/`install/proxmox`'s own `requirements.txt` files.

## Starting Point

Copy from `server/plugins/__template` and customize.
