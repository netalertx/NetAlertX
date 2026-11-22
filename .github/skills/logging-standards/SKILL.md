---
name: netalertx-logging-standards
description: Logging conventions for NetAlertX backend Python code. Use this when adding, modifying, or reviewing log statements.
---

# Logging Standards

## Import

```python
from logger import mylog
```

Never import `logging` directly in application code. Use `mylog` exclusively.

## Function Signature

```python
mylog(level, message_or_list)
```

`message_or_list` can be a plain string or a list of values — the logger joins them with spaces.

## Log Levels

Levels from least to most verbose (higher number = more output):

| Level | Numeric | When to use |
|-------|---------|-------------|
| `"none"` | 0 | Always printed regardless of user setting. Reserve for startup, fatal errors, and one-time permission checks. |
| `"minimal"` | 1 | Important state transitions visible by default (scan start/end, plugin finish, restart). |
| `"verbose"` | 2 | Informational progress — what the system is doing without clutter (e.g. "No changes to report"). |
| `"debug"` | 3 | Developer-level detail — loop decisions, branch taken, counts. |
| `"trace"` | 4 | Granular per-item tracing — individual device rows, SQL queries, raw values. |

## Message Format

Prefix every message with a `[Module]` tag matching the file/function context:

```python
mylog("debug", [f"[device_handling] Processing MAC: {mac}"])
mylog("verbose", ["[Scan] Scan complete — devices updated:", count])
```

Use `f-strings` inside a list element, not string concatenation:

```python
# Correct
mylog("debug", [f"[NIC] parent={parent_mac} nic_online={nic_online}"])

# Avoid
mylog("debug", "[NIC] parent=" + parent_mac + " nic_online=" + str(nic_online))
```

## Timestamp

`mylog` / `file_print` prepend the current local-timezone time automatically via `timeNowTZ`. Do **not** add a timestamp manually inside the message.

## What NOT to Log

- Do not log raw user input without sanitization.
- Do not log full SQL query strings at `"none"` or `"minimal"` — use `"trace"` at most.
- Do not use `print()` in server code — use `mylog`. `file_print` is an internal helper; do not call it directly.

## Log File Location

Written to `{logPath}/app.log` (`logPath` from `const.py` → `/tmp/logs` at runtime). Do not hardcode this path.

## `app.log` Is a Shared, Untagged Sink - Don't Assume Which Process Wrote a Line

Every process that calls `mylog()` writes to the same `app.log` with no PID or process tag: the main backend, every plugin subprocess (`server/plugin.py` runs each plugin script as its own `python3` subprocess, each doing its own `DB(); db.open()`), and - easy to miss - any test using Flask's in-process `app.test_client()` (e.g. `test/scan/test_device_field_lock.py`), which exercises real view functions and real DB writes with no network socket at all. A suspicious log line's mere presence near a crash or bug is not evidence about which process produced it - check which code path actually generates that exact line (grep the message text, check which test exercises that route) before treating it as proof about the main backend's own behavior. A real investigation spent multiple rounds treating a `"[Database] - Open DB Error"` cluster as evidence the main backend was crashing from DB lock contention, when it was actually pytest's own in-process test client hitting real SQLite contention under heavy concurrent test load - a coincidental correlation, not the crash's cause.

## `print()` to stdout Can Legitimately Fail

`file_print()`'s `print(result)` is wrapped in `except BrokenPipeError: pass` - stdout's reader (a `docker logs` consumer, a supervisor) can go away mid-run, and losing that echo is harmless (the real persistence path is the file write via `log_writer()`'s queue, logged immediately before). An unguarded `print()` here previously crashed the *entire main loop* over a closed pipe, with a traceback that has nothing to do with whatever `mylog()` call happened to trigger it - don't remove this guard, and don't add a new unguarded `print()` call anywhere else in server code for the same reason (this is why `file_print` is a pre-existing internal helper, not a reason to add a second print path).
