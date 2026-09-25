#!/usr/bin/env python

"""
WIFICANARY - flags rogue APs from a periodic passive WiFi scan.

Scope (see GitHub issue #1789): only the 6 heuristics that a plain `iw scan`
snapshot can see are implemented here, plus the addendum's "known device
turned rogue" escalation (cross-referencing a detection's own BSSID against
NetAlertX's Devices table - not the deauth/probe/beacon source-MAC version
of that idea, which still needs monitor-mode data this plugin doesn't have).
Deauth/probe-flood/beacon-flood themselves need real monitor-mode frame
capture (rate over time, not a point-in-time scan) and are out of scope for
this plugin - see a dedicated monitor-mode tool (e.g. ESP32 WiFi Canary,
https://github.com/simeononsecurity/esp32-wifi-canary) for those.
"""

import json
import os
import re
import subprocess
import sys
from pytz import timezone

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

from const import logPath # noqa: E402, E261
from plugin_helper import Plugin_Objects, normalize_mac, decode_settings_base64 # noqa: E402, E261
from logger import mylog, Logger # noqa: E402, E261
from helper import get_setting_value # noqa: E402, E261
from models.device_instance import DeviceInstance # noqa: E402, E261

import conf # noqa: E402, E261

conf.tz = timezone(get_setting_value('TIMEZONE'))
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'WIFICANARY'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

plugin_objects = Plugin_Objects(RESULT_FILE)

# Global signatures, independent of any trusted-AP baseline.
PWNAGOTCHI_BSSID = 'de:ad:be:ef:de:ad'
PINEAPPLE_OUI_MID = ('13', '37')  # BSSID octets [1:3] == 13:37

# Weakest-to-strongest, used to detect a downgrade.
SECURITY_RANK = {'open': 0, 'wep': 1, 'wpa': 2, 'wpa2': 3, 'wpa3': 4}


def main():
    """Scan once, compare against the configured trusted-AP baseline, and
    emit one CurrentScan row per anomaly found."""
    mylog('verbose', [f'[{pluginName}] In script'])

    iface = get_setting_value('WIFICANARY_IFACE')
    if not iface:
        mylog('none', [f'[{pluginName}] WIFICANARY_IFACE is not set - nothing to scan'])
        plugin_objects.write_result_file()
        return 0

    trusted_aps = get_trusted_aps()
    timeout = get_setting_value('WIFICANARY_RUN_TIMEOUT') or 60

    aps = scan(iface, timeout)
    mylog('verbose', [f'[{pluginName}] Parsed {len(aps)} APs from scan on {iface}'])

    detections = []
    detections += check_global_signatures(aps)
    detections += check_trusted_aps(aps, trusted_aps)
    detections += check_duplicate_ssid(aps, trusted_aps)
    detections = dedupe_detections(detections)
    escalate_known_devices(detections)

    for det in detections:
        plugin_objects.add_object(
            primaryId=det['bssid'],
            secondaryId=det['motor'],
            watched1=det['reason'],
            watched2=det['security'],
            watched3=det['signal'],
            watched4=det['oui'],
            extra=det['ssid'],
            foreignKey=det['bssid'],
            helpVal1=normalize_mac(det['bssid']),
            helpVal2='1',        # scanCreatesDevice - every row here is an anomaly
            helpVal3='normal',   # scanNotificationMode - these are meant to alert
            helpVal4='1',        # scanPresence - detected in this scan cycle
        )

    mylog('verbose', [f'[{pluginName}] {len(detections)} anomalies'])
    plugin_objects.write_result_file()
    return 0


def get_trusted_aps():
    """Decode the WIFICANARY_trusted_aps nested setting into a list of dicts
    with ssid/bssid/security_set keys. security_set is the set of every
    encryption this network is allowed to legitimately use (e.g. a WPA2/WPA3
    transition-mode AP would list both)."""
    raw_entries = get_setting_value('WIFICANARY_trusted_aps') or []
    trusted = []
    for raw in raw_entries:
        cfg = decode_settings_base64(raw)
        ssid = cfg.get('WIFICANARY_TRUSTED_SSID', '').strip()
        if not ssid:
            continue
        bssid = cfg.get('WIFICANARY_TRUSTED_BSSID', '').strip().lower()
        trusted.append({
            'ssid': ssid,
            'bssid': normalize_mac(bssid) if bssid else '',
            'security_set': parse_security_set(cfg.get('WIFICANARY_TRUSTED_SECURITY')),
        })
    return trusted


