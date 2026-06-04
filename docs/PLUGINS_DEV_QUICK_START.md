# Plugin Development Quick Start

Get a working plugin up and running in 5 minutes.

## Prerequisites

- Read [Development Environment Setup Guide](./DEV_ENV_SETUP.md) to set up your local environment
- Understand [Plugin Architecture Overview](PLUGINS_DEV.md)

## Quick Start Steps

### 1. Create Your Plugin Folder

Start from the template to get the basic structure:

```bash
cd /workspaces/NetAlertX/front/plugins
cp -r __template my_plugin
cd my_plugin
```

### 2. Update `config.json` Identifiers

Edit `my_plugin/config.json` and update these critical fields:

```json
{
  "code_name": "my_plugin",
  "unique_prefix": "MYPLN",
  "display_name": [{"language_code": "en_us", "string": "My Plugin"}],
  "description": [{"language_code": "en_us", "string": "My custom plugin"}]
}
```

**Important:**
- `code_name` must match the folder name
- `unique_prefix` must be unique and uppercase (check existing plugins to avoid conflicts)
- `unique_prefix` is used as a prefix for all generated settings (e.g., `MYPLN_RUN`, `MYPLN_CMD`)

### 3. Implement Your Script

Edit `my_plugin/script.py` and implement your data collection logic:

```python
#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../server'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../plugins'))

from plugin_helper import Plugin_Objects, mylog
from helper import get_setting_value
from const import logPath

pluginName = "MYPLN"

LOG_PATH = logPath + "/plugins"
LOG_FILE = os.path.join(LOG_PATH, f"script.{pluginName}.log")
RESULT_FILE = os.path.join(LOG_PATH, f"last_result.{pluginName}.log")

# Initialize
plugin_objects = Plugin_Objects(RESULT_FILE)

try:
    # Your data collection logic here
    # For example, scan something and collect results

    # Add an object to results
    plugin_objects.add_object(
        objectPrimaryId="example_id",
        objectSecondaryId=None,
        DateTime="2023-01-02 15:56:30",
        watchedValue1="value1",
        watchedValue2=None,
        watchedValue3=None,
        watchedValue4=None,
        Extra="additional_data",
        ForeignKey=None
    )

    # Write results to the log file
    plugin_objects.write_result_file()

except Exception as e:
    mylog("none", f"Error: {e}")
    sys.exit(1)
```

### 4. Configure Execution

Edit the `RUN` and `CMD` settings in `config.json`:

```json
{
  "function": "RUN",
  "type": {"dataType":"string", "elements": [{"elementType": "select", "elementOptions": [], "transformers": []}]},
  "default_value": "disabled",
  "options": ["disabled", "once", "schedule"],
  "localized": ["name", "description"],
  "name": [{"language_code":"en_us", "string": "When to run"}],
  "description": [{"language_code":"en_us", "string": "Enable plugin execution"}]
},
{
  "function": "CMD",
  "type": {"dataType":"string", "elements": [{"elementType": "input", "elementOptions": [], "transformers": []}]},
  "default_value": "python3 /app/front/plugins/my_plugin/script.py",
  "localized": ["name", "description"],
  "name": [{"language_code":"en_us", "string": "Command"}],
  "description": [{"language_code":"en_us", "string": "Command to execute"}]
}
```

### 5. Test Your Plugin

#### In Dev Container

```bash
# Test the script directly
python3 /workspaces/NetAlertX/front/plugins/my_plugin/script.py

# Check the results
cat /tmp/log/plugins/last_result.MYPLN.log
```

#### Via UI

1. Restart backend: Run task `[Dev Container] Start Backend (Python)`
2. Open Settings → Plugin Settings → My Plugin
3. Set `My Plugin - When to run` to `once`
4. Click Save
5. Check `/tmp/log/plugins/last_result.MYPLN.log` for output

### 6. Check Results

Verify your plugin is working:

```bash
# Check if result file was generated
ls -la /tmp/log/plugins/last_result.MYPLN.log

# View contents
cat /tmp/log/plugins/last_result.MYPLN.log

# Check backend logs for errors
tail -f /tmp/log/stdout.log | grep "my_plugin\|MYPLN"
```

## Next Steps

Now that you have a working basic plugin:

1. **Add Settings**: Customize behavior via user-configurable settings (see [PLUGINS_DEV_SETTINGS.md](PLUGINS_DEV_SETTINGS.md))
2. **Implement Data Contract**: Structure your output correctly (see [PLUGINS_DEV_DATA_CONTRACT.md](PLUGINS_DEV_DATA_CONTRACT.md))
3. **Configure UI**: Display plugin results in the web interface (see [PLUGINS_DEV_UI_COMPONENTS.md](PLUGINS_DEV_UI_COMPONENTS.md))
4. **Map to Database**: Import data into NetAlertX tables like `CurrentScan` or `Devices`
5. **Set Schedules**: Run your plugin on a schedule (see [PLUGINS_DEV_CONFIG.md](PLUGINS_DEV_CONFIG.md))

## Common Issues

| Issue | Solution |
|-------|----------|
| "Module not found" errors | Ensure `sys.path` includes `/app/server` and `/app/front/plugins` |
| Settings not appearing | Restart backend and clear browser cache |
| Results not showing up | Check `/tmp/log/plugins/*.log` and `/tmp/log/stdout.log` for errors |
| Permission denied | Plugin runs in container, use absolute paths like `/app/front/plugins/...` |

## Resources

- [Full Plugin Development Guide](PLUGINS_DEV.md)
- [Plugin Data Contract](PLUGINS_DEV_DATA_CONTRACT.md)
- [Plugin Settings System](PLUGINS_DEV_SETTINGS.md)
- [Data Sources](PLUGINS_DEV_DATASOURCES.md)
- [UI Components](PLUGINS_DEV_UI_COMPONENTS.md)
- [Debugging Plugins](DEBUG_PLUGINS.md)
