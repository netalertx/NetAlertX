## Overview - PIHOLEMON Plugin — Pi-hole Monitor

The **PIHOLEMON** plugin does two jobs against the same Pi-hole connection(s):

1. **Query anomaly detection** - flags a device whose *blocked*-query count spikes well above its own recent average, the classic signature of malware or a compromised device beaconing out to blocklisted domains. This is deliberately not the same thing as device discovery: it's about a device you already know suddenly behaving differently, not a new device showing up.
2. **Device import** - same job as the official **PIHOLEAPI** (`pihole_api_scan`) plugin: pulls the device list from Pi-hole and feeds it into NetAlertX's normal device-scanner pipeline, so a device Pi-hole knows about but NetAlertX doesn't gets created automatically.

Both share one login per Pi-hole instance and one settings page, instead of being two separately configured pieces that happen to need the same credentials.

See the [Pi-hole guide](https://docs.netalertx.com/PIHOLE_GUIDE) for a walkthrough covering this plugin alongside the other Pi-hole integrations (`PIHOLE`, `PIHOLEAPI`, `DHCPLSS`).

Two design choices worth knowing about:

* **Both a primary and an optional secondary/failover Pi-hole are checked, and their results combined.** Watching only one leaves an obvious blind spot for the anomaly detection - a device can simply point at the other resolver and never show up. Leave the secondary URL blank if you only run one Pi-hole; most setups do.
* **The anomaly baseline is keyed by MAC address, not IP.** DHCP-assigned IPs change; since this plugin already has the device list from Pi-hole itself, it resolves IP to MAC from that same data - no separate lookup needed for that part. A device owner, if you use NetAlertX's `devOwner` field, is looked up via NetAlertX's own GraphQL API purely to make the anomaly label friendlier; it's optional and never blocks import or detection if unavailable.

### Why not just run two copies of PIHOLEAPI for two Pi-holes?

PIHOLEAPI doesn't support running two independent instances against different Pi-holes - both copies would read and write the same settings keys. PIHOLEMON was built to support a primary and secondary instance natively from the start.

### Quick setup guide

* You are running **Pi-hole v6** or newer on every instance you configure (this plugin uses `/api/auth`, `/api/network/devices`, and `/api/stats/top_clients`, none of which exist in v5).
* An **App Password** is generated on each Pi-hole (`Settings → Web Interface / API → App Password`) - recommended over using the admin login password directly.
* Like every non-core plugin, **When to run** (`PIHOLEMON_RUN`) defaults to `disabled` - set it to `schedule` (or another option) once your URL/password are filled in, or nothing runs.

#### 🔒 A note on `http://` vs `https://`

Most home Pi-hole setups (including the one this plugin was developed and tested against) run over plain `http://` on a trusted LAN, and that's what the examples below use - this plugin doesn't require `https://` or refuse an `http://` URL. Know the trade-off either way, though: over `http://`, the App Password/admin password is sent in cleartext on every run, readable by anything else that can see that network segment (a compromised device, a hostile guest network, etc.). If your Pi-hole's admin interface is reachable from anywhere less trusted than your own LAN, either put it behind `https://` (Pi-hole's own self-signed cert, or a reverse proxy with a real one) or keep it LAN-only. **Verify SSL** only matters once an instance is on `https://` - it's on by default, per instance (primary and secondary can each be on `http://` or `https://` independently), and turning it off to tolerate a self-signed cert accepts *any* certificate, including an attacker's; installing that self-signed CA as trusted on the machine running NetAlertX is the safer way to use a self-signed cert if you need one.

### Usage

- Head to **Settings** > **Pi-hole Monitor** to fill in the values below.

