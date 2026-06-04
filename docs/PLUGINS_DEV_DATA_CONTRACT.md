# Plugin Data Contract

This document specifies the exact interface between plugins and the NetAlertX core.

> [!IMPORTANT]
> Every plugin must output data in this exact format to be recognized and processed correctly.

## Overview

Plugins communicate with NetAlertX by writing results to a **pipe-delimited log file**. The core reads this file, parses the data, and processes it for notifications, device discovery, and data integration.

**File Location:** `/tmp/log/plugins/last_result.<PREFIX>.log`

**Format:** Pipe-delimited (`|`), one record per line

**Required Columns:** 9 (mandatory) + up to 4 optional helper columns = 13 total


## Using `plugin_helper.py`

The easiest way to ensure correct output is to use the [`plugin_helper.py`](../front/plugins/plugin_helper.py) library:

```python
from plugin_helper import Plugin_Objects

# Initialize with your plugin's prefix
plugin_objects = Plugin_Objects("YOURPREFIX")

# Add objects
plugin_objects.add_object(
    objectPrimaryId="device_id",
    objectSecondaryId="192.168.1.1",
    DateTime="2023-01-02 15:56:30",
    watchedValue1="online",
    watchedValue2=None,
    watchedValue3=None,
    watchedValue4=None,
    Extra="Additional data",
    ForeignKey="aa:bb:cc:dd:ee:ff",
    helpVal1=None,
    helpVal2=None,
    helpVal3=None,
    helpVal4=None
)

# Write results (handles formatting, sanitization, and file creation)
plugin_objects.write_result_file()
```

The library automatically:

- Validates data types
- Sanitizes string values
- Normalizes MAC addresses
- Writes to the correct file location
- Creates the file in `/tmp/log/plugins/last_result.<PREFIX>.log`

## Column Specification

> [!NOTE]
> The order of columns is **FIXED** and cannot be changed. All 9 mandatory columns must be provided. If you use any optional column (`helpVal1`), you must supply all optional columns (`helpVal1` through `helpVal4`).

### Mandatory Columns (0–8)

| Order | Column Name | Type | Required | Description |
|-------|-------------|------|----------|-------------|
| 0 | `objectPrimaryId` | string | **YES** | The primary identifier for grouping. Examples: device MAC, hostname, service name, or any unique ID |
| 1 | `objectSecondaryId` | string | no | Secondary identifier for relationships (e.g., IP address, port, sub-ID). Use `null` if not needed |
| 2 | `DateTime` | string | **YES** | Timestamp when the event/data was collected. Format: `YYYY-MM-DD HH:MM:SS` |
| 3 | `watchedValue1` | string | **YES** | Primary watched value. Changes trigger notifications. Examples: IP address, status, version |
| 4 | `watchedValue2` | string | no | Secondary watched value. Use `null` if not needed |
| 5 | `watchedValue3` | string | no | Tertiary watched value. Use `null` if not needed |
| 6 | `watchedValue4` | string | no | Quaternary watched value. Use `null` if not needed |
| 7 | `Extra` | string | no | Any additional metadata to display in UI and notifications. Use `null` if not needed |
| 8 | `ForeignKey` | string | no | Foreign key linking to parent object (usually MAC address for device relationship). Use `null` if not needed |

### Optional Columns (9–12)

| Order | Column Name | Type | Required | Description |
|-------|-------------|------|----------|-------------|
| 9 | `helpVal1` | string | *conditional* | Helper value 1. If used, all help values must be supplied |
| 10 | `helpVal2` | string | *conditional* | Helper value 2. If used, all help values must be supplied |
| 11 | `helpVal3` | string | *conditional* | Helper value 3. If used, all help values must be supplied |
| 12 | `helpVal4` | string | *conditional* | Helper value 4. If used, all help values must be supplied |

## Usage Guide

### Empty/Null Values

- Represent empty values as the literal string `null` (not Python `None`, SQL `NULL`, or empty string)
- Example: `device_id|null|2023-01-02 15:56:30|status|null|null|null|null|null`

### Watched Values

**What are Watched Values?**

Watched values are fields that the NetAlertX core monitors for **changes between scans**. When a watched value differs from the previous scan, it can trigger notifications.

**How to use them:**

- `watchedValue1`: Always required; primary indicator of status/state
- `watchedValue2–4`: Optional; use for secondary/tertiary state information
- Leave unused ones as `null`

**Example:**

- Device scanner: `watchedValue1 = "online"` or `"offline"`
- Port scanner: `watchedValue1 = "80"` (port number), `watchedValue2 = "open"` (state)
- Service monitor: `watchedValue1 = "200"` (HTTP status), `watchedValue2 = "0.45"` (response time)

### Foreign Key

Use the `ForeignKey` column to link objects to a parent device by MAC address:

```
device_name|192.168.1.100|2023-01-02 15:56:30|online|null|null|null|Found on network|aa:bb:cc:dd:ee:ff
                                                                                              ↑
                                                                                        ForeignKey (MAC)
```

