# Plugin UI Components

Configure how your plugin's data is displayed in the NetAlertX web interface.

## Overview

Plugin results are displayed in the UI via the **Plugins page** and **Device details tabs**. You control the appearance and functionality of these displays by defining `database_column_definitions` in your plugin's `config.json`.

Each column definition specifies:

- Which data field to display
- How to render it (label, link, color-coded badge, etc.)
- What CSS classes to apply
- What transformations to apply (regex, string replacement, etc.)

## Column Definition Structure

```json
{
  "column": "objectPrimaryId",
  "mapped_to_column": "devMac",
  "mapped_to_column_data": null,
  "css_classes": "col-sm-2",
  "show": true,
  "type": "device_mac",
  "default_value": "",
  "options": [],
  "options_params": [],
  "localized": ["name"],
  "name": [
    {
      "language_code": "en_us",
      "string": "MAC Address"
    }
  ]
}
```

## Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `column` | string | **YES** | Source column name from data contract (e.g., `objectPrimaryId`, `watchedValue1`) |
| `mapped_to_column` | string | no | Target database column if mapping to a table like `CurrentScan` |
| `mapped_to_column_data` | object | no | Static value to map instead of using column data |
| `css_classes` | string | no | Bootstrap CSS classes for width/spacing (e.g., `"col-sm-2"`, `"col-sm-6"`) |
| `show` | boolean | **YES** | Whether to display in UI (must be `true` to appear) |
| `type` | string | **YES** | How to render the value (see [Render Types](#render-types)) |
| `default_value` | varies | **YES** | Default if column is empty |
| `options` | array | no | Options for `select`/`threshold`/`replace`/`regex` types |
| `options_params` | array | no | Dynamic options from SQL or settings |
| `localized` | array | **YES** | Which properties need translations (e.g., `["name", "description"]`) |
| `name` | array | **YES** | Display name in UI (localized strings) |
| `description` | array | no | Help text in UI (localized strings) |
| `maxLength` | number | no | Character limit for input fields |

## Render Types

### Display-Only Types

These render as read-only display elements:

#### `label`
Plain text display (read-only).

```json
{
  "column": "watchedValue1",
  "show": true,
  "type": "label",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Status"}]
}
```

**Output:** `online`

---

#### `device_mac`
Renders as a clickable link to the device with the given MAC address.

```json
{
  "column": "ForeignKey",
  "show": true,
  "type": "device_mac",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Device"}]
}
```

**Input:** `aa:bb:cc:dd:ee:ff`
**Output:** Clickable link to device details page

---

#### `device_ip`
Resolves an IP address to a MAC address and creates a device link.

```json
{
  "column": "objectSecondaryId",
  "show": true,
  "type": "device_ip",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Host"}]
}
```

**Input:** `192.168.1.100`
**Output:** Link to device with that IP (if known)

---

#### `device_name_mac`
Creates a device link with the target device's name as the link label.

```json
{
  "column": "objectPrimaryId",
  "show": true,
  "type": "device_name_mac",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Device Name"}]
}
```

**Input:** `aa:bb:cc:dd:ee:ff`
**Output:** Device name (clickable link to device)

---

#### `url`
Renders as a clickable HTTP/HTTPS link.

```json
{
  "column": "watchedValue1",
  "show": true,
  "type": "url",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Endpoint"}]
}
```

**Input:** `https://example.com/api`
**Output:** Clickable link

---

#### `url_http_https`
Creates two links (HTTP and HTTPS) as lock icons for the given IP/hostname.

```json
{
  "column": "objectSecondaryId",
  "show": true,
  "type": "url_http_https",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Web Links"}]
}
```

**Input:** `192.168.1.50`
**Output:** 🔓 HTTP link | 🔒 HTTPS link

---

#### `textarea_readonly`
Multi-line read-only display with newlines preserved.

```json
{
  "column": "Extra",
  "show": true,
  "type": "textarea_readonly",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Details"}]
}
```

---

### Interactive Types

#### `textbox_save`
User-editable text box that persists changes to the database (typically `UserData` column).

```json
{
  "column": "UserData",
  "show": true,
  "type": "textbox_save",
  "default_value": "",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Notes"}]
}
```

---

### Styled/Transformed Types

#### `label` with `threshold`

Color-codes values based on ranges. Useful for status codes, latency, capacity percentages.

```json
{
  "column": "watchedValue1",
  "show": true,
  "type": "threshold",
  "options": [
    {
      "maximum": 199,
      "hexColor": "#792D86"  // Purple for <199
    },
    {
      "maximum": 299,
      "hexColor": "#5B862D"  // Green for 200-299
    },
    {
      "maximum": 399,
      "hexColor": "#7D862D"  // Orange for 300-399
    },
    {
      "maximum": 499,
      "hexColor": "#BF6440"  // Red-orange for 400-499
    },
    {
      "maximum": 999,
      "hexColor": "#D33115"  // Dark red for 500+
    }
  ],
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "HTTP Status"}]
}
```

**How it works:**

- Value `150` → Purple (≤199)
- Value `250` → Green (≤299)
- Value `350` → Orange (≤399)
- Value `450` → Red-orange (≤499)
- Value `550` → Dark red (>500)

---

#### `replace`
Replaces specific values with display strings or HTML.

```json
{
  "column": "watchedValue2",
  "show": true,
  "type": "replace",
  "options": [
    {
      "equals": "online",
      "replacement": "<i class='fa-solid fa-circle' style='color: green;'></i> Online"
    },
    {
      "equals": "offline",
      "replacement": "<i class='fa-solid fa-circle' style='color: red;'></i> Offline"
    },
    {
      "equals": "idle",
      "replacement": "<i class='fa-solid fa-circle' style='color: yellow;'></i> Idle"
    }
  ],
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Status"}]
}
```

**Output Examples:**

- `"online"` → 🟢 Online
- `"offline"` → 🔴 Offline
- `"idle"` → 🟡 Idle

---

#### `regex`
Applies a regular expression to extract/transform values.

```json
{
  "column": "watchedValue1",
  "show": true,
  "type": "regex",
  "options": [
    {
      "type": "regex",
      "param": "([0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3})"
    }
  ],
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "IP Address"}]
}
```

- **Input:** `Host: 192.168.1.100 Port: 8080`
- **Output:** `192.168.1.100`

---

#### `eval`
Evaluates JavaScript code with access to the column value (use `${value}` or `{value}`).

```json
{
  "column": "watchedValue1",
  "show": true,
  "type": "eval",
  "default_value": "",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Formatted Value"}]
}
```

**Example with custom formatting:**
```json
{
  "column": "watchedValue1",
  "show": true,
  "type": "eval",
  "options": [
    {
      "type": "eval",
      "param": "`<b>${value}</b> units`"
    }
  ],
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Value with Units"}]
}
```

- **Input:** `42`
- **Output:** **42** units

---

### Chaining Types

You can chain multiple transformations with dot notation:

```json
{
  "column": "watchedValue3",
  "show": true,
  "type": "regex.url_http_https",
  "options": [
    {
      "type": "regex",
      "param": "([\\d.:]+)"  // Extract IP/host
    }
  ],
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "HTTP/S Links"}]
}
```

**Flow:**

1. Apply regex to extract `192.168.1.50` from input
2. Create HTTP/HTTPS links for that host

---

## Dynamic Options

### SQL-Driven Select

Use SQL query results to populate dropdown options:

```json
{
  "column": "watchedValue2",
  "show": true,
  "type": "select",
  "options": ["{value}"],
  "options_params": [
    {
      "name": "value",
      "type": "sql",
      "value": "SELECT devType as id, devType as name FROM Devices UNION SELECT 'Unknown' as id, 'Unknown' as name ORDER BY id"
    }
  ],
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Device Type"}]
}
```

The SQL query must return exactly **2 columns:**

- **First column (id):** Option value
- **Second column (name):** Display label

---

### Setting-Driven Select

Use plugin settings to populate options:

```json
{
  "column": "watchedValue1",
  "show": true,
  "type": "select",
  "options": ["{value}"],
  "options_params": [
    {
      "name": "value",
      "type": "setting",
      "value": "MYPLN_AVAILABLE_STATUSES"
    }
  ],
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Status"}]
}
```

---

## Mapping to Database Tables

### Mapping to `CurrentScan`

To import plugin data into the device scan pipeline (for notifications, heuristics, etc.):

1. Add `"mapped_to_table": "CurrentScan"` at the root level of `config.json`
2. Add `"mapped_to_column"` property to each column definition

```json
{
  "code_name": "my_device_scanner",
  "unique_prefix": "MYSCAN",
  "mapped_to_table": "CurrentScan",
  "database_column_definitions": [
    {
      "column": "objectPrimaryId",
      "mapped_to_column": "scanMac",
      "show": true,
      "type": "device_mac",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "MAC Address"}]
    },
    {
      "column": "objectSecondaryId",
      "mapped_to_column": "scanLastIP",
      "show": true,
      "type": "device_ip",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "IP Address"}]
    },
    {
      "column": "NameDoesntMatter",
      "mapped_to_column": "scanSourcePlugin",
      "mapped_to_column_data": {
        "value": "MYSCAN"
      },
      "show": true,
      "type": "label",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "Scan Method"}]
    }
  ]
}
```

---

### Using Static Values

Use `mapped_to_column_data` to map a static value instead of reading from a column:

```json
{
  "column": "NameDoesntMatter",
  "mapped_to_column": "scanSourcePlugin",
  "mapped_to_column_data": {
    "value": "MYSCAN"
  },
  "show": true,
  "type": "label",
  "localized": ["name"],
  "name": [{"language_code": "en_us", "string": "Discovery Method"}]
}
```

This always sets `scanSourcePlugin` to `"MYSCAN"` regardless of column data.

---

## Filters

Control which rows are displayed based on filter conditions. Filters are applied on the client-side in JavaScript.

```json
{
  "data_filters": [
    {
      "compare_column": "objectPrimaryId",
      "compare_operator": "==",
      "compare_field_id": "txtMacFilter",
      "compare_js_template": "'{value}'.toString()",
      "compare_use_quotes": true
    }
  ]
}
```

| Property | Description |
|----------|-------------|
| `compare_column` | The column from plugin results to compare (left side) |
| `compare_operator` | JavaScript operator: `==`, `!=`, `<`, `>`, `<=`, `>=`, `includes`, `startsWith` |
| `compare_field_id` | HTML input field ID containing the filter value (right side) |
| `compare_js_template` | JavaScript template to transform values. Use `{value}` placeholder |
| `compare_use_quotes` | If `true`, wrap result in quotes for string comparison |

**Example: Filter by MAC address**

```json
{
  "data_filters": [
    {
      "compare_column": "ForeignKey",
      "compare_operator": "==",
      "compare_field_id": "txtMacFilter",
      "compare_js_template": "'{value}'.toString()",
      "compare_use_quotes": true
    }
  ]
}
```

When viewing a device detail page, the `txtMacFilter` field is populated with that device's MAC, and only rows where `ForeignKey == MAC` are shown.

---

## Example: Complete Column Definitions

```json
{
  "database_column_definitions": [
    {
      "column": "objectPrimaryId",
      "mapped_to_column": "scanMac",
      "css_classes": "col-sm-2",
      "show": true,
      "type": "device_mac",
      "default_value": "",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "MAC Address"}]
    },
    {
      "column": "objectSecondaryId",
      "mapped_to_column": "scanLastIP",
      "css_classes": "col-sm-2",
      "show": true,
      "type": "device_ip",
      "default_value": "unknown",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "IP Address"}]
    },
    {
      "column": "DateTime",
      "css_classes": "col-sm-2",
      "show": true,
      "type": "label",
      "default_value": "",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "Last Seen"}]
    },
    {
      "column": "watchedValue1",
      "css_classes": "col-sm-2",
      "show": true,
      "type": "threshold",
      "options": [
        {"maximum": 199, "hexColor": "#792D86"},
        {"maximum": 299, "hexColor": "#5B862D"},
        {"maximum": 399, "hexColor": "#7D862D"},
        {"maximum": 499, "hexColor": "#BF6440"},
        {"maximum": 999, "hexColor": "#D33115"}
      ],
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "HTTP Status"}]
    },
    {
      "column": "watchedValue2",
      "css_classes": "col-sm-1",
      "show": true,
      "type": "label",
      "default_value": "",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "Response Time"}]
    },
    {
      "column": "Extra",
      "css_classes": "col-sm-3",
      "show": true,
      "type": "textarea_readonly",
      "default_value": "",
      "localized": ["name"],
      "name": [{"language_code": "en_us", "string": "Additional Info"}]
    }
  ]
}
```

---

## CSS Classes

Use Bootstrap grid classes to control column widths in tables:

| Class | Width | Usage |
|-------|-------|-------|
| `col-sm-1` | ~8% | Very narrow (icons, status) |
| `col-sm-2` | ~16% | Narrow (MACs, IPs) |
| `col-sm-3` | ~25% | Medium (names, URLs) |
| `col-sm-4` | ~33% | Medium-wide (descriptions) |
| `col-sm-6` | ~50% | Wide (large content) |

---

## Validation Checklist

- [ ] All columns have `"show": true` or `false`
- [ ] Display columns with `"type"` specified from supported types
- [ ] Localized strings include at least `en_us`
- [ ] `mapped_to_column` matches target table schema (if using mapping)
- [ ] Options/thresholds have correct structure
- [ ] CSS classes are valid Bootstrap grid classes
- [ ] Chaining types (e.g., `regex.url_http_https`) are supported combinations

---

## See Also

- [Plugin Data Contract](PLUGINS_DEV_DATA_CONTRACT.md) - What data fields are available
- [Plugin Settings System](PLUGINS_DEV_SETTINGS.md) - Configure user input
- [Database Mapping](PLUGINS_DEV.md#-mapping-the-plugin-results-into-a-database-table) - Map data to core tables
- [Debugging Plugins](DEBUG_PLUGINS.md) - Troubleshoot display issues