| Setting Key                       | Description                                                                                       |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- |
| **PIHOLEMON_PRIMARY_URL**          | Required. URL to your primary Pi-hole, e.g. `http://192.168.1.10/`.                                |
| **PIHOLEMON_PRIMARY_PASSWORD**     | App Password (or admin password) for the primary Pi-hole.                                          |
| **PIHOLEMON_PRIMARY_VERIFY_SSL**   | Verify TLS certificates on the *primary* instance's `https://` URL. Default **on**. Only disable if that Pi-hole uses a self-signed certificate you can't install as trusted - see the security note below. |
| **PIHOLEMON_SECONDARY_URL**        | Optional. URL to a secondary/failover Pi-hole, e.g. `http://192.168.1.11:8080/`. Leave blank if you only run one. |
| **PIHOLEMON_SECONDARY_PASSWORD**   | Only used if a secondary URL is set.                                                                |
| **PIHOLEMON_SECONDARY_VERIFY_SSL** | Same, for the *secondary* instance. Only used if a secondary URL is set. Default **on**.            |
| **PIHOLEMON_GET_OFFLINE**          | Import devices even if not recently seen. Default off.                                             |
| **PIHOLEMON_CONSIDER_ONLINE**      | Seconds since last seen to still count a device as online. Default `300`.                          |
| **PIHOLEMON_API_MAXCLIENTS**       | Maximum devices requested **per instance**'s device list. Default `500`.                            |
| **PIHOLEMON_FAKE_MAC**             | Generate a fake MAC from the IP for devices with a non-standard hardware address. Default off.     |
| **PIHOLEMON_GET_OWNER**            | Look up an already-known device's owner for a friendlier anomaly label. Default **on**. Uses this app's own **GRAPHQL_PORT** and **API_TOKEN** settings (Settings → General) automatically - nothing else to configure. Disable if you don't use device owners. |
| **PIHOLEMON_MULTIPLIER**           | Flag a device when the blocked queries it generated *since the last run* exceed this many times its own recent per-run average. Default `4`. |
| **PIHOLEMON_MIN_BLOCKED**          | Ignore devices below this many blocked queries since the last run, even if the multiplier is exceeded. Default `20` - depends heavily on your Schedule (see the note below the settings table). |
| **PIHOLEMON_HISTORY_DAYS**         | How many days of recent runs to keep per device for the rolling baseline. A real time window, not a sample count - means the same thing regardless of your Schedule setting, and a faster schedule just adds more data points inside it. Default `7` (one week). |
| **Watched** *(standard NetAlertX setting)* | Which columns count as "changed" for notification purposes. Defaults to `watchedValue4` (the anomaly/normal flag) only - the per-run blocked-query delta changes every run by design. |

#### A note on the blocked-query count: per-run delta, not a running total

Pi-hole's `/api/stats/top_clients` returns a count that's cumulative since Pi-hole's FTL service last started - it does not reset daily, and it's not a "since I last checked" delta. This plugin diffs each run's raw count against the one from its last run to get a real per-run increment, which is what `PIHOLEMON_MULTIPLIER`/`PIHOLEMON_MIN_BLOCKED` actually compare against - comparing the raw cumulative totals directly would make any device's traffic look like a growing "anomaly" purely from the counter never resetting. The very first run for a device, and any run right after Pi-hole/FTL restarts (the counter resets, so the raw count can drop below what was last seen), can't produce a valid delta - those runs establish a new reference point instead of evaluating an anomaly.
| **Report on** *(standard NetAlertX setting)* | Which statuses actually notify. Defaults to `watched-changed` only, so you hear about it exactly when a device flips into (or out of) an anomaly. |

This plugin does **not** send notifications on its own - it relies on NetAlertX's own core, which diffs the columns picked in **Watched** between runs and, on a match against **Report on**, dispatches through whichever publisher(s) you already have enabled under **Settings → Notifications** (ntfy, Apprise, email, Telegram, ...).

One extra setting is required for that to actually reach you: NetAlertX's **Notification Processing** plugin (`NTFPRCS`) has its own **"Notify on"** setting (`NTFPRCS_INCLUDED_SECTIONS`), and its default value - `new_devices`, `down_devices`, `events` - does **not** include `plugins`. Without `plugins` in that list, this plugin's Watched/Report on matches are recorded correctly but never make it into a notification. Add `plugins` to `NTFPRCS_INCLUDED_SECTIONS` once, and it also covers any other plugin using the same mechanism, not just this one.

The default text notification for the `plugins` section is a generic vertical `Header: Value` dump. For something more readable, set `NTFPRCS`'s **"Text Template: Plugins"** (`NTFPRCS_TEXT_TEMPLATE_plugins`) to something like:

```
{objectPrimaryId} [{watchedValue2}] @ {objectSecondaryId} → {watchedValue4} ({watchedValue3} blocked)
```

