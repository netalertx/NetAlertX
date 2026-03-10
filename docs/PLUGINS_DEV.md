# Plugin Development Guide

This comprehensive guide covers how to build plugins for NetAlertX.

> [!TIP]
> **New to plugin development?** Start with the [Quick Start Guide](PLUGINS_DEV_QUICK_START.md) to get a working plugin in 5 minutes.

NetAlertX comes with a plugin system to feed events from third-party scripts into the UI and then send notifications, if desired. The highlighted core functionality this plugin system supports:

* **Dynamic UI generation** - Automatically create tables for discovered objects
* **Data filtering** - Filter and link values in the Devices UI
* **User settings** - Surface plugin configuration in the Settings UI
* **Rich display types** - Color-coded badges, links, formatted text, and more
* **Database integration** - Import plugin data into NetAlertX tables like `CurrentScan` or `Devices`

> [!NOTE]
> For a high-level overview of how the `config.json` is used and its lifecycle, see the [config.json Lifecycle Guide](PLUGINS_DEV_CONFIG.md).

## Quick Links

### 🚀 Getting Started
- **[Quick Start Guide](PLUGINS_DEV_QUICK_START.md)** - Create a working plugin in 5 minutes
- **[Development Environment Setup](./DEV_ENV_SETUP.md)** - Set up your local development environment

### 📚 Core Concepts
- **[Data Contract](PLUGINS_DEV_DATA_CONTRACT.md)** - The exact output format plugins must follow (9-13 columns, pipe-delimited)
- **[Data Sources](PLUGINS_DEV_DATASOURCES.md)** - How plugins retrieve data (scripts, databases, templates)
- **[Plugin Settings System](PLUGINS_DEV_SETTINGS.md)** - Let users configure your plugin via the UI
- **[UI Components](PLUGINS_DEV_UI_COMPONENTS.md)** - Display plugin results with color coding, links, and more

