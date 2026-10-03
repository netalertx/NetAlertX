---
name: netalertx-code-standards
description: NetAlertX coding standards and conventions. Use this when writing code, reviewing code, or implementing features.
---

# Code Standards

- ask me to review before going to each next step (mention n step out of x)  (AI only)
- before starting, prepare implementation plan  (AI only)
- ask me to review it and ask any clarifying questions first
- add test creation as last step - follow repo architecture patterns - do not place in the root of `/test`
- code has to be maintainable, no duplicate code
- follow DRY principle - maintainability of code is more important than speed of implementation
- code files should be less than 500 LOC for better maintainability
- DB columns must not contain underscores, use camelCase instead (e.g., deviceInstanceId, not device_instance_id)
- treat DB as temporary storage for stats, long-term configuration should be stored in the `/config` folder, the `/config` folder should allow you to restore most of your functionality (excluding historical data)
- never access DB directly from application layers, always use helper functions in `server/db/db_helper.py` and implement new functionality in handlers (e.g., `DeviceInstance` in `server/models/device_instance.py`)
- always validate and normalize MAC addresses before writing to DB (use `normalize_mac` from `plugin_helper.py`)
- all subprocess calls must set explicit timeouts
- use `timeNowUTC` from `utils.datetime_utils` for all time-related operations and DB timestamps (store all timestamps in UTC)
- use sanitizers from `server/helper.py` for user input before storing in DB
- reuse shared mocks and factories from `test/db_test_helpers.py` for tests, never redefine them locally
- use environment variables for runtime paths, never hardcode paths or use relative paths
- follow existing code style and structure, and ensure backward compatibility with existing installations when submitting PRs
- all code needs to be scalable to handle large networks with thousands of devices (10k+) without performance degradation
- no inline imports, all imports must be at the top of the file
- when using `server/logger.py` `mylog()`, only use valid levels: `none`, `minimal`, `verbose`, `debug`, `trace`; invalid levels silently degrade to `none`
- every Python function/method needs a succinct docstring describing its current use and behavior — not what changed or why (see Docstrings section below)
- before adding a new frontend language string, search `front/php/templates/language/en_us.json` for an existing key with the same text/purpose and reuse it — don't add a near-duplicate key just because it's needed on a new page (see Language Strings section below)
- never add new server-side PHP logic (a new endpoint, new computation inside an existing PHP file) — `front/` is being migrated away from PHP, so any new backend state/computation belongs in the Python server, exposed to the frontend via an existing read path (see PHP/Python Boundary section below)


## File Length

Keep code files under 500 lines. Split larger files into modules.

## DRY Principle

Do not re-implement functionality. Reuse existing methods or refactor to create shared methods.

**This is a required pre-step, not a cleanup pass to do later.** Before writing any new check/condition/helper, search for an existing implementation of the same or similar logic first - grep the codebase, and read the *whole* file you're already touching, not just the section being edited. If something equivalent exists, extract it into a shared function and call it from the new site instead of writing a parallel implementation.

A real case this was missed on: a new frontend indicator needed to know "is the backend still applying a settings change." That exact check already existed inline in `settings.php`'s own polling loop (`handleLoadingDialog()`, further down the same file being edited) - it took two rounds of reinventing it elsewhere (a cookie-based guess, then a duplicate PHP endpoint computing the same thing a second time) before it got extracted into one shared function (`isSettingsPending()` in `common.js`) that both the original page and the new consumer call. Read the existing code first; refactor into something reusable *while* implementing, not after a reviewer points out the duplication.

## Database Access

- Never access DB directly from application layers
- Use `server/db/db_helper.py` functions (e.g., `get_table_json`)
- Implement new functionality in handlers (e.g., `DeviceInstance` in `server/models/device_instance.py`)

## MAC Address Handling

Always validate and normalize MACs before DB writes:

```python
from plugin_helper import normalize_mac

mac = normalize_mac(raw_mac)
```

## Subprocess Safety

**MANDATORY:** All subprocess calls must set explicit timeouts.

```python
result = subprocess.run(cmd, timeout=60)  # Minimum 60s
```

Nested subprocess calls need their own timeout—outer timeout won't save you.

## Time Utilities

```python
from utils.datetime_utils import timeNowUTC

timestamp = timeNowUTC()
```

This is the ONLY function that calls datetime.datetime.now() in the entire codebase.

⚠️ CRITICAL: ALL database timestamps MUST be stored in UTC
This is the SINGLE SOURCE OF TRUTH for current time in NetAlertX
Use timeNowUTC() for DB writes (returns UTC string by default)
Use timeNowUTC(as_string=False) for datetime operations (scheduling, comparisons, logging)

## String Sanitization

Use sanitizers from `server/helper.py` before storing user input. MAC addresses are always lowercased and normalized. IP addresses should be validated.

## Docstrings

Every Python function/method gets a docstring — one or two sentences, describing what it does and how it's used *right now*. Not a changelog:

```python
# Correct
def count_children_by_parent_mac(devices):
    """Return {parentMac: childCount} for the given device list, keyed by devParentMAC."""

# Wrong — narrates the diff instead of the current behavior
def count_children_by_parent_mac(devices):
    """Replaces the old get_number_of_children() to fix the O(n^2) scan."""
```

That history belongs in the commit message or PR description, not the docstring — it rots the moment the next change lands. Keep it succinct; only go past a couple of lines when the contract genuinely needs it (non-obvious return shape, units, a caller-visible side effect).

## Language Strings — Reuse Before Adding (DRY)

Before adding a new key to `front/php/templates/language/en_us.json`, grep it for an existing key with the same text or purpose and reuse that key instead of adding a near-duplicate:

```bash
grep -n "\"Gen_" front/php/templates/language/en_us.json   # generic, reusable strings
grep -n "Next\|Previous\|Showing" front/php/templates/language/en_us.json
```

Prefer the generic `Gen_*` keys (e.g. `Gen_Prev`, `Gen_Next`) over a page-scoped name (`Presence_Page_Prev`) for genuinely generic UI text — a future page needing the same label should find it already there. Only add a new key when nothing existing fits; only that one file needs the addition — `getString()`/`lang()` fall back to the English string for any locale missing a key, so the other ~23 locale files don't need touching.

## PHP/Python Boundary — No New PHP Backend Logic

`front/` is being migrated away from PHP. Never add a new PHP endpoint, or new server-side computation inside an existing PHP file - if a feature needs backend state or computation, it belongs in the Python server (`server/`), exposed to the frontend through an existing read path:

- `app_state.json`, read via the generic `front/php/server/query_json.php` file-passthrough (no settings/state-specific logic lives in that file - it just serves raw JSON)
- `table_settings.json` (same passthrough)
- an existing REST or GraphQL endpoint

A real case this was caught on: a new "settings still applying" UI indicator needed to know whether the backend had caught up on a config reload. The correct signal (`showSpinner` state + a config-file-mtime comparison) already existed in Python (`server/initialise.py`'s `importConfigs()`) - the first draft instead re-derived the same comparison in a new PHP endpoint, duplicating logic that the Python backend already computed and should have just exposed into existing shared state.

Editing *existing* PHP page logic - templating, fixing a bug like a broken `explode()` parse, wiring up a new `<div>` - is fine and expected during the migration period. This rule is about not growing the PHP surface area with new backend-side logic, not about avoiding PHP entirely.

## No Test Harness? Simulate Before Asking for a Live Test

`front/` has no automated JS/PHP test suite. That makes it *more* important to verify a change before calling it done, not less - without a harness, "the user tests it live" becomes the only feedback loop, and that loop is slow and expensive (a real save, a real scan cycle, real timing) compared to a throwaway script.

Before telling anyone a JS/PHP change is ready to test: write a small disposable Node (or PHP CLI) script that extracts the actual function(s) involved and runs them against realistic inputs - including the inputs that come from a different code path than the one being edited (a real `app_state.json` sample, a real cookie value, a renamed parameter actually being passed through). Do this on the *first* attempt, not after a live test comes back broken.

A real case: a settings-reload indicator went through several rounds of "should work" before any of its logic was actually run. A standalone simulation run at that point would have immediately caught a renamed-parameter typo that a diff review missed, and an ordering bug (a cookie needing to clear before a reload fires, not inside the reload's own callback) - both found only after a live test failed, when a five-line script could have found them in seconds.

## Devcontainer Constraints

- Never `chmod` or `chown` during operations
- Everything is already writable
- If permissions needed, fix `.devcontainer/scripts/setup.sh`

## Test Helpers — No Duplicate Mocks

Reuse shared mocks and factories from `test/db_test_helpers.py`. Never redefine `DummyDB`, `make_db`, or inline DDL in individual test files.

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db_test_helpers import make_db, DummyDB, insert_device, minutes_ago
```

If a helper you need doesn't exist yet, add it to `db_test_helpers.py` — not locally in the test file.

## Stubbing Modules in Standalone-Capable Tests

If a test stubs NetAlertX modules into `sys.modules` so a script can be imported
outside the container (see `test/plugins/test_ntfy_custom_headers.py`), pop each
stubbed name back out of `sys.modules` right after the one-time import that needed
it. Otherwise the fake module leaks into every other test file collected in the
same pytest session and shadows the real module (see `testing-workflow` skill for
the full pattern and reproduction steps).

## MAC Literals in Tests — ALWAYS Lowercase

**MANDATORY:** Every MAC address literal used in test fixtures, parametrize decorators, assertions, or comments must be lowercase hex:

```python
# Correct
make_device_dict("aa:bb:cc:dd:ee:01", ...)

# Wrong — will be rejected in review
make_device_dict("AA:BB:CC:DD:EE:01", ...)
make_device_dict("Aa:Bb:Cc:Dd:Ee:01", ...)
```

This applies to hardcoded strings in `assert`, `pytest.mark.parametrize`, docstrings, and comments too. There are no exceptions.

## Path Hygiene

- Use environment variables for runtime paths
- `/data` for persistent config/db
- `/tmp` for runtime logs/api/nginx state
- Never hardcode `/data/db` or use relative paths
