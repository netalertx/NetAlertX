---
name: netalertx-code-standards
description: NetAlertX coding standards and conventions. Use this when writing code, reviewing code, or implementing features.
---

# Code Standards

## File Length

Keep code files under 500 lines. Split larger files into modules.

## DRY Principle

Do not re-implement functionality. Reuse existing methods or refactor to create shared methods.

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

Use sanitizers from `server/helper.py` before storing user input.

## Devcontainer Constraints

- Never `chmod` or `chown` during operations
- Everything is already writable
- If permissions needed, fix `.devcontainer/scripts/setup.sh`

## Path Hygiene

- Use environment variables for runtime paths
- `/data` for persistent config/db
- `/tmp` for runtime logs/api/nginx state
- Never hardcode `/data/db` or use relative paths
