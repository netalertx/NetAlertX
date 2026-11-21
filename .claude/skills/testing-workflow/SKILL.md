---
name: testing-workflow
description: Read before running tests. Detailed instructions for single tests, full suites, authentication, obtaining the API Token, and a real cross-test pollution pitfall. Use this when asked to run tests, check failures, or debug failing tests.
---

# Testing Workflow

**Crucial:** Tests MUST be run inside the devcontainer to access the correct runtime environment (DB, config, dependencies).

## 0. Pre-requisites: Environment Check

Before running any tests, verify you are inside the development container:

```bash
ls -d /workspaces/NetAlertX
```

If this directory does not exist, you are likely on the host machine — load the `devcontainer-management` skill (or its `.github`/`.gemini` equivalents) to enter the container or run commands inside it.

## 1. Check for Pre-Existing Failures First

Before attributing any failure to your own changes, see what was already broken:

```bash
cd /workspaces/NetAlertX; pytest test/ --tb=no -q 2>&1 | tail -20
```

Do not fix pre-existing failures unless that is the explicit goal.

## 2. Full Test Suite (default)

Unless the user explicitly asks for "fast"/"quick" tests, run the full suite. Don't optimize for time — comprehensive coverage is the priority.

```bash
cd /workspaces/NetAlertX; pytest test/
```

## 3. Fast Unit Tests (only when explicitly requested)

Excludes tests marked `docker` or `feature_complete`:

```bash
cd /workspaces/NetAlertX; pytest test/ -m 'not docker and not feature_complete'
```

## 4. Running Specific Tests

```bash
cd /workspaces/NetAlertX; pytest test/<path_to_test>
# e.g. pytest test/api_endpoints/test_mcp_extended_endpoints.py
# or a single test: pytest test/plugins/test_adguard_export.py::TestManagedNames::test_round_trip
```

## PYTHONPATH

Pre-configured with:
- `/app` — primary location where Python runs in production
- `/app/server`, `/app/server/plugins` — symlinks to `/workspaces/NetAlertX/server[/plugins]`
- `/opt/venv/lib/pythonX.Y/site-packages`, `/usr/lib/pythonX.Y/site-packages`
- `/workspaces/NetAlertX`, `/workspaces/NetAlertX/server`, `/workspaces/NetAlertX/test`

## Authentication & Environment Reset

After making code changes, reset the environment to pick up the new code and get a fresh `API_TOKEN`:

```bash
bash /workspaces/NetAlertX/.devcontainer/scripts/setup.sh
sleep 5   # let nginx/python server/etc. stabilize
python3 -c "from helper import get_setting_value; print(get_setting_value('API_TOKEN'))"
```

Use the retrieved token for any subsequent authenticated API/test calls.

### Troubleshooting 403 Forbidden / empty token

1. Confirm the server is running; re-run `setup.sh` if needed.
2. Verify config loaded: `cat /data/config/app.conf`, or `get_setting_value("API_TOKEN")` returns non-empty.

## Docker Test Image

If the Dockerfile or dependencies changed, rebuild before running tests:

```bash
docker buildx build -t netalertx-test .
```

~30 seconds normally, ~90 seconds if the venv stage changed.

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
