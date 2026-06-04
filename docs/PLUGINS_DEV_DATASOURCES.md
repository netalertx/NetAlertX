# Plugin Data Sources

Learn how to configure different data sources for your plugin.

## Overview

Data sources determine **where the plugin gets its data** and **what format it returns**. NetAlertX supports multiple data source types, each suited for different use cases.

| Data Source | Type | Purpose | Returns | Example |
|-------------|------|---------|---------|---------|
| `script` | Code Execution | Execute Linux commands or Python scripts | Pipeline | Scan network, collect metrics, call APIs |
| `app-db-query` | Database Query | Query the NetAlertX database | Result set | Show devices, open ports, recent events |
| `sqlite-db-query` | External DB | Query external SQLite databases | Result set | PiHole database, external logs |
| `template` | Template | Generate values from templates | Values | Initialize default settings |

## Data Source: `script`

Execute any Linux command or Python script and capture its output.

### Configuration

```json
{
  "data_source": "script",
  "show_ui": true,
  "mapped_to_table": "CurrentScan"
}
```

### How It Works

1. Command specified in `CMD` setting is executed
2. Script writes results to `/tmp/log/plugins/last_result.<PREFIX>.log`
3. Core reads file and parses pipe-delimited results
4. Results inserted into database

### Example: Simple Python Script

```json
{
  "function": "CMD",
  "type": {"dataType": "string", "elements": [{"elementType": "input", "elementOptions": [], "transformers": []}]},
  "default_value": "python3 /app/front/plugins/my_plugin/script.py",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Command"}]
}
```

### Example: Bash Script

```json
{
  "function": "CMD",
  "default_value": "bash /app/front/plugins/my_plugin/script.sh",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Command"}]
}
```

### Best Practices

- **Always use absolute paths** (e.g., `/app/front/plugins/...`)
- **Use `plugin_helper.py`** for output formatting
- **Add timeouts** via `RUN_TIMEOUT` setting (default: 60s)
- **Log errors** to `/tmp/log/plugins/<PREFIX>.log`
- **Handle missing dependencies gracefully**

### Output Format

Must write to: `/tmp/log/plugins/last_result.<PREFIX>.log`

Format: Pipe-delimited, 9 or 13 columns

See [Plugin Data Contract](PLUGINS_DEV_DATA_CONTRACT.md) for exact format

---

## Data Source: `app-db-query`

Query the NetAlertX SQLite database and display results.

### Configuration

```json
{
  "data_source": "app-db-query",
  "show_ui": true,
  "mapped_to_table": "CurrentScan"
}
```

### How It Works

1. SQL query specified in `CMD` setting is executed against `app.db`
2. Results parsed according to column definitions
3. Inserted into plugin display/database

### SQL Query Requirements

- Must return exactly **9 or 13 columns** matching the [data contract](PLUGINS_DEV_DATA_CONTRACT.md)
- Column names must match (order matters!)
- Must be **readable SQLite SQL** (not vendor-specific)

### Example: Open Ports from Nmap

```json
{
  "function": "CMD",
  "type": {"dataType": "string", "elements": [{"elementType": "input", "elementOptions": [], "transformers": []}]},
  "default_value": "SELECT dv.devName as objectPrimaryId, cast(dv.devLastIP as VARCHAR(100)) || ':' || cast(SUBSTR(ns.Port, 0, INSTR(ns.Port, '/')) as VARCHAR(100)) as objectSecondaryId, datetime() as DateTime, ns.Service as watchedValue1, ns.State as watchedValue2, null as watchedValue3, null as watchedValue4, ns.Extra as Extra, dv.devMac as ForeignKey FROM (SELECT * FROM Nmap_Scan) ns LEFT JOIN (SELECT devName, devMac, devLastIP FROM Devices) dv ON ns.MAC = dv.devMac",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "SQL to run"}],
  "description": [{"language_code": "en_us", "string": "This SQL query populates the plugin table"}]
}
```

### Example: Recent Device Events

```sql
SELECT
  e.EventValue as objectPrimaryId,
  d.devName as objectSecondaryId,
  e.EventDateTime as DateTime,
  e.EventType as watchedValue1,
  d.devLastIP as watchedValue2,
  null as watchedValue3,
  null as watchedValue4,
  e.EventDetails as Extra,
  d.devMac as ForeignKey
FROM
  Events e
LEFT JOIN
  Devices d ON e.DeviceMac = d.devMac
WHERE
  e.EventDateTime > datetime('now', '-24 hours')
ORDER BY
  e.EventDateTime DESC
```

See the [Database documentation](./DATABASE.md) for a list of common columns.

---

## Data Source: `sqlite-db-query`

Query an **external SQLite database** mounted in the container.

### Configuration

First, define the database path in a setting:

```json
{
  "function": "DB_PATH",
  "type": {"dataType": "string", "elements": [{"elementType": "input", "elementOptions": [], "transformers": []}]},
  "default_value": "/etc/pihole/pihole-FTL.db",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Database path"}],
  "description": [{"language_code": "en_us", "string": "Path to external SQLite database"}]
}
```

Then set data source and query:

```json
{
  "data_source": "sqlite-db-query",
  "show_ui": true
}
```

### How It Works

1. External database file path specified in `DB_PATH` setting
2. Database mounted at that path (e.g., via Docker volume)
3. SQL query executed against external database using `EXTERNAL_<PREFIX>.` prefix
4. Results returned in standard format

### SQL Query Example: PiHole Data