This allows NetAlertX to:

- Display the object on the device details page
- Send notifications when the parent device is involved
- Link events across plugins

## Examples

### Valid Data (9 columns, minimal)

```csv
https://example.com|null|2023-01-02 15:56:30|200|null|null|null|null|null
printer-hp-1|192.168.1.50|2023-01-02 15:56:30|online|50%|null|null|Last seen in office|aa:11:22:33:44:55
gateway.local|null|2023-01-02 15:56:30|active|v2.1.5|null|null|Firmware version|null
```

### Valid Data (13 columns, with helpers)

```csv
service-api|192.168.1.100:8080|2023-01-02 15:56:30|200|45ms|true|null|Responding normally|aa:bb:cc:dd:ee:ff|extra1|extra2|extra3|extra4
host-web-1|10.0.0.20|2023-01-02 15:56:30|active|256GB|online|ok|Production server|null|cpu:80|mem:92|disk:45|alerts:0
```

### Invalid Data (Common Errors)

❌ **Missing required column** (only 8 separators instead of 8):
```csv
https://google.com|null|2023-01-02 15:56:30|200|0.7898||null|null
                                                      ↑
                                                  Missing pipe
```

❌ **Missing mandatory watchedValue1** (column 3):
```csv
https://duckduckgo.com|192.168.1.1|2023-01-02 15:56:30|null|0.9898|null|null|Best|null
                                                         ↑
                                          Must not be null
```

❌ **Incomplete optional columns** (has helpVal1 but missing helpVal2–4):
```csv
device|null|2023-01-02 15:56:30|status|null|null|null|null|null|helper1
                                                                    ↑
                                                    Has helper but incomplete
```

✅ **Complete with helpers** (all 4 helpers provided):
```csv
device|null|2023-01-02 15:56:30|status|null|null|null|null|null|h1|h2|h3|h4
```

✅ **Complete without helpers** (9 columns exactly):
```csv
device|null|2023-01-02 15:56:30|status|null|null|null|null|null
```

## De-duplication

The core runs **de-duplication once per hour** on the `Plugins_Objects` table:

- **Duplicate Detection Key:** Combination of `objectPrimaryId`, `objectSecondaryId`, `Plugin` (auto-filled from `unique_prefix`), and `UserData`
- **Resolution:** Oldest duplicate entries are removed, newest are kept
- **Use Case:** Prevents duplicate notifications when the same object is detected multiple times

## DateTime Format

**Required Format:** `YYYY-MM-DD HH:MM:SS`

**Examples:**

- `2023-01-02 15:56:30` ✅
- `2023-1-2 15:56:30` ❌ (missing leading zeros)
- `2023-01-02T15:56:30` ❌ (wrong separator)
- `15:56:30 2023-01-02` ❌ (wrong order)

**Python Helper:**
```python
from datetime import datetime

# Current time in correct format
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# Output: "2023-01-02 15:56:30"
```

**Bash Helper:**
```bash
# Current time in correct format
date '+%Y-%m-%d %H:%M:%S'
# Output: 2023-01-02 15:56:30
```

## Validation Checklist

Before writing your plugin's `script.py`, ensure:

- [ ] **9 or 13 columns** in each output line (8 or 12 pipe separators)
- [ ] **Mandatory columns filled:**
  - Column 0: `objectPrimaryId` (not null)
  - Column 2: `DateTime` in `YYYY-MM-DD HH:MM:SS` format
  - Column 3: `watchedValue1` (not null)
- [ ] **Null values as literal string** `null` (not empty string or special chars)
- [ ] **No extra pipes or misaligned columns**
- [ ] **If using optional helpers** (columns 9–12), all 4 must be present
- [ ] **File written to** `/tmp/log/plugins/last_result.<PREFIX>.log`
- [ ] **One record per line** (newline-delimited)
- [ ] **No header row** (data only)

## Debugging

**View raw plugin output:**
```bash
cat /tmp/log/plugins/last_result.YOURPREFIX.log
```

**Check line count:**
```bash
wc -l /tmp/log/plugins/last_result.YOURPREFIX.log
```

**Validate column count (should be 8 or 12 pipes per line):**
```bash
cat /tmp/log/plugins/last_result.YOURPREFIX.log | awk -F'|' '{print NF}' | sort | uniq
# Output: 9 (for minimal) or 13 (for with helpers)
```

**Check core processing in logs:**
```bash
tail -f /tmp/log/stdout.log | grep -i "YOURPREFIX\|Plugins_Objects"
```

## See Also

- [Plugin Settings System](PLUGINS_DEV_SETTINGS.md) - How to accept user input
- [Data Sources](PLUGINS_DEV_DATASOURCES.md) - Different data source types
- [Debugging Plugins](DEBUG_PLUGINS.md) - Troubleshooting plugin issues