### 🏗️ Architecture
- **[Plugin Config Lifecycle](PLUGINS_DEV_CONFIG.md)** - How `config.json` is loaded and used
- **[Full Plugin Development Reference](#full-reference-below)** - Comprehensive details on all aspects

### 🐛 Troubleshooting
- **[Debugging Plugins](DEBUG_PLUGINS.md)** - Troubleshoot plugin issues
- **[Plugin Examples](https://github.com/netalertx/NetAlertX/tree/main/front/plugins)** - Study existing plugins as reference implementations

### 🎥 Video Tutorial

[![Watch the video](./img/YouTube_thumbnail.png)](https://youtu.be/cdbxlwiWhv8)

### 📸 Screenshots

| ![Screen 1][screen1] | ![Screen 2][screen2] | ![Screen 3][screen3] |
|----------------------|----------------------| ----------------------|
| ![Screen 4][screen4] |  ![Screen 5][screen5] |

## Use Cases

Plugins are infinitely flexible. Here are some examples:

* **Device Discovery** - Scan networks using ARP, mDNS, DHCP leases, or custom protocols
* **Service Monitoring** - Monitor web services, APIs, or network services for availability
* **Integration** - Import devices from PiHole, Home Assistant, Unifi, or other systems
* **Enrichment** - Add data like geolocation, threat intelligence, or asset metadata
* **Alerting** - Send notifications to Slack, Discord, Telegram, email, or webhooks
* **Reporting** - Generate insights from existing NetAlertX database (open ports, recent changes, etc.)
* **Custom Logic** - Create fake devices, trigger automations, or implement custom heuristics

If you can imagine it and script it, you can build a plugin.

## Limitations & Notes

- Plugin data is deduplicated hourly (same Primary ID + Secondary ID + User Data = duplicate removed)
- Currently, only `CurrentScan` table supports update/overwrite of existing objects
- Plugin results must follow the strict [Data Contract](PLUGINS_DEV_DATA_CONTRACT.md)
- Plugins run with the same permissions as the NetAlertX process
- External dependencies must be installed in the container

## Plugin Development Workflow

### Step 1: Understand the Basics
1. Read [Quick Start Guide](PLUGINS_DEV_QUICK_START.md) - 5 minute overview
2. Study the [Data Contract](PLUGINS_DEV_DATA_CONTRACT.md) - Understand the output format
3. Choose a [Data Source](PLUGINS_DEV_DATASOURCES.md) - Where does your data come from?

### Step 2: Create Your Plugin
1. Copy the `__template` plugin folder (see below for structure)
2. Update `config.json` with your plugin metadata
3. Implement `script.py` (or configure alternative data source)
4. Test locally in the devcontainer

### Step 3: Configure & Display
1. Define [Settings](PLUGINS_DEV_SETTINGS.md) for user configuration
2. Design [UI Components](PLUGINS_DEV_UI_COMPONENTS.md) for result display
3. Map to database tables if needed (for notifications, etc.)

### Step 4: Deploy & Test
1. Restart the backend
2. Test via Settings → Plugin Settings
3. Verify results in UI and logs
4. Check `/tmp/log/plugins/last_result.<PREFIX>.log`

See [Quick Start Guide](PLUGINS_DEV_QUICK_START.md) for detailed step-by-step instructions.

## Plugin File Structure

Every plugin lives in its own folder under `/app/front/plugins/`.

> **Important:** Folder name must match the `"code_name"` value in `config.json`

```
/app/front/plugins/
├── __template/          # Copy this as a starting point
│   ├── config.json      # Plugin manifest (configuration)
│   ├── script.py        # Your plugin logic (optional, depends on data_source)
│   └── README.md        # Setup and usage documentation
├── my_plugin/           # Your new plugin
│   ├── config.json      # REQUIRED - Plugin manifest
│   ├── script.py        # OPTIONAL - Python script (if using script data source)
│   ├── README.md        # REQUIRED - Documentation for users
│   └── other_files...   # Your supporting files
```

## Plugin Manifest (config.json)

The `config.json` file is the **plugin manifest** - it tells NetAlertX everything about your plugin:

- **Metadata:** Plugin name, description, icon
- **Execution:** When to run, what command to run, timeout
- **Settings:** User-configurable options
- **Data contract:** Column definitions and how to display results
- **Integration:** Database mappings, notifications, filters

**Example minimal config.json:**

```json
{
  "code_name": "my_plugin",
  "unique_prefix": "MYPLN",
  "display_name": [{"language_code": "en_us", "string": "My Plugin"}],
  "description": [{"language_code": "en_us", "string": "My awesome plugin"}],
  "icon": "fa-plug",
  "data_source": "script",
  "execution_order": "Layer_0",
  "settings": [
    {
      "function": "RUN",
      "type": {"dataType": "string", "elements": [{"elementType": "select", "elementOptions": [], "transformers": []}]},
      "default_value": "disabled",
      "options": ["disabled", "once", "schedule"],
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "When to run"}]
    },
    {
      "function": "CMD",
      "type": {"dataType": "string", "elements": [{"elementType": "input", "elementOptions": [], "transformers": []}]},
      "default_value": "python3 /app/front/plugins/my_plugin/script.py",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "Command"}]
    }
  ],
  "database_column_definitions": []
}
```

> For comprehensive `config.json` documentation, see [PLUGINS_DEV_CONFIG.md](PLUGINS_DEV_CONFIG.md)

## Full Reference (Below)

The sections below provide complete reference documentation for all plugin development topics. Use the quick links above to jump to specific sections, or read sequentially for a deep dive.

More on specifics below.

---

## Data Contract & Output Format

For detailed information on plugin output format, see **[PLUGINS_DEV_DATA_CONTRACT.md](PLUGINS_DEV_DATA_CONTRACT.md)**.

Quick reference:
- **Format:** Pipe-delimited (`|`) text file
- **Location:** `/tmp/log/plugins/last_result.<PREFIX>.log`
- **Columns:** 9 required + 4 optional = 13 maximum
- **Helper:** Use `plugin_helper.py` for easy formatting

### The 9 Mandatory Columns

| Column | Name | Required | Example |
|--------|------|----------|---------|
| 0 | Object_PrimaryID | **YES** | `"device_name"` or `"192.168.1.1"` |
| 1 | Object_SecondaryID | no | `"secondary_id"` or `null` |
| 2 | DateTime | **YES** | `"2023-01-02 15:56:30"` |
| 3 | Watched_Value1 | **YES** | `"online"` or `"200"` |
| 4 | Watched_Value2 | no | `"ip_address"` or `null` |
| 5 | Watched_Value3 | no | `null` |
| 6 | Watched_Value4 | no | `null` |
| 7 | Extra | no | `"additional data"` or `null` |
| 8 | ForeignKey | no | `"aa:bb:cc:dd:ee:ff"` or `null` |

See [Data Contract](PLUGINS_DEV_DATA_CONTRACT.md) for examples, validation, and debugging tips.

---

## Config.json: Settings & Configuration

For detailed settings documentation, see **[PLUGINS_DEV_SETTINGS.md](PLUGINS_DEV_SETTINGS.md)** and **[PLUGINS_DEV_DATASOURCES.md](PLUGINS_DEV_DATASOURCES.md)**.

### Setting Object Structure

Every setting in your plugin has this structure:

```json
{
  "function": "UNIQUE_CODE",
  "type": {"dataType": "string", "elements": [...]},
  "default_value": "...",
  "options": [...],
  "localized": ["name", "description"],
  "name": [{"language_code": "en_us", "string": "Display Name"}],
  "description": [{"language_code": "en_us", "string": "Help text"}]
}
```

### Reserved Function Names

These control core plugin behavior:

| Function | Purpose | Required | Options |
|----------|---------|----------|---------|
| `RUN` | When to execute | **YES** | `disabled`, `once`, `schedule`, `always_after_scan`, `before_name_updates`, `on_new_device` |
| `RUN_SCHD` | Cron schedule | If `RUN=schedule` | Cron format: `"0 * * * *"` |
| `CMD` | Command to run | **YES** | Shell command or script path |
| `RUN_TIMEOUT` | Max execution time | optional | Seconds: `"60"` |
| `WATCH` | Monitor for changes | optional | Column names |
| `REPORT_ON` | When to notify | optional | `new`, `watched-changed`, `watched-not-changed`, `missing-in-last-scan` |
| `DB_PATH` | External DB path | If using SQLite | `/path/to/db.db` |

See [PLUGINS_DEV_SETTINGS.md](PLUGINS_DEV_SETTINGS.md) for full component types and examples.

---

## Filters & Data Display

For comprehensive display configuration, see **[PLUGINS_DEV_UI_COMPONENTS.md](PLUGINS_DEV_UI_COMPONENTS.md)**.

### Filters

Control which rows display in the UI:

```json
{
  "data_filters": [
    {
      "compare_column": "Object_PrimaryID",
      "compare_operator": "==",
      "compare_field_id": "txtMacFilter",
      "compare_js_template": "'{value}'.toString()",
      "compare_use_quotes": true
    }
  ]
}
```

See [UI Components: Filters](PLUGINS_DEV_UI_COMPONENTS.md#filters) for full documentation.


---

## Database Mapping

To import plugin data into NetAlertX tables for device discovery or notifications:

```json
{
  "mapped_to_table": "CurrentScan",
  "database_column_definitions": [
    {
      "column": "Object_PrimaryID",
      "mapped_to_column": "scanMac",
      "show": true,
      "type": "device_mac",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "MAC Address"}]
    }
  ]
}
```

See [UI Components: Database Mapping](PLUGINS_DEV_UI_COMPONENTS.md#mapping-to-database-tables) for full documentation.

### Static Value Mapping

To always map a static value (not read from plugin output):

```json
{
  "column": "NameDoesntMatter",
  "mapped_to_column": "scanSourcePlugin",
  "mapped_to_column_data": {
    "value": "MYPLN"
  }
}
```

---

## UI Component Types

Plugin results are displayed in the web interface using various component types. See **[PLUGINS_DEV_UI_COMPONENTS.md](PLUGINS_DEV_UI_COMPONENTS.md)** for complete documentation.

### Common Display Types

**Read settings in your Python script:**

```python
from helper import get_setting_value

# Read a setting by code name (prefix + function)
api_url = get_setting_value('MYPLN_API_URL')
api_key = get_setting_value('MYPLN_API_KEY')
watch_columns = get_setting_value('MYPLN_WATCH')

print(f"Connecting to {api_url}")
```

**Pass settings as command parameters:**

Define `params` in config to pass settings as script arguments:

```json
{
  "params": [
    {
      "name": "api_url",
      "type": "setting",
      "value": "MYPLN_API_URL"
    }
  ]
}
```

Then use in `CMD`: `python3 script.py --url={api_url}`

See [PLUGINS_DEV_SETTINGS.md](PLUGINS_DEV_SETTINGS.md) for complete settings documentation, and [PLUGINS_DEV_DATASOURCES.md](PLUGINS_DEV_DATASOURCES.md) for data source details.

[screen1]: https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/docs/img/plugins.png                    "Screen 1"
[screen2]: https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/docs/img/plugins_settings.png           "Screen 2"
[screen3]: https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/docs/img/plugins_json_settings.png      "Screen 3"
[screen4]: https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/docs/img/plugins_json_ui.png            "Screen 4"
[screen5]: https://raw.githubusercontent.com/jokob-sk/NetAlertX/main/docs/img/plugins_device_details.png     "Screen 5"

## Quick Reference: Key Concepts

### Plugin Output Format
```
Object_PrimaryID|Object_SecondaryID|DateTime|Watched_Value1|Watched_Value2|Watched_Value3|Watched_Value4|Extra|ForeignKey
```
9 required columns, 4 optional helpers = 13 max

See: [Data Contract](PLUGINS_DEV_DATA_CONTRACT.md)

### Plugin Metadata (config.json)
```json
{
  "code_name": "my_plugin",           // Folder name
  "unique_prefix": "MYPLN",           // Settings prefix
  "display_name": [...],              // UI label
  "data_source": "script",            // Where data comes from
  "settings": [...],                  // User configurable
  "database_column_definitions": [...] // How to display
}
```

See: [Full Guide](PLUGINS_DEV.md), [Settings](PLUGINS_DEV_SETTINGS.md)

### Reserved Settings
- `RUN` - When to execute (disabled, once, schedule, always_after_scan, etc.)
- `RUN_SCHD` - Cron schedule
- `CMD` - Command/script to execute
- `RUN_TIMEOUT` - Max execution time
- `WATCH` - Monitor for changes
- `REPORT_ON` - Notification trigger

See: [Settings System](PLUGINS_DEV_SETTINGS.md)

### Display Types
`label`, `device_mac`, `device_ip`, `url`, `threshold`, `replace`, `regex`, `textbox_save`, and more.

See: [UI Components](PLUGINS_DEV_UI_COMPONENTS.md)

---

## Tools & References

- **Template Plugin:** `/app/front/plugins/__template/` - Start here!
- **Helper Library:** `/app/front/plugins/plugin_helper.py` - Use for output formatting
- **Settings Helper:** `/app/server/helper.py` - Use `get_setting_value()` in scripts
- **Example Plugins:** `/app/front/plugins/*/` - Study working implementations
- **Logs:** `/tmp/log/plugins/` - Plugin output and execution logs
- **Backend Logs:** `/tmp/log/stdout.log` - Core system logs

---