def parse_security_set(raw_value):
    """WIFICANARY_TRUSTED_SECURITY is a multi-select `array` setting - the
    frontend sends its value as a JSON-encoded list string (e.g.
    '["wpa2","wpa3"]'), not a real list, since it travels through the
    popupForm's generic decode_settings_base64() path rather than the
    top-level array-setting one. Falls back to {'wpa2'} for a blank/missing/
    malformed value, matching config.json's own default_value."""
    if not raw_value:
        return {'wpa2'}
    try:
        values = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    except (TypeError, ValueError):
        return {'wpa2'}
    security_set = {str(v).strip().lower() for v in values if str(v).strip()}
    return security_set or {'wpa2'}


def scan(iface, timeout):
    """Run `iw dev <iface> scan` and parse the output into a list of AP dicts
    (bssid/ssid/security/signal/oui)."""
    cmd = ['sudo', 'iw', 'dev', iface, 'scan']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        mylog('none', [f'[{pluginName}] scan on {iface} timed out after {timeout}s'])
        return []
    except FileNotFoundError:
        mylog('none', [f'[{pluginName}] `iw` not found - is it installed on this host?'])
        return []

    if result.returncode != 0:
        mylog('none', [f'[{pluginName}] scan on {iface} failed: {result.stderr.strip()}'])
        return []

    return parse_iw_scan(result.stdout)


def parse_iw_scan(output):
    """Parse `iw scan` text output into a list of AP dicts."""
    aps = []
    current = None

    for line in output.splitlines():
        bss_match = re.match(r'^BSS ([0-9a-fA-F:]{17})', line)
        if bss_match:
            if current and current.get('ssid'):
                aps.append(current)
            current = {
                'bssid': bss_match.group(1).lower(),
                'ssid': '',
                'security': 'open',
                'signal': '',
            }
            continue

        if current is None:
            continue

        stripped = line.strip()

        m = re.match(r'^SSID:\s?(.*)$', stripped)
        if m:
            current['ssid'] = m.group(1)
            continue

        if stripped.startswith('capability:') and 'Privacy' in stripped:
            if current['security'] == 'open':
                # Privacy bit set but no RSN/WPA IE found below -> most likely WEP
                # (or a TKIP-only WPA1 network with no separate IE, rare in practice).
                current['security'] = 'wep'

        if stripped.startswith('RSN:'):
            current['security'] = 'wpa2'
            continue

        if stripped.startswith('WPA:'):
            if current['security'] not in ('wpa2', 'wpa3'):
                current['security'] = 'wpa'
            continue

        if 'Authentication suites' in stripped and 'SAE' in stripped:
            current['security'] = 'wpa3'
            continue

        m = re.match(r'^signal:\s*(-?\d+(?:\.\d+)?)\s*dBm', stripped)
        if m:
            current['signal'] = m.group(1)

    if current and current.get('ssid'):
        aps.append(current)

    for ap in aps:
        parts = ap['bssid'].split(':')
        ap['oui'] = ':'.join(parts[0:3]) if len(parts) >= 3 else ''

    return aps


def check_global_signatures(aps):
    """Motors 1-2: absolute signatures that don't depend on any baseline -
    a known pwnagotchi BSSID, or a WiFi Pineapple's default OUI pattern."""
    found = []
    for ap in aps:
        parts = ap['bssid'].split(':')

        if ap['bssid'] == PWNAGOTCHI_BSSID:
            found.append(make_detection(ap, 'pwnagotchi_nearby',
                         f"Pwnagotchi signature BSSID seen ({ap['bssid']})"))

        if len(parts) >= 3 and (parts[1], parts[2]) == PINEAPPLE_OUI_MID:
            found.append(make_detection(ap, 'pineapple_oui',
                         f"WiFi Pineapple default OUI pattern on BSSID {ap['bssid']}"))

    return found