```json
{
  "function": "CMD",
  "default_value": "SELECT hwaddr as objectPrimaryId, cast('http://' || (SELECT ip FROM EXTERNAL_PIHOLE.network_addresses WHERE network_id = id ORDER BY lastseen DESC LIMIT 1) as VARCHAR(100)) || ':' || cast(SUBSTR((SELECT name FROM EXTERNAL_PIHOLE.network_addresses WHERE network_id = id ORDER BY lastseen DESC LIMIT 1), 0, INSTR((SELECT name FROM EXTERNAL_PIHOLE.network_addresses WHERE network_id = id ORDER BY lastseen DESC LIMIT 1), '/')) as VARCHAR(100)) as objectSecondaryId, datetime() as DateTime, macVendor as watchedValue1, lastQuery as watchedValue2, (SELECT name FROM EXTERNAL_PIHOLE.network_addresses WHERE network_id = id ORDER BY lastseen DESC LIMIT 1) as watchedValue3, null as watchedValue4, '' as Extra, hwaddr as ForeignKey FROM EXTERNAL_PIHOLE.network WHERE hwaddr NOT LIKE 'ip-%' AND hwaddr <> '00:00:00:00:00:00'",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "SQL to run"}]
}
```

### Key Points

- **Prefix all external tables** with `EXTERNAL_<PREFIX>.`
  - For PiHole (`PIHOLE` prefix): `EXTERNAL_PIHOLE.network`
  - For custom database (`CUSTOM` prefix): `EXTERNAL_CUSTOM.my_table`
- **Database must be valid SQLite**
- **Path must be accessible** inside the container
- **No columns beyond the data contract** required

### Docker Volume Setup

To mount external database in docker-compose:

```yaml
services:
  netalertx:
    volumes:
      - /path/on/host/pihole-FTL.db:/etc/pihole/pihole-FTL.db:ro
```

---

## Data Source: `template`

Generate values from a template. Usually used for initialization and default settings.

### Configuration

```json
{
  "data_source": "template"
}
```

### How It Works

- **Not widely used** in standard plugins
- Used internally for generating default values
- Check `newdev_template` plugin for implementation example

### Example: Default Device Template

```json
{
  "function": "DEFAULT_DEVICE_PROPERTIES",
  "type": {"dataType": "string", "elements": [{"elementType": "textarea", "elementOptions": [], "transformers": []}]},
  "default_value": "type=Unknown|vendor=Unknown",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Default properties"}]
}
```

---

## Data Source: `plugin_type`

Declare the plugin category. Controls where settings appear in the UI.

### Configuration

```json
{
  "data_source": "plugin_type",
  "value": "scanner"
}
```

### Supported Values

| Value | Section | Purpose |
|-------|---------|---------|
| `scanner` | Device Scanners | Discovers devices on network |
| `system` | System Plugins | Core system functionality |
| `publisher` | Notification/Alert Plugins | Sends notifications/alerts |
| `importer` | Data Importers | Imports devices from external sources |
| `other` | Other Plugins | Miscellaneous functionality |

### Example

```json
{
  "settings": [
    {
      "function": "plugin_type",
      "type": {"dataType": "string", "elements": []},
      "default_value": "scanner",
      "options": ["scanner"],
      "data_source": "plugin_type",
      "value": "scanner",
      "localized": []
    }
  ]
}
```

---

## Execution Order

Control plugin execution priority. Higher priority plugins run first.

```json
{
  "execution_order": "Layer_0"
}
```

### Levels (highest to lowest priority)

- `Layer_0` - Highest priority (run first)
- `Layer_1`
- `Layer_2`
- ...

### Example: Device Discovery


```json
{
  "code_name": "device_scanner",
  "unique_prefix": "DEVSCAN",
  "execution_order": "Layer_0",
  "data_source": "script",
  "mapped_to_table": "CurrentScan"
}
```

---

## Performance Considerations

### Script Source
- **Pros:** Flexible, can call external tools
- **Cons:** Slower than database queries
- **Optimization:** Add caching, use timeouts
- **Default timeout:** 60 seconds (set `RUN_TIMEOUT`)

### Database Query Source
- **Pros:** Fast, native query optimization
- **Cons:** Limited to SQL capabilities
- **Optimization:** Use indexes, avoid complex joins
- **Timeout:** Usually instant

### External DB Query Source
- **Pros:** Direct access to external data
- **Cons:** Network latency, external availability
- **Optimization:** Use indexes in external DB, selective queries
- **Timeout:** Depends on DB response time

---

## Debugging Data Sources

### Check Script Output

```bash
# Run script manually
python3 /app/front/plugins/my_plugin/script.py

# Check result file
cat /tmp/log/plugins/last_result.MYPREFIX.log
```

### Test SQL Query

```bash
# Connect to app database
sqlite3 /data/db/app.db

# Run query
sqlite> SELECT ... ;
```

### Monitor Execution

```bash
# Watch backend logs
tail -f /tmp/log/stdout.log | grep -i "data_source\|MYPREFIX"
```

---

## See Also

- [Plugin Data Contract](PLUGINS_DEV_DATA_CONTRACT.md) - Output format specification
- [Plugin Settings System](PLUGINS_DEV_SETTINGS.md) - How to define settings
- [Quick Start Guide](PLUGINS_DEV_QUICK_START.md) - Create your first plugin
- [Database Schema](DATABASE.md) - Available tables and columns
- [Debugging Plugins](DEBUG_PLUGINS.md) - Troubleshooting data issues
