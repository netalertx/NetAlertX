---
name: incident-debugging
description: Methodology for diagnosing a recurring crash or bug with no direct evidence (no traceback, ambiguous logs). Use this before building a fix on top of a log-correlation theory.
---

# Incident Debugging

## Core Principle: Get a Traceback Before Theorizing

When a recurring crash has no traceback, capturing one via the cheapest reliable mechanism is the first priority task - not a last resort tried after several theories built on indirect log evidence have failed. A log line that merely *correlates* with a crash (shows up nearby in time) is a lead to verify, not proof of cause - two symptoms of the same underlying load (e.g. a test suite hammering the API) can correlate perfectly without either causing the other.

A real case (a NetAlertX main-loop crash-loop investigation): ten findings were produced across several days. Eight of them were built on the theory that SQLite lock contention caused the crash, because a `"database is locked"` log line kept showing up near crash time. That correlation was real but not causal. The actual cause (an unguarded `print()` raising `BrokenPipeError` when stdout's reader went away - see `logging-standards`) was found within one round of finally capturing a real traceback.

## If a Diagnostic Mechanism Fails Mysteriously, Don't Give Up on the Goal - Try a Simpler One

A first attempt at traceback capture in that investigation used a `sys.excepthook`/`threading.excepthook` pair (a global hook). It failed silently in the real target environment for a reason never identified - not reproducible locally, failing even for its simplest possible test (a bare hook assignment, checked immediately). That failure got wrongly generalized to "a traceback isn't obtainable here," and the investigation reverted to indirect log inference for several more rounds instead of trying a structurally different, simpler mechanism immediately.

**Prefer a plain `try/except` in normal control flow over a global hook for crash capture.** A `try/except` around a call is a basic language guarantee - Python *will* catch whatever that call raises. A hook (`sys.excepthook`, a signal handler, monkeypatching a method) is a runtime-configurable piece of global state whose "did it actually take effect" is a separate question from "does the logic inside it work," and that extra failure mode is exactly what made the first attempt undiagnosable. When the hook-based attempt failed, the fix was to wrap the single top-level entrypoint call (`if __name__ == "__main__": sys.exit(_wrapper())`) in a plain `try/except Exception`, log `traceback.format_exc()` synchronously, and re-raise. It worked on the first real attempt.

## Verify Which Process Actually Produced a Log Line Before Trusting It

See `logging-standards`' "shared, untagged sink" section - `app.log` is written by the main backend, every plugin subprocess, and any test using an in-process Flask test client, with no PID or process tag. Before citing a log line as evidence about a specific process's behavior, check which code path actually produces that exact message (grep the literal text, check which test exercises that route) rather than assuming from timing alone.

## Diagnostic Writes Must Survive the Crash They're Documenting

- Use a **synchronous** write (`open()`/`write()`/`close()`) for crash-path diagnostics, not an async-buffered logger. `server/logger.py`'s `mylog()` buffers through a queue flushed every 10 lines or on 1s idle - a fast subsequent crash can lose buffered lines, including the first one written right after a restart. A traceback written via plain file I/O at the moment of the exception doesn't have this problem.
- Don't let a routine, user-triggerable cleanup path (e.g. a "clear logs" endpoint) be able to erase crash evidence. A diagnostic log file that can be casually purged through the same mechanism used for everyday log hygiene isn't durable evidence - it's evidence that happens to survive only if nobody clears logs between the crash and when someone looks.