def is_downgrade(observed_security, accepted):
    """True if `observed_security` is neither explicitly accepted nor at
    least as strong as the strongest accepted value - the shared threshold
    check_trusted_aps() uses for both a known radio weakening over time and
    a different radio cloning the SSID with lesser security."""
    if observed_security in accepted:
        return False
    observed_rank = SECURITY_RANK.get(observed_security, 0)
    strongest_accepted_rank = max(SECURITY_RANK.get(s, 0) for s in accepted)
    return observed_rank < strongest_accepted_rank


def check_trusted_aps(aps, trusted_aps):
    """Motors 3-5: evil twin / weaker-security clone, baseline AP absent
    while a clone is present, and security downgrade - all evaluated
    against the user's trusted-AP baseline (WIFICANARY_trusted_aps)."""
    found = []

    # Every explicitly-trusted BSSID, grouped by SSID - lets a match get
    # excluded from another entry's evaluation below (each trusted radio
    # is judged only against its own entry's accepted set, not a sibling
    # entry's - e.g. a main AP requiring wpa3 must not flag a legitimately
    # separately-trusted extender that only accepts wpa2).
    trusted_bssids_by_ssid = {}
    for t in trusted_aps:
        if t['bssid']:
            trusted_bssids_by_ssid.setdefault(t['ssid'], set()).add(t['bssid'])

    for trust in trusted_aps:
        matches = [ap for ap in aps if ap['ssid'] == trust['ssid']]
        other_trusted_bssids = trusted_bssids_by_ssid.get(trust['ssid'], set()) - {trust['bssid']}
        baseline_bssid_seen = any(ap['bssid'] == trust['bssid'] for ap in matches) if trust['bssid'] else True
        accepted = trust['security_set']
        expected_desc = ' or '.join(sorted(accepted))

        for ap in matches:
            if ap['bssid'] in other_trusted_bssids:
                continue  # evaluated against its own trusted entry instead

            if not is_downgrade(ap['security'], accepted):
                continue

            same_radio = trust['bssid'] and ap['bssid'] == trust['bssid']

            if same_radio or not trust['bssid']:
                # The radio we already trust for this SSID (or, with no
                # BSSID configured, the only radio we have to go on).
                found.append(make_detection(ap, 'security_downgrade',
                             f"'{trust['ssid']}' now broadcasting {ap['security']}, "
                             f"expected {expected_desc}"))
                continue

            # A different BSSID broadcasting the same protected SSID with
            # weaker-than-accepted security. A same- or stronger-encrypted
            # different radio is check_duplicate_ssid's job instead, via
            # OUI mismatch, not this one's.
            if trust['bssid'] and not baseline_bssid_seen:
                found.append(make_detection(ap, 'absent_baseline_clone',
                             f"'{trust['ssid']}' baseline AP ({trust['bssid']}) missing, "
                             f"weaker clone ({ap['security']}) seen on {ap['bssid']}"))
            else:
                found.append(make_detection(ap, 'evil_twin',
                             f"'{trust['ssid']}' cloned with weaker security ({ap['security']}) "
                             f"by {ap['bssid']} (expected {expected_desc})"))

    return found


