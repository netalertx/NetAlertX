---
name: netalertx-settings-management
description: Manage NetAlertX configuration settings. Use this when asked to add setting, read config, get_setting_value, ccd, or configure options.
---

# Settings Management

## Reading Settings

```python
from helper import get_setting_value

value = get_setting_value('SETTING_NAME')
```

Never hardcode ports, secrets, or configuration values. Always use `get_setting_value()`.

## Adding Core Settings

Use `ccd()` in `server/initialise.py`:

```python
ccd('SETTING_NAME', 'default_value', 'description')
```

## Adding Plugin Settings

Define in plugin's `config.json` manifest under the settings section.

## Config Files

| File | Purpose |
|------|---------|
| `/data/config/app.conf` | Runtime config (modified by app) |
| `back/app.conf` | Default config (template) |

## Environment Override

Use `APP_CONF_OVERRIDE` environment variable for settings that must be set before startup.
