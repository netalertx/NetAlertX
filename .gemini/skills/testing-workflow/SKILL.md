---
name: testing-workflow
description: Read before running tests. Detailed instructions for single, standard unit tests (fast), full suites (slow), handling authentication, and obtaining the API Token. Tests must be run when a job is complete.
---

# Testing Workflow
After code is developed, tests must be run to ensure the integrity of the final result.

**Crucial:** Tests MUST be run inside the container to access the correct runtime environment (DB, Config, Dependencies).

## 0. Pre-requisites: Environment Check

Before running any tests, verify you are inside the development container:

```bash
ls -d /workspaces/NetAlertX
```

**IF** this directory does not exist, you are likely on the host machine. You **MUST** immediately activate the `devcontainer-management` skill to enter the container or run commands inside it.

```text
activate_skill("devcontainer-management")
```

## 1. Full Test Suite (MANDATORY DEFAULT)

Unless the user **explicitly** requests "fast" or "quick" tests, you **MUST** run the full test suite. **Do not** optimize for time. Comprehensive coverage is the priority over speed.

```bash
cd /workspaces/NetAlertX; pytest test/
```

## 2. Fast Unit Tests (Conditional)

**ONLY** use this if the user explicitly asks for "fast tests", "quick tests", or "unit tests only". This **excludes** slow tests marked with `docker` or `feature_complete`.

```bash
cd /workspaces/NetAlertX; pytest test/ -m 'not docker and not feature_complete'
```

## 3. Running Specific Tests

To run a specific file or folder:

```bash
cd /workspaces/NetAlertX; pytest test/<path_to_test>
```

*Example:*
```bash
cd /workspaces/NetAlertX; pytest test/api_endpoints/test_mcp_extended_endpoints.py
```

## Authentication & Environment Reset

Authentication tokens are required to perform certain operations such as manual testing or crafting expressions to work with the web APIs. After making code changes, you MUST reset the environment to ensure the new code is running and verify you have the latest `API_TOKEN`.

1. **Reset Environment:** Run the setup script inside the container.
   ```bash
   bash /workspaces/NetAlertX/.devcontainer/scripts/setup.sh
   ```
2. **Wait for Stabilization:** Wait at least 5 seconds for services (nginx, python server, etc.) to start.
   ```bash
   sleep 5
   ```
3. **Obtain Token:** Retrieve the current token from the container.
   ```bash
   python3 -c "from helper import get_setting_value; print(get_setting_value('API_TOKEN'))"
   ```

The retrieved token MUST be used in all subsequent API or test calls requiring authentication.

### Troubleshooting

If tests fail with 403 Forbidden or empty tokens:
1. Verify server is running and use the setup script (`/workspaces/NetAlertX/.devcontainer/scripts/setup.sh`) if required.
2. Verify `app.conf` inside the container: `cat /data/config/app.conf`

## Check for Pre-Existing Failures

Before attributing failures to your changes, check what was already broken:

```bash
cd /workspaces/NetAlertX; pytest test/ --tb=no -q 2>&1 | tail -20
```

Do not fix pre-existing failures unless that is the explicit goal.

## PYTHONPATH

The test environment is pre-configured with:
- `/app` — primary location where Python runs in production
- `/app/server` — symlink to `/workspaces/NetAlertX/server`
- `/app/server/plugins` — symlink to `/workspaces/NetAlertX/server/plugins`
- `/opt/venv/lib/pythonX.Y/site-packages`
- `/workspaces/NetAlertX/test`
- `/workspaces/NetAlertX/server`
- `/workspaces/NetAlertX`
- `/usr/lib/pythonX.Y/site-packages`

## Docker Test Image

If the Dockerfile or dependencies changed, rebuild the test image before running:

```bash
docker buildx build -t netalertx-test .
```

Takes ~30 seconds; ~90 seconds if the venv stage changed.

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
