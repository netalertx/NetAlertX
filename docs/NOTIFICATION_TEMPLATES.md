# Notification Text Templates

> Customize how devices and events appear in **text** notifications (email previews, push notifications, Apprise messages).

By default, NetAlertX formats each device as a vertical list of `Header: Value` pairs. Text templates let you define a **single-line format per device** using `{FieldName}` placeholders — ideal for mobile notification previews and high-volume alerts.

HTML email tables are **not affected** by these templates.

## Quick Start

1. Go to **Settings → Notification Processing**.
2. Set a template string for the section you want to customize, e.g.:
   - **Text Template: New Devices** → `{devName} ({eveMac}) - {eveIp}`
3. Save. The next notification will use your format.

**Before (default):**
```
🆕 New devices
---------
devName: 	    MyPhone
eveMac: 	    aa:bb:cc:dd:ee:ff
devVendor: 	    Apple
eveIp: 	    192.168.1.42
eveDateTime: 	2025-01-15 10:30:00
eveEventType:  New Device
devComments:
```

**After (with template `{devName} ({eveMac}) - {eveIp}`):**
```
🆕 New devices
---------
MyPhone (aa:bb:cc:dd:ee:ff) - 192.168.1.42
```

## Settings Reference

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `NTFPRCS_TEXT_SECTION_HEADERS` | Boolean | `true` | Show/hide section titles (e.g. `🆕 New devices \n---------`). |
| `NTFPRCS_TEXT_TEMPLATE_new_devices` | String | *(empty)* | Template for new device rows. |
| `NTFPRCS_TEXT_TEMPLATE_down_devices` | String | *(empty)* | Template for down device rows. |
| `NTFPRCS_TEXT_TEMPLATE_down_reconnected` | String | *(empty)* | Template for reconnected device rows. |
| `NTFPRCS_TEXT_TEMPLATE_events` | String | *(empty)* | Template for event rows. |
| `NTFPRCS_TEXT_TEMPLATE_plugins` | String | *(empty)* | Template for plugin event rows. |

When a template is **empty**, the section uses the original vertical `Header: Value` format (full backward compatibility).

## Template Syntax

Use `{FieldName}` to insert a value from the notification data. Field names are **case-sensitive** and must match the column names exactly.

```
{devName} ({eveMac}) connected at {eveDateTime}
```

- No loops, conditionals, or nesting — just simple string replacement.
- If a `{FieldName}` does not exist in the data, it is left as-is in the output (safe failure). For example, `{NonExistent}` renders literally as `{NonExistent}`.

## Variable Availability by Section

All four device sections (`new_devices`, `down_devices`, `down_reconnected`, `events`) share the same unified field names.

### `new_devices`, `down_devices`, `down_reconnected`, and `events`

| Variable | Description |
|----------|-------------|
| `{devName}` | Device display name |
| `{eveMac}` | Device MAC address |
| `{devVendor}` | Device vendor/manufacturer |
| `{eveIp}` | Device IP address |
| `{eveDateTime}` | Event timestamp |
| `{eveEventType}` | Type of event (e.g. `New Device`, `Connected`, `Device Down`) |
| `{devComments}` | Device comments |

**Example (new_devices/events):** `{devName} ({eveMac}) - {eveIp} [{eveEventType}]`

**Example (down_devices):** `{devName} ({eveMac}) {devVendor} - went down at {eveDateTime}`

**Example (down_reconnected):** `{devName} ({eveMac}) reconnected at {eveDateTime}`

### `plugins`

| Variable | Description |
|----------|-------------|
| `{plugin}` | Plugin code name |
| `{objectPrimaryId}` | Primary identifier of the object |
| `{objectSecondaryId}` | Secondary identifier |
| `{dateTimeChanged}` | Timestamp of change |
| `{watchedValue1}` | First watched value |
| `{watchedValue2}` | Second watched value |
| `{watchedValue3}` | Third watched value |
| `{watchedValue4}` | Fourth watched value |
| `{status}` | Plugin event status |

**Example:** `{plugin}: {objectPrimaryId} - {status}`

## Section Headers Toggle

Set **Text Section Headers** (`NTFPRCS_TEXT_SECTION_HEADERS`) to `false` to remove the section title separators from text notifications. This is useful when you want compact output without the `🆕 New devices \n---------` banners.
