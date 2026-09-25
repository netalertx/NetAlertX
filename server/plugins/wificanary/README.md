## Overview

Runs a periodic passive WiFi scan (`iw scan`, no monitor mode) and flags rogue APs against a baseline you define: pwnagotchi/WiFi Pineapple signatures, evil-twin/open clones of a protected SSID, a protected AP going missing while a clone is visible, security downgrades, and a protected SSID suddenly broadcast from an unexpected vendor. Originated from [issue #1789](https://github.com/netalertx/NetAlertX/issues/1789), which also covers why deauth/probe-flood/beacon-flood detection is intentionally **not** included here - those need real monitor-mode frame capture, not a scan snapshot. For that, pair this plugin with a dedicated monitor-mode tool such as [ESP32 WiFi Canary](https://github.com/simeononsecurity/esp32-wifi-canary).

### Requirements

- A WiFi interface reachable from the NetAlertX host, in station mode (monitor mode is *not* required - a normal onboard or USB WiFi adapter is enough). If your NetAlertX host has no WiFi hardware, this plugin has nothing to scan with.
- The image ships `iw` with `cap_net_raw,cap_net_admin` already set (same treatment as `arp-scan`/`nmap`/`nbtscan`/`traceroute`), so the plugin can scan as the non-root runtime user without real `sudo`. You still need a WiFi interface actually visible to the container, e.g. via host networking.

### Usage

- Set `WIFICANARY_IFACE` to your wireless interface (e.g. `wlan0`).
- Add each network you want protected to `WIFICANARY_trusted_aps` - SSID, optionally its BSSID (recommended: without a BSSID, the evil-twin/absent-baseline checks fall back to matching on SSID alone), and every encryption you'd accept from it (select more than one for a WPA2/WPA3-transition-mode AP).
- Have a range extender or mesh node broadcasting the same SSID as your main AP? Add it as its **own** `WIFICANARY_trusted_aps` entry (same SSID, its own BSSID/security) rather than leaving it out - a real extender is very often a different vendor/OUI than the main router, and every trusted BSSID's OUI for a given SSID is treated as legitimate, not just the first one.
- Enable the plugin (`WIFICANARY_RUN` → `schedule`) and set a schedule in `WIFICANARY_RUN_SCHD`.
- A detection creates a new, dangerous-by-default `Devices` entry for the rogue BSSID (even though it never associated with your network) - turn off `WIFICANARY_IMPORT_ON` if you'd rather tune your trusted-AP list against the plugin's history first, without devices being created yet.
- Pwnagotchi and WiFi Pineapple signature checks run unconditionally, regardless of `WIFICANARY_trusted_aps`.
- If a detected rogue BSSID turns out to already be a device NetAlertX knows from another source (ARP, DHCP, an importer...), the finding is escalated in place - the reason is rewritten to name the known device, and the motor gets a `_known_device` suffix (e.g. `evil_twin_known_device`) so a [Workflow](https://docs.netalertx.com/WORKFLOWS) rule can route it to a more urgent channel than a stranger's radio.

### Notes

- Vendor names for a rogue device do show up in the GUI, but not from this plugin - a `Devices` row it creates gets its `Vendor` field filled in by core's own `VNDRPDT` (vendor_update) plugin on its next run, same as any other device. That lookup is a local OUI-database match, not a network call, so it's deliberately kept out of the scan step itself.
- The duplicate-SSID/different-vendor check only looks at SSIDs you've listed in `WIFICANARY_trusted_aps` - an untracked network's own AP diversity (e.g. a cafe chain) is never flagged. For a tracked SSID, every explicitly-trusted BSSID's OUI is whitelisted (see the range-extender note above) - only an OUI that matches *none* of them gets flagged. "Vendor" here means OUI (BSSID's first 3 octets) compared directly between the APs sharing an SSID, not a vendor-name lookup.
- `WIFICANARY_TRUSTED_SECURITY` is multi-select. An observed encryption exactly matching any selected value is always accepted; otherwise it's flagged if it's weaker than the *strongest* value you selected - deliberately, not a typo: comparing against the weakest would make selecting more than one value pointless (anything at or above the weakest would silently pass either way, making the rest of the selection meaningless). Worked example for `wep` + `wpa2` selected:

  | Observed | Result |
  |---|---|
  | `wep` | OK (listed) |
  | `wpa2` | OK (listed) |
  | `wpa` | **Alert** - not listed, and weaker than `wpa2` |
  | `open` | **Alert** - weaker than everything |

  Select `open` here only for a network you intend to run unencrypted on purpose (e.g. a guest SSID) - otherwise leave it out so an unexpected open clone or downgrade still trips an alert.
- Encryption is classified from the `iw scan` IEs into `open` / `wep` / `wpa` / `wpa2` / `wpa3`. A `Privacy`-flagged AP with neither an `RSN` nor a `WPA` information element is reported as `wep` - the closest reasonable guess for that combination, not a certainty.
- See the [WIFICANARY addendum on issue #1789](https://github.com/netalertx/NetAlertX/issues/1789#issuecomment-5777023835) for the reasoning behind creating a device for never-associated attacker BSSIDs, and for the "known device turned rogue" idea. The implemented version above only covers the BSSID-identity angle (is the radio itself a device you already trust?) - the addendum's original, richer version (cross-referencing the *source MAC of attack traffic* like deauth/probe floods) still needs monitor-mode data this plugin doesn't have.

- Author: `mauricio-camayo`