def check_duplicate_ssid(aps, trusted_aps):
    """Motor 6: a trusted SSID broadcast by more than one OUI at once - a
    plausible impostor sharing a protected network's name. Restricted to
    SSIDs the user has explicitly claimed via the trusted-AP list, so an
    untracked network's own AP diversity (e.g. a cafe chain) never triggers
    this. A real multi-radio setup for the *same* trusted SSID (a range
    extender, a mesh kit - often a different OUI than the main AP) is
    expected to be listed as its own WIFICANARY_trusted_aps entry (same
    SSID, its own BSSID) - every trusted BSSID's OUI for a given SSID is
    whitelisted, not just one."""
    trusted_ssids = {t['ssid'] for t in trusted_aps}
    trusted_ouis_by_ssid = {}
    for t in trusted_aps:
        if t['bssid']:
            trusted_ouis_by_ssid.setdefault(t['ssid'], set()).add(':'.join(t['bssid'].split(':')[:3]))

    found = []

    by_ssid = {}
    for ap in aps:
        if ap['ssid'] in trusted_ssids:
            by_ssid.setdefault(ap['ssid'], []).append(ap)

    for ssid, group in by_ssid.items():
        ouis = {ap['oui'] for ap in group}
        if len(ouis) < 2:
            continue

        trusted_ouis = trusted_ouis_by_ssid.get(ssid)
        if trusted_ouis:
            # One or more explicit trusted BSSIDs exist for this SSID -
            # their OUIs are the whitelist. Anything else sharing the SSID
            # is suspect regardless of how common it is in this scan.
            for ap in group:
                if ap['oui'] not in trusted_ouis:
                    found.append(make_detection(ap, 'duplicate_ssid_diff_vendor',
                                 f"'{ssid}' also seen from OUI {ap['oui']} on {ap['bssid']} "
                                 f"(trusted OUIs for this SSID are {', '.join(sorted(trusted_ouis))})"))
            continue

        # No trusted BSSID configured for this SSID (wildcard-only entry) -
        # fall back to majority OUI as the presumed "expected" one.
        primary_oui = max(ouis, key=lambda o: sum(1 for ap in group if ap['oui'] == o))
        for ap in group:
            if ap['oui'] != primary_oui:
                found.append(make_detection(ap, 'duplicate_ssid_diff_vendor',
                             f"'{ssid}' also seen from OUI {ap['oui']} on {ap['bssid']} "
                             f"(other APs for this SSID are {primary_oui})"))

    return found


def dedupe_detections(detections):
    """Collapse detections sharing the same (bssid, motor) identity -
    check_trusted_aps() can otherwise flag one rogue clone once per
    WIFICANARY_trusted_aps entry sharing its SSID (e.g. a main AP + range
    extender pair). Keeps the first occurrence of each identity."""
    seen = set()
    deduped = []
    for det in detections:
        key = (det['bssid'], det['motor'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(det)
    return deduped


def escalate_known_devices(detections):
    """Motor 10 (see the addendum on issue #1789): a BSSID this plugin just
    flagged might not be a stranger's radio at all - it might be a device
    NetAlertX already knows and trusts, now behaving like an attacker
    (compromised firmware, a misconfigured AP mode, etc). That's a much
    more urgent signal than "unknown pineapple nearby", so it's called out
    separately - mutates each matching detection's motor/reason in place
    rather than returning a new list.

    One DeviceInstance().getAllByMacs() call for every distinct BSSID in this
    run, not one getByMac() per detection - a run can easily produce several
    detections (multiple motors firing on the same BSSID, or several rogue
    APs at once), and each would otherwise be its own DB round-trip.

    Only escalates when the existing Devices row was NOT itself created by
    a previous WIFICANARY run - otherwise every anomaly would trivially
    "escalate" against its own prior detection from run 2 onward."""
    bssids = [det['bssid'] for det in detections]
    known_by_mac = DeviceInstance().getAllByMacs(bssids)

    for det in detections:
        existing = known_by_mac.get(det['bssid'].lower())
        if not existing or (existing.get('devSourcePlugin') or '') == 'WIFICANARY':
            continue

        device_label = existing.get('devName') or det['bssid']
        det['motor'] = f"{det['motor']}_known_device"
        det['reason'] = f"Known device '{device_label}' now behaving like a rogue AP: {det['reason']}"


def make_detection(ap, motor, reason):
    """Build the dict consumed by main()'s add_object() call for one AP anomaly."""
    return {
        'bssid': ap['bssid'],
        'ssid': ap['ssid'] or 'null',
        'motor': motor,
        'reason': reason,
        'security': ap['security'],
        'signal': ap['signal'] or 'null',
        'oui': ap['oui'] or 'null',
    }


if __name__ == '__main__':
    main()
