---
name: netalertx-testing-workflow
description: Run and debug tests in the NetAlertX devcontainer. Use this when asked to run tests, check test failures, debug failing tests, or execute pytest.
---

# Testing Workflow

## Pre-Flight Check (MANDATORY)

Before running any tests, always check for existing failures first:

1. Use the `testFailure` tool to gather current failure information
2. Review the failures to understand what's already broken
3. Only then proceed with test execution

## Running Tests

Use VS Code's testing interface or the `runTests` tool with appropriate parameters:

- To run all tests: invoke runTests without file filter
- To run specific test file: invoke runTests with the test file path
- To run failed tests only: invoke runTests with `--lf` flag

## Test Location

Tests live in `test/` directory. App code is under `server/`.

PYTHONPATH is preconfigured to include the following which should meet all needs:
- `/app` # the primary location where python runs in the production system
- `/app/server` # symbolic link to /wprkspaces/NetAlertX/server
- `/app/server/plugins` # symbolic link to /workspaces/NetAlertX/server/plugins
- `/opt/venv/lib/pythonX.Y/site-packages`
- `/workspaces/NetAlertX/test`
- `/workspaces/NetAlertX/server`
- `/workspaces/NetAlertX`
- `/usr/lib/pythonX.Y/site-packages`

## Authentication in Tests

Retrieve `API_TOKEN` using Python (not shell):

```python
from helper import get_setting_value
token = get_setting_value("API_TOKEN")
```

## Troubleshooting 403 Forbidden

1. Ensure backend is running (use devcontainer-services skill)
2. Verify config loaded: `get_setting_value("API_TOKEN")` returns non-empty
3. Re-run startup if needed (use devcontainer-setup skill)

## Docker Test Image

If container changes affect tests, rebuild the test image first:

```bash
docker buildx build -t netalertx-test .
```

This takes ~30 seconds unless venv stage changes (~90s).

## Pitfall: `sys.modules` Stubbing Leaks Across Test Files

Some plugin tests (e.g. `test/plugins/test_ntfy_custom_headers.py`) stub NetAlertX
modules (`conf`, `helper`, `models.notification_instance`, etc.) via
`sys.modules[name] = fake_module` so the plugin script can be imported standalone,
outside the container. Because `sys.modules` is a single process-wide cache shared
by the whole pytest session, a fake module inserted by one test file silently
shadows the real module for every other test file collected afterwards — pytest
imports all test files during collection, before any test runs, so this can happen
regardless of alphabetical/directory order.

Symptom: `AttributeError: <module 'models.notification_instance'> does not have
the attribute 'get_setting_value'` (or similar) in an unrelated test file, where
the module repr has no `from '<path>'` suffix — a giveaway that a stub, not the
real module, was resolved.

Fix pattern: track which module names your stub actually inserted, and pop them
back out of `sys.modules` immediately after the one-time import that needed them
(the already-imported script keeps its bound names regardless):

```python
_stubbed_module_names = []

def _stub(name, **attrs):
    if name not in sys.modules:
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
        _stubbed_module_names.append(name)

# ... _stub(...) calls, then the one-time import ...
import ntfy

for _name in _stubbed_module_names:
    sys.modules.pop(_name, None)
```

test_ntfy_custom_headers.py already pops its stubs back out (see the fix
pattern above), so running it alongside test_notification_templates.py now is
a regression check that pollution doesn't recur - not a reproduction of the
original bug, which this specific pair no longer has:

```bash
pytest test/plugins/test_ntfy_custom_headers.py test/backend/test_notification_templates.py -v
```

To actually reproduce pollution (a different file that still stubs and never
pops), first confirm the stub survives - e.g. import the suspect file alone,
then check `sys.modules` for the name it stubbed - before pairing it with a
second file; don't assume any filename resembling this example will show the
same leak.