Only the columns the `plugins` section actually selects are available as placeholders (`{plugin}`, `{objectPrimaryId}`, `{objectSecondaryId}`, `{dateTimeChanged}`, `{watchedValue1-4}`, `{status}`) - `extra` (where this plugin's `owner`/`ratio` detail lives) isn't one of them, so that richer text is only visible on the device's page in NetAlertX, not in the notification itself. This template setting is global to `NTFPRCS`, so it affects any plugin using Watched/Report on, not just this one.

If the same device (same MAC) is seen on both instances, the entry with the more recent "last seen" timestamp wins - it isn't imported twice, and its blocked-query counts from both instances are summed, not compared separately.

### Testing the notification pipeline end-to-end

Waiting for real, organic beaconing traffic to confirm notifications actually arrive isn't practical. The clean way to force a `normal` → `anomaly` transition on demand, without touching any internal state file by hand:

1. Temporarily set `PIHOLEMON_MULTIPLIER` to something like `1.01` and `PIHOLEMON_MIN_BLOCKED` to `1`.
2. Run the plugin (wait for its schedule, or trigger it manually from the UI).
3. Any device with a baseline and *any* blocked traffic should now flip to `anomaly` - confirming the whole chain: Watched/Report on match → `Plugins_Events` row → NetAlertX's Notification Processing (`NTFPRCS`, needs `plugins` in `NTFPRCS_INCLUDED_SECTIONS`, see above) → your configured publisher.
4. Set `PIHOLEMON_MULTIPLIER`/`PIHOLEMON_MIN_BLOCKED` back to their real values afterward - left at the test values, everything with any traffic at all reads as an anomaly.

### ⚠️ Troubleshooting

---

#### ❌ Authentication failed / no data from a Pi-hole instance

* Confirm the URL includes the scheme (`http://`/`https://`) and, if not on the default port, the port too - e.g. `http://192.168.1.10/` ✔, `http://192.168.1.10/admin` ❌.
* Confirm that instance is running **Pi-hole v6**, not v5.
* SSL verification matches your setup (disable for self-signed certificates).
* Try the App Password by hand first: `curl -X POST <url>/api/auth -d '{"password":"<app password>"}'` should return a `session.sid`.
* Check the plugin log for `[PIHOLEMON] <label>: ...` lines - `label` is `primary` or `secondary`, so you can tell which instance is the problem.

---

#### ❌ Some devices are missing

* Devices with an invalid MAC are skipped unless **Generate fake MAC** is enabled - turning it on trades data consistency for coverage (the "MAC" becomes a stand-in derived from the IP, not a real hardware address).
* Offline devices don't get a device-import row (name/vendor) unless **Import offline devices** is enabled - but their MAC is still used to attribute blocked-query counts correctly, so an offline-but-active device never falls back to being tracked by bare IP.
* Blocked traffic from an IP Pi-hole never tied to any MAC is written out under a fake MAC derived from that IP when **Generate fake MAC** is enabled; otherwise it's only logged, with no result row, so it can't create a device whose "MAC" is the IP.

---

#### ❌ Notifications don't arrive even though an anomaly was detected

* Check NetAlertX's own **Notification Processing** settings - the `Notify on` setting (`NTFPRCS_INCLUDED_SECTIONS`) must include `plugins`, or Watched/Report on matches never reach a notification (see the note above `Watched`/`Report on` in the settings table).
* Confirm you actually have a publisher enabled and working under **Settings → Notifications** (ntfy, Apprise, email, ...) - this plugin never sends anything itself, so a working publisher there is a prerequisite, not optional.

---

#### ❌ Anomaly label missing an owner

* NetAlertX doesn't have `devOwner` set for that device yet, or the GraphQL lookup isn't reachable - neither blocks anomaly detection, the label is just less friendly.
* Confirm `PIHOLEMON_GET_OWNER` is enabled, and that this app's own **GRAPHQL_PORT**/**API_TOKEN** settings (Settings → General) are correct, if you expect owners to resolve.

---

#### ❌ Getting flagged for normal usage / not getting flagged for a real spike

* Both `PIHOLEMON_MULTIPLIER` and `PIHOLEMON_MIN_BLOCKED` are starting values, not tuned defaults - let it run for a week and adjust based on what's actually normal for your network. They apply *per run*, so if you change `PIHOLEMON_RUN_SCHD` to something much less frequent than the default, `PIHOLEMON_MIN_BLOCKED` in particular may need raising (fewer, larger runs mean more blocked queries naturally accumulate in each one).
* `PIHOLEMON_HISTORY_DAYS` is a retention window, not a detection delay. A new device becomes evaluable after its 3rd successful run: the 1st anchors the raw counter, the 2nd records the first delta into the baseline history, and the 3rd is the first one with a baseline to compare against.
* A device is also never flagged on the one run right after it's first seen, or right after Pi-hole/FTL restarts - see the delta note above the settings table.

### Notes

- Device-import parsing (online/offline handling, fake-MAC fallback, endpoints used) mirrors the official `pihole_api_scan` plugin - this isn't meant to reinvent that half, only to support a second Pi-hole instance without forking it.
- This plugin never blocks, unblocks, or otherwise changes anything on either Pi-hole - it only reads.
- The rolling per-device history is kept in its own `state.PIHOLEMON.json` file in NetAlertX's DB folder (survives upgrades, unlike the log folder) - safe to delete if you want to reset the baseline from scratch. The per-run `last_result` file stays in this plugin's log directory as usual.

- Version: 1.0.2
- Author: [mauricio-camayo](https://github.com/mauricio-camayo/)
- Release Date: `2026-08-31`
