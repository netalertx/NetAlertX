# adguard_export — NetAlertX Plugin

> **Direction:** NetAlertX → AdGuard Home  
> Syncs known devices from the NetAlertX database to AdGuard Home as **persistent clients**, keeping device names, MAC addresses, and IP identifiers in sync.

---

## What it does

On every run the plugin:

1. Reads all (or only *known*) devices from the NetAlertX database.
2. Fetches the current list of persistent clients from AdGuard Home via its REST API.
3. **Adds** clients that are in NetAlertX but not yet in AdGuard Home.
4. **Updates** clients whose name, identifiers, or device-type tag have changed.
5. Optionally **deletes** clients that have been removed from NetAlertX (see `DELETE` setting).

Device types set in NetAlertX (e.g. `Smartphone`, `Laptop`, `NAS`) are automatically mapped to the corresponding AdGuard Home `device_*` tags (e.g. `device_phone`, `device_laptop`, `device_nas`).

---

## Requirements

| Requirement | Notes |
|---|---|
| AdGuard Home | v0.107+ (REST API must be enabled) |
| Python packages | `requests`, `pytz` — already present in the NetAlertX container |
| AdGuard credentials | A user account with permission to manage clients |

---

## Installation

1. Copy the `adguard_export/` folder into `/app/front/plugins/` inside your NetAlertX container (or mount it as a volume).
2. Restart NetAlertX so the plugin is discovered.
3. Open **Settings → Plugins → AdGuard (Device Export)** and configure the settings below.

---

## Settings

| Setting key | Default | Description |
|---|---|---|
| `ADGUARDEXP_RUN` | `disabled` | When to run: `disabled`, `once`, or `schedule` |
| `ADGUARDEXP_RUN_SCHD` | `0 * * * *` | Cron schedule (default: hourly) |
| `ADGUARDEXP_URL` | `http://localhost:3000` | Base URL of AdGuard Home web UI |
| `ADGUARDEXP_USER` | `admin` | AdGuard Home username |
| `ADGUARDEXP_PASSWORD` | *(empty)* | AdGuard Home password |
| `ADGUARDEXP_VERIFYSSL` | `true` | Verify TLS cert; set `false` for self-signed certs |
| `ADGUARDEXP_INCLUDE_OFFLINE` | `true` | When `true`, devices not seen in the last scan are still exported |
| `ADGUARDEXP_INCLUDE_NEW` | `false` | When `false`, devices flagged as new/unknown are excluded until identified |
| `ADGUARDEXP_USEMAC` | `true` | Use MAC address as primary client identifier; falls back to IP |
| `ADGUARDEXP_DELETE` | `false` | ⚠ Delete AdGuard clients no longer present in NetAlertX |

---

## AdGuard Home client identifiers

AdGuard Home identifies a client by one or more **ids**, which can be:

- A MAC address (e.g. `aa:bb:cc:dd:ee:ff`)
- An IP address (e.g. `192.168.1.42`)
- A CIDR range
- A ClientID string

When `ADGUARDEXP_USEMAC=true`, the plugin prefers the device's MAC address and includes the last known IP as a secondary identifier. When `ADGUARDEXP_USEMAC=false`, only the IP address is used.

---

## Device type tags

The plugin maps NetAlertX device types to valid AdGuard Home `device_*` tags automatically:

| NetAlertX type | AdGuard tag |
|---|---|
| Smartphone, Phone, Mobile | `device_phone` |
| Laptop, Notebook | `device_laptop` |
| Desktop, Server, Hypervisor | `device_pc` |
| Tablet | `device_tablet` |
| Smart TV, SmartTV, TV | `device_tv` |
| NAS | `device_nas` |
| Printer | `device_printer` |
| IP Camera, Camera | `device_camera` |
| Game Console | `device_gameconsole` |
| Speaker, Assistant, Virtual Assistance | `device_audio` |
| AP, Gateway, Router, House Appliance | `device_other` |

Devices with an unrecognised or empty type are exported without a tag.

---

## Safe deletion

When `ADGUARDEXP_DELETE=true`, the plugin only removes clients it previously created — it will never delete clients you added manually in AdGuard Home. Ownership is tracked in a local state file at:

```text
/app/db/state.ADGUARDEXP.json
```

---

## Logs

Plugin logs are written to:

```text
/tmp/log/plugins/script.ADGUARDEXP.log
```

Result rows (used by the NetAlertX UI) are written to:

```text
/tmp/log/plugins/last_result.ADGUARDEXP.log
```

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Connection failed` in logs | Wrong `ADGUARDEXP_URL` or AdGuard Home is unreachable from the NetAlertX container |
| `HTTP error: 401` | Wrong username / password |
| `HTTP error: 400` | Client already exists with conflicting ids — check AdGuard Home for duplicate entries |
| Devices not appearing | `ADGUARDEXP_INCLUDE_NEW=false` and devices are flagged as new/unknown; identify them in NetAlertX first |
| SSL errors | Set `ADGUARDEXP_VERIFYSSL=false` for self-signed certificates |

---

## Related plugins

- **adguard_import** — the reverse direction: imports devices *from* AdGuard Home *into* NetAlertX.

---

### Other info

- Version: 1.0.0
- Maintainer: [natecj](https://github.com/natecj)
- Release Date: 10-May-2026
