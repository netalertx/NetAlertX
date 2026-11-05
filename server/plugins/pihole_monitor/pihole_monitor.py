#!/usr/bin/env python
"""NetAlertX plugin: PIHOLEMON — Pi-hole Monitor

Does two jobs against the same Pi-hole connection(s), instead of two
separately configured plugins:

  1. Device import (same job as the official PIHOLEAPI/pihole_api_scan
     plugin): pulls the device list from Pi-hole's `/api/network/devices`
     and feeds it into NetAlertX's normal device-scanner pipeline
     (mapped_to_table=CurrentScan), so devices Pi-hole knows about but
     NetAlertX doesn't get created automatically.

  2. Query anomaly detection: pulls `/api/stats/top_clients?blocked=true`
     and flags a device whose blocked-query count spikes well above its
     own recent rolling average - the signature of malware/a compromised
     device beaconing out, not just "a lot of DNS traffic".

Why one plugin instead of two: they need the exact same Pi-hole session
(auth once, reuse for both endpoints) and the exact same "primary +
optional secondary" source list, so splitting them would mean either two
logins per source or two separately configured URL/password pairs to keep
in sync. One plugin, one settings page, one login per source.

Why not just run two copies of the official PIHOLEAPI plugin for two
Pi-holes: we looked into this first. `pihole_api_scan.py` hardcodes its
settings-key prefix (`PIHOLEAPI_URL`, `PIHOLEAPI_PASSWORD`, ...) as literal
strings throughout the script rather than reading it from `config.json`.
Duplicating the plugin folder gives you two copies that both read and
write the *same* settings keys - not two independent instances - and
NetAlertX's own plugin docs don't describe an officially supported way to
run multiple instances of one plugin. Making a real second instance would
mean forking the script and renaming every occurrence of the prefix by
hand, then keeping that fork in sync with any upstream changes by hand
too. This plugin exists so none of that is necessary: it accepts a second
set of credentials natively, and the secondary instance is entirely
optional - leave its URL blank and this behaves like a single-Pi-hole
import, which covers most setups.
"""

import os
import sys
import json

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects, is_mac  # noqa: E402
from utils.datetime_utils import timeNowUTC  # noqa: E402
from logger import mylog, Logger  # noqa: E402
from helper import get_setting_value  # noqa: E402
from const import logPath, dbFolderPath  # noqa: E402
import conf  # noqa: E402
from pytz import timezone  # noqa: E402
from utils.crypto_utils import string_to_fake_mac  # noqa: E402

conf.tz = timezone(get_setting_value('TIMEZONE'))
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'PIHOLEMON'
VERSION_DATE = "NAX-PIHOLEMON-1.0"

LOG_PATH = logPath + '/plugins'
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')
# Lives in the DB folder, not LOG_PATH: logs are routinely wiped on upgrade,
# which would silently reset every device's anomaly baseline.
STATE_FILE = os.path.join(dbFolderPath, f'state.{pluginName}.json')

REQUEST_TIMEOUT_DEFAULT = 30


