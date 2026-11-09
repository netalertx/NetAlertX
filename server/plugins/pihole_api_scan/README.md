## Overview - PIHOLEAPI Plugin — Pi-hole v6 Device Import

The **PIHOLEAPI** plugin lets NetAlertX import network devices directly from a **Pi-hole v6** instance.
This turns Pi-hole into an additional discovery source, helping NetAlertX stay aware of devices seen by your DNS server.

The plugin connects to your Pi-hole’s API and retrieves:

* MAC addresses
* IP addresses
* Hostnames (if available)
* Vendor info
* Time of the last DNS query

NetAlertX then uses this information to match or create devices in your system.

See the [Pi-hole guide](https://docs.netalertx.com/PIHOLE_GUIDE) for a walkthrough covering this plugin alongside the other Pi-hole integrations (`PIHOLE`, `PIHOLEMON`, `DHCPLSS`).

### Quick setup guide

* You are running **Pi-hole v6** or newer.
* The Web UI password in **Pi-hole** is set.
* Local network devices appear under **Settings → Network** in Pi-hole.

No additional Pi-hole configuration is required.

### Usage

- Head to **Settings** > **Plugin name** to adjust the default values.

| Setting Key                  | Description                                                                      |
| ---------------------------- | -------------------------------------------------------------------------------- |
| **PIHOLEAPI_URL**            | Your Pi-hole base URL.                                                           |
| **PIHOLEAPI_PASSWORD**       | The Web UI base64 encoded (en-/decoding handled by the app) admin password.      |
| **PIHOLEAPI_VERIFY_SSL**     | Whether to verify HTTPS certificates. Disable only for self-signed certificates. |
| **PIHOLEAPI_RUN_TIMEOUT**    | Request timeout in seconds.                                                      |
| **PIHOLEAPI_API_MAXCLIENTS** | Maximum number of devices to request from Pi-hole. Defaults are usually fine.    |
| **PIHOLEAPI_FAKE_MAC**       | Generate FAKE MAC from IP.                                                       |


### ⚠️ Troubleshooting

Below are the most common issues and how to resolve them.

---

#### ❌ Authentication failed

Check the following:

* The Pi-hole URL is correct and includes a trailing slash

  * `http://192.168.1.10/` ✔
  * `http://192.168.1.10/admin` ❌
* Your Pi-hole password is correct
* You are using **Pi-hole v6**, not v5
* SSL verification matches your setup (disable for self-signed certificates)

---

#### ❌ Connection error

Usually caused by:

* Wrong URL
* Wrong HTTP/HTTPS selection
* Timeout too low

Try:

```
PIHOLEAPI_URL = http://<pi-hole-ip>/
PIHOLEAPI_RUN_TIMEOUT = 60
```

---

#### ❌ No devices imported

Check:

* Pi-hole shows devices under **Settings → Network**
* NetAlertX logs contain:

```
[PIHOLEAPI] Pi-hole API returned data
```

If nothing appears:

* Pi-hole might be returning empty results
* Your network interface list may be empty
* A firewall or reverse proxy is blocking access

Try enabling debug logging:

```
LOG_LEVEL = debug
```

Then re-run the plugin.

---

#### ❌ Some devices are missing

Check:

* Pi-hole shows devices under **Settings → Network**
* NetAlertX logs contain:

```
[PIHOLEAPI] Skipping invalid MAC (see PIHOLEAPI_FAKE_MAC setting) ...
```

If devices are missing:

* The app skipps devices with invalid MACs
* Enable PIHOLEAPI_FAKE_MAC if you want to import these devices with a fake mac and you are not concerned with data inconsistencies later on

Try enabling PIHOLEAPI_FAKE_MAC:

```
PIHOLEAPI_FAKE_MAC = 1
```

Then re-run the plugin.

---

#### ❌ Wrong or missing hostnames

Pi-hole only reports names it knows from:

* Local DNS
* DHCP leases
* Previously seen queries

If names are missing, confirm they appear in Pi-hole’s own UI first.

### Notes

- **Online status comes from DNS activity.** A device counts as online when its last DNS query to Pi-hole is at most `PIHOLEAPI_CONSIDER_ONLINE` seconds old. Pi-hole's per-IP "last seen" value is not used, because Pi-hole keeps refreshing it for as long as it holds the client in memory (about 24 hours in practice), also after the device has left.
- Devices that send a DNS query only every few hours, such as smart plugs, powerline adapters or speakers, can show as offline although they are on. Run a presence scanner such as [ARPSCAN](https://docs.netalertx.com/plugins/arp_scan) on the same schedule. If PIHOLEAPI is your only presence source, raise `PIHOLEAPI_CONSIDER_ONLINE` instead (for example to `3600`). A device that has left the network then also counts as online for that long.
- With `PIHOLEAPI_GET_OFFLINE` enabled, offline devices are still imported (name, vendor, IP), but they are not marked as online.

- Version: 1.0.0
- Author: `jokob-sk`, `leiweibau`
- Release Date: `11-2025`

---