class PiholeSource:
    """One Pi-hole instance's connection + auth state, kept isolated from
    any other instance so two can run side by side without interfering."""

    def __init__(self, label, url, password, verify_ssl, run_timeout):
        """Store this instance's connection details. Does not connect -
        call auth() to actually log in."""
        self.label = label
        self.url = url.rstrip('/') + '/' if url else None
        self.password = password
        self.verify_ssl = verify_ssl
        self.run_timeout = run_timeout
        self.sid = None
        self.csrf = None

    @property
    def configured(self):
        """True if a URL was set for this instance (the secondary one is
        optional and left unconfigured in most setups)."""
        return bool(self.url)

    def auth(self):
        """Log in to this instance's /api/auth, storing the session id and
        CSRF token for subsequent requests. Returns False (and logs why)
        on any failure - never raises, so one bad source doesn't abort
        the whole run."""
        if not self.configured:
            return False

        if not self.verify_ssl:
            requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "User-Agent": "NetAlertX/" + VERSION_DATE,
        }
        try:
            resp = requests.post(
                self.url + 'api/auth',
                headers=headers,
                json={"password": self.password},
                verify=self.verify_ssl,
                timeout=self.run_timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            mylog('none', [f'[{pluginName}] {self.label}: auth request timed out. Try increasing the run timeout.'])
            return False
        except requests.exceptions.ConnectionError:
            mylog('none', [f'[{pluginName}] {self.label}: connection error during auth. Check the URL and password.'])
            return False
        except Exception as e:
            mylog('none', [f'[{pluginName}] {self.label}: unexpected auth error: {e}'])
            return False

        try:
            session_data = resp.json().get('session', {})
        except Exception:
            mylog('none', [f'[{pluginName}] {self.label}: unable to parse auth response JSON.'])
            return False

        if not session_data.get('valid', False):
            mylog('none', [f'[{pluginName}] {self.label}: auth required or failed.'])
            return False

        self.sid = session_data.get('sid')
        self.csrf = session_data.get('csrf')
        mylog('verbose', [f'[{pluginName}] {self.label}: authenticated (sid present).'])
        return True

    def deauth(self):
        """Best-effort logout so this instance doesn't accumulate sessions
        across runs. Never raises - a failed logout isn't worth failing
        the run over."""
        if not self.configured or not self.sid:
            return
        try:
            requests.delete(
                self.url + 'api/auth',
                headers={"X-FTL-SID": self.sid},
                verify=self.verify_ssl,
                timeout=self.run_timeout,
            )
        except Exception:
            pass  # best-effort logout
        self.sid = None
        self.csrf = None

    def _headers(self):
        """Auth headers for an authenticated request against this instance."""
        headers = {"X-FTL-SID": self.sid}
        if self.csrf:
            headers["X-FTL-CSRF"] = self.csrf
        return headers

    def fetch_devices(self, max_clients):
        """Raw 'devices' list from Pi-hole's network/devices endpoint - MAC,
        IP(s), hostname, vendor, last-seen. Used for device import."""
        if not self.sid:
            return []
        params = {'max_devices': str(max_clients), 'max_addresses': '2'}
        try:
            resp = requests.get(
                self.url + 'api/network/devices',
                headers=self._headers(),
                params=params,
                verify=self.verify_ssl,
                timeout=self.run_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            mylog('debug', [f'[{pluginName}] {self.label}: devices API returned data: {json.dumps(data)}'])
            return data.get('devices', [])
        except Exception as e:
            mylog('none', [f'[{pluginName}] {self.label}: failed to fetch devices: {e}'])
            return []

    def fetch_top_blocked_clients(self, count):
        """{ip: blocked_count} for this instance, used for anomaly detection.

        Each blocked_count is Pi-hole's raw counter value, cumulative since
        FTL last started - not a per-interval or "since last poll" count,
        and it does not reset daily. Callers must diff it against the
        previous run's value (see compute_delta()) before comparing it to
        anything; used raw, it would make any device's ordinary traffic
        look like a runaway anomaly purely from the counter never resetting.

        `count` should cover every client Pi-hole is tracking, not just a
        handful - Pi-hole's own API default (10) truncates silently, so a
        caller that doesn't pass an explicit count would never see clients
        past that cutoff. Returns None (not {}) on any failure to fetch or
        parse the response, so callers can tell "no source authenticated
        for this instance right now" apart from "this instance genuinely
        has no blocked queries this run" - treating the two the same would
        write a false zero into a device's history and dilute its baseline.
        """
        if not self.sid:
            return None
        try:
            resp = requests.get(
                self.url + 'api/stats/top_clients',
                headers=self._headers(),
                params={"blocked": "true", "count": count},
                verify=self.verify_ssl,
                timeout=self.run_timeout,
            )
            resp.raise_for_status()
            clients = resp.json().get("clients", [])
            return {c["ip"]: c.get("count", 0) for c in clients if c.get("ip")}
        except Exception as e:
            mylog('none', [f'[{pluginName}] {self.label}: failed to fetch top_clients: {e}'])
            return None


def gather_device_entries(source, consider_online, fake_mac, max_clients):
    """Same parsing logic as the official PIHOLEAPI plugin, scoped to one source.

    Returns every device/IP pair Pi-hole knows about, each tagged with
    is_online. Callers decide separately what to do with that flag:
    device-import rows should skip offline devices unless GET_OFFLINE is
    set, but the IP->MAC identity mapping (used to attribute blocked-query
    counts to the right device) must NOT skip them - Pi-hole's own "last
    seen" can lag behind real DNS activity, so a device it currently calls
    offline can still be the one generating the blocked queries in this
    same run. Dropping it there would misattribute the traffic to a bare
    IP instead of the device's real MAC.
    """
    entries = []
    devices = source.fetch_devices(max_clients)
    now_ts = int(timeNowUTC(as_string=False).timestamp())

    for device in devices:
        hwaddr = device.get('hwaddr')
        # "ip-<address>" is Pi-hole's own placeholder for "no real MAC known,
        # falling back to identifying by IP" - not just the "ip-::" (IPv6)
        # case, any address. Caught downstream by is_mac() either way, but
        # this is the actual placeholder check, so it should recognize the
        # whole pattern.
        if not hwaddr or hwaddr == "00:00:00:00:00:00" or hwaddr.startswith("ip-"):
            continue

        device_ips = device.get('ips', [])
        if not device_ips:
            continue

        max_last_seen = max((ip_info.get('lastSeen', 0) for ip_info in device_ips), default=0)
        is_online = (now_ts - max_last_seen) <= consider_online

        mac_vendor = device.get('macVendor', '')

        for ip_info in device_ips:
            ip = ip_info.get('ip')
            if not ip or ip in ["0.0.0.0", "::"]:
                continue

            name = ip_info.get('name') or ''
            tmp_mac = hwaddr.lower()

            if fake_mac and not is_mac(tmp_mac):
                tmp_mac = string_to_fake_mac(ip)

            entries.append({
                'mac': tmp_mac,
                'ip': ip,
                'name': name,
                'macVendor': mac_vendor,
                'lastSeen': max_last_seen,
                'is_online': is_online,
            })

    return entries


def merge_device_entries(all_entries):
    """One entry per MAC - the freshest, if the same device shows up on both
    Pi-hole instances (usually with the same IP, but not always)."""
    merged = {}
    for entry in all_entries:
        current = merged.get(entry['mac'])
        if current is None or entry['lastSeen'] > current['lastSeen']:
            merged[entry['mac']] = entry
    return merged


def build_ip_to_mac(all_entries):
    """Map every IP Pi-hole has ever associated with a device to that
    device's MAC, for attributing blocked-query counts (which only come
    back as IPs) to the right device.

    Deliberately built from every gathered entry, not from
    merge_device_entries()'s output: a device with more than one IP gets
    one entry per IP in `all_entries`, but merge_device_entries() keeps
    only the single freshest entry per MAC - so deriving the IP map from
    its result would silently drop that device's other IPs, and any
    blocked-query traffic seen from those would fall back to being
    tracked under a bare IP instead of the device's real MAC. If two
    different MACs were ever seen on the same IP (e.g. a DHCP
    reassignment), the entry with the freshest lastSeen wins that IP.
    """
    ip_to_mac = {}
    ip_last_seen = {}
    for entry in all_entries:
        ip = entry['ip']
        if ip not in ip_to_mac or entry['lastSeen'] > ip_last_seen[ip]:
            ip_to_mac[ip] = entry['mac']
            ip_last_seen[ip] = entry['lastSeen']
    return ip_to_mac


def netalertx_device_owners(graphql_url, token, run_timeout):
    """{mac: devOwner} for every device NetAlertX already knows about, purely
    for a friendlier anomaly label. Fetched once per run rather than once per
    device - on a network with hundreds of devices, one query beats hundreds
    of blocking round-trips to the same endpoint. Returns {} if unavailable,
    unset, or on any error - never blocks device import or anomaly detection."""
    if not graphql_url:
        return {}

    query = """
    query GetDevices {
      devices {
        devices { devMac devOwner }
      }
    }
    """

    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = requests.post(
            graphql_url,
            json={"query": query},
            headers=headers,
            timeout=run_timeout,
        )
        resp.raise_for_status()
        devices = resp.json().get("data", {}).get("devices", {}).get("devices", [])
        return {d["devMac"]: d.get("devOwner") or '' for d in devices if d.get("devMac")}
    except Exception as e:
        mylog('debug', [f'[{pluginName}] GraphQL owner lookup failed: {e}'])
        return {}


def load_state():
    """Per-key {"last_raw": {source_label: int}, "history": [[timestamp,
    delta], ...]} from past runs, or {} on first run / a missing or corrupt
    state file (never fatal - just starts fresh). last_raw is keyed by
    source, not a single number, so each Pi-hole instance gets its own
    diff reference point - see aggregate_source_deltas()."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    """Persist per-key last-raw-count + delta history for next run's diff
    and baseline."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def trim_history(history, now_ts, history_days):
    """Drop samples older than history_days from `history` ([timestamp,
    delta] pairs). An age cutoff, not a count: the window means the same
    real-world span regardless of how often this plugin happens to run - a
    faster schedule just adds more samples inside that same window instead
    of shrinking it, and a slower one doesn't stretch it out."""
    cutoff = now_ts - history_days * 86400
    return [sample for sample in history if sample[0] >= cutoff]


def compute_delta(last_raw, current_raw):
    """Turn Pi-hole's raw blocked-query count (cumulative since FTL last
    started, *not* a per-interval count - confirmed against FTL's own
    source and long-standing user reports that it doesn't reset at
    midnight) into a per-run increment, which is what's actually
    comparable against a rolling baseline.

    Returns None (not 0) when there's nothing valid to diff against yet:
    the first time this device is seen (last_raw is None), or when
    current_raw < last_raw - Pi-hole/FTL restarted and the counter reset,
    or the device simply dropped out of top_clients this run. A caller
    must not treat None as a real zero: a genuine 0 means "no new blocked
    queries since last run", while None means "we can't tell this run" -
    conflating them would either manufacture a fake anomaly out of a
    restart, or silently swallow a real one right after."""
    if last_raw is None or current_raw < last_raw:
        return None
    return current_raw - last_raw


def aggregate_source_deltas(last_raw_by_source, raw_by_source):
    """Combine each configured source's raw count into one delta for a
    device, computing every source's delta independently (via
    compute_delta()) before summing - never by summing the raw totals
    first and diffing once. Summing raw totals first would let one
    source's counter reset silently net out against real traffic on
    another: e.g. primary +2000 (a real spike) and secondary resetting
    from 1000 to 5 (-995) would combine into a raw delta of only 1005,
    hiding most of the primary's actual spike behind the secondary's
    unrelated restart.

    `raw_by_source` only needs entries for sources that reported this
    device this run - a source that didn't (auth failed, or the device
    simply wasn't in that instance's top_clients) is skipped for this run
    without affecting the others.

    Returns (delta, updated_last_raw_by_source):
      - delta is None only if none of the sources present this run
        produced a valid delta (e.g. all are bootstrapping or just
        reset) - same None-means-"can't tell" contract as
        compute_delta(). If at least one source has a valid delta, it's
        included even if another source in the same run doesn't.
      - updated_last_raw_by_source carries every source's newest raw
        value forward (valid delta or not), so each source keeps its own
        independent reference point for the next run.
    """
    updated = dict(last_raw_by_source)
    total = 0
    any_valid = False
    for label, raw in raw_by_source.items():
        delta = compute_delta(last_raw_by_source.get(label), raw)
        updated[label] = raw
        if delta is not None:
            total += delta
            any_valid = True
    return (total if any_valid else None), updated


def main():
    """Entry point: authenticate to every configured Pi-hole instance,
    import its devices, evaluate blocked-query anomalies against each
    device's rolling history, and write both out. Returns 0 on a normal
    run, 1 if no Pi-hole instance is configured at all."""
    run_timeout = get_setting_value('PIHOLEMON_RUN_TIMEOUT') or REQUEST_TIMEOUT_DEFAULT
    get_offline = bool(get_setting_value('PIHOLEMON_GET_OFFLINE'))
    fake_mac = bool(get_setting_value('PIHOLEMON_FAKE_MAC'))
    max_clients = get_setting_value('PIHOLEMON_API_MAXCLIENTS') or 500
    consider_online = get_setting_value('PIHOLEMON_CONSIDER_ONLINE')
    if not isinstance(consider_online, int):
        consider_online = 300

    # The user only decides whether to look up the owner at all - the
    # endpoint itself is derived from this app's own GRAPHQL_PORT (single
    # source of truth) instead of being a second, easily stale copy of it.
    graphql_url = f"http://127.0.0.1:{get_setting_value('GRAPHQL_PORT')}/graphql" if get_setting_value('PIHOLEMON_GET_OWNER') else None
    # Reuse this app's own API token rather than keep a second, easily
    # forgotten copy of it in this plugin's settings.
    graphql_token = get_setting_value('API_TOKEN')
    multiplier = float(get_setting_value('PIHOLEMON_MULTIPLIER') or 4)
    min_blocked = int(get_setting_value('PIHOLEMON_MIN_BLOCKED') or 20)
    # Days, not run count: a run-count window silently shrinks or stretches
    # in real time whenever RUN_SCHD changes (or differs between users), so
    # the baseline it produces means something different depending on how
    # often the plugin happens to run. A day-based window means the same
    # thing regardless of schedule, and a faster schedule only adds more
    # data points within that same window instead of shortening it.
    # Clamped to at least 1 for the same reason as elsewhere: 0 already
    # falls back to 7 via `or`, but a negative setting would otherwise
    # produce a nonsensical, hard-to-debug cutoff below.
    history_days = max(1, int(get_setting_value('PIHOLEMON_HISTORY_DAYS') or 7))

    sources = [
        PiholeSource(
            'primary',
            get_setting_value('PIHOLEMON_PRIMARY_URL'),
            get_setting_value('PIHOLEMON_PRIMARY_PASSWORD'),
            bool(get_setting_value('PIHOLEMON_PRIMARY_VERIFY_SSL')),
            run_timeout,
        ),
        PiholeSource(
            'secondary',
            get_setting_value('PIHOLEMON_SECONDARY_URL'),
            get_setting_value('PIHOLEMON_SECONDARY_PASSWORD'),
            bool(get_setting_value('PIHOLEMON_SECONDARY_VERIFY_SSL')),
            run_timeout,
        ),
    ]
    configured_sources = [s for s in sources if s.configured]
    if not configured_sources:
        mylog('none', [f'[{pluginName}] No Pi-hole URL configured - nothing to do.'])
        return 1

    all_device_entries = []
    # Pi-hole's raw, cumulative-since-FTL-started counts (see
    # compute_delta()'s docstring), kept separate per source until each
    # source's own delta is computed - see aggregate_source_deltas()'
    # docstring for why combining the raw totals across sources first
    # (before diffing) would be wrong.
    blocked_by_source_ip = {}
    # False if any configured source failed to authenticate or its
    # top_clients fetch failed - the blocked-query counts for this run are
    # then incomplete for reasons unrelated to real traffic, so anomaly
    # evaluation and history persistence are skipped below rather than
    # risk writing a false "quiet run" into a device's baseline.
    stats_complete = True

    for source in configured_sources:
        if not source.auth():
            mylog('none', [f'[{pluginName}] {source.label}: authentication failed - skipping this source.'])
            stats_complete = False
            continue
        try:
            all_device_entries.extend(
                gather_device_entries(source, consider_online, fake_mac, max_clients)
            )
            top_blocked = source.fetch_top_blocked_clients(count=max_clients)
            if top_blocked is None:
                stats_complete = False
            else:
                blocked_by_source_ip[source.label] = top_blocked
        finally:
            source.deauth()

    # IP->MAC identity mapping uses every device Pi-hole knows about,
    # online or not (see gather_device_entries docstring for why), and is
    # built from every entry rather than the by-MAC merge below so a
    # multi-IP device doesn't lose its other IPs (see build_ip_to_mac).
    ip_to_mac = build_ip_to_mac(all_device_entries)

    # Device-import rows (name/vendor) still respect GET_OFFLINE.
    importable_entries = [e for e in all_device_entries if e['is_online'] or get_offline]
    for entry in all_device_entries:
        if not entry['is_online'] and not get_offline:
            mylog('verbose', [f"[{pluginName}]: skipping offline device import for {entry['mac']} ({entry['ip']})."])
    devices_by_mac = merge_device_entries(importable_entries)

    # Combine blocked-query counts per MAC, still kept separate per source
    # (see aggregate_source_deltas()). An IP Pi-hole has genuinely never
    # associated with any MAC (not even an offline one) is keyed by a fake
    # MAC derived from that IP when FAKE_MAC is on - same as device import -
    # or else tracked under the bare IP for anomaly logging only, never
    # written out as a result row (see the results loop).
    blocked_by_mac_by_source = {}
    for label, ip_counts in blocked_by_source_ip.items():
        mac_counts = {}
        for ip, count in ip_counts.items():
            key = ip_to_mac.get(ip)
            if key is None:
                key = string_to_fake_mac(ip) if fake_mac else ip
            mac_counts[key] = mac_counts.get(key, 0) + count
        blocked_by_mac_by_source[label] = mac_counts

    if not stats_complete:
        mylog(
            'none',
            [f'[{pluginName}] Blocked-query data is incomplete for this run '
             '(a source failed to authenticate or its top_clients fetch failed) - '
             'skipping anomaly evaluation and history updates so a real outage '
             'doesn\'t get recorded as a quiet run.'],
        )

    state = load_state()
    plugin_objects = Plugin_Objects(RESULT_FILE)
    blocked_keys = {key for mac_counts in blocked_by_mac_by_source.values() for key in mac_counts}
    all_keys = set(devices_by_mac.keys()) | blocked_keys
    # One batched lookup for the whole run instead of one per device - see
    # netalertx_device_owners' docstring.
    owners_by_mac = netalertx_device_owners(graphql_url, graphql_token, run_timeout)
    now_ts = int(timeNowUTC(as_string=False).timestamp())

    for key in all_keys:
        device = devices_by_mac.get(key)
        mac = key if is_mac(key) else None

        entry = state.get(key, {})
        # A plain number here is a pre-existing state file from before
        # last_raw was tracked per source - treat it the same as no prior
        # reference point at all (every source bootstraps fresh) rather
        # than crash on it.
        last_raw_by_source = entry.get("last_raw", {})
        if not isinstance(last_raw_by_source, dict):
            last_raw_by_source = {}
        history = trim_history(entry.get("history", []), now_ts, history_days)
        values = [sample[1] for sample in history]
        # `baseline is not None` (not a truthy check): a device with a real,
        # all-zero history has baseline == 0.0, which is itself meaningful -
        # any blocked traffic at all on such a device is a spike from its own
        # established normal. `baseline` alone is falsy for 0.0 and would
        # silently exempt exactly the devices most worth watching.
        baseline = sum(values) / len(values) if values else None

        # None (not 0) when there's no valid per-run increment yet from any
        # source - first time seen, or every reporting source just reset
        # (see aggregate_source_deltas()). blocked_count is only a display
        # fallback for that case; is_anomaly is gated on the real delta,
        # not on this substitute.
        if stats_complete:
            raw_by_source = {
                label: mac_counts[key]
                for label, mac_counts in blocked_by_mac_by_source.items()
                if key in mac_counts
            }
            delta, updated_last_raw_by_source = aggregate_source_deltas(last_raw_by_source, raw_by_source)
        else:
            delta = None
        blocked_count = delta if delta is not None else 0
        is_anomaly = bool(stats_complete and baseline is not None and delta is not None and blocked_count >= min_blocked and blocked_count > baseline * multiplier)

        owner = owners_by_mac.get(mac, '') if mac else ''
        if stats_complete and delta is None:
            detail = "blocked=unknown (establishing baseline - first run seen, or Pi-hole/FTL restarted)"
        else:
            detail = f"blocked={blocked_count}"
            if baseline is not None:
                detail += f", avg={round(baseline, 1)}"
                if baseline > 0:
                    detail += f", ratio={round(blocked_count / baseline, 2)}x"
        if owner:
            detail += f" - owner: {owner}"

        if device:
            if not is_mac(device['mac']):
                mylog('verbose', [f"[{pluginName}] Skipping invalid MAC (see Generate fake MAC setting): {device}"])
                continue
            plugin_objects.add_object(
                primaryId=str(device['mac']),
                secondaryId=str(device['ip']),
                watched1=str(device['name']),
                watched2=str(device['macVendor']),
                watched3=str(blocked_count),
                watched4='anomaly' if is_anomaly else 'normal',
                extra=detail,
                foreignKey=str(device['mac']),
            )
        elif mac:
            # No device-import row this run for `key`, but it's still a MAC:
            # either a real, known device that's just offline-filtered above
            # (link the anomaly to its existing page via foreignKey), or the
            # FAKE_MAC stand-in for an IP Pi-hole never associated with a MAC.
            plugin_objects.add_object(
                primaryId=key,
                secondaryId=key,
                watched1='',
                watched2='',
                watched3=str(blocked_count),
                watched4='anomaly' if is_anomaly else 'normal',
                extra=detail,
                foreignKey=key,
            )
        else:
            # A bare IP with FAKE_MAC off. Results map primaryId to
            # CurrentScan.scanMac, so writing it out would create a bogus
            # device whose "MAC" is the IP. Keep tracking its history so an
            # anomaly still gets logged below, but don't emit a row.
            mylog('verbose', [f"[{pluginName}] No MAC for {key} (see Generate fake MAC setting) - not writing a result row"])

        if is_anomaly:
            mylog('none', [f'[{pluginName}] Anomaly: {key} - {detail}'])

        if stats_complete:
            # Always reset each source's diff reference point, even on a
            # bootstrap or reset run (delta is None) - that's exactly what
            # makes the *next* run's delta valid again instead of repeating
            # the same "no valid delta" state indefinitely. Only append to
            # the baseline history when this run actually produced a real
            # (aggregate) delta.
            if delta is not None:
                history.append([now_ts, delta])
            state[key] = {"last_raw": updated_last_raw_by_source, "history": history}

    save_state(state)
    plugin_objects.write_result_file()
    mylog(
        'verbose',
        [f'[{pluginName}] Script finished. {len(devices_by_mac)} device(s) imported, '
         f'{len(blocked_keys)} with blocked-query data, from {len(configured_sources)} source(s).'],
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
