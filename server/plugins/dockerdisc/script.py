#!/usr/bin/env python
"""NetAlertX plugin: DOCKERDISC - Docker discovery

For each configured Docker host, lists that host's containers under the
*host's own* Device Details -> Plugins -> DOCKERDISC tab. The host itself
is never created by this plugin - it must already exist in NetAlertX
(found the normal way, via ARP/Nmap).

  - objectPrimaryId / foreignKey is always the Docker HOST's MAC - never a
    container's own MAC. Every plugin object (one per container) attaches
    to the host device.
  - Because matching targets the host (persistent LAN identity), not the
    container, EVERY container is listed - bridge/overlay ones included -
    not only macvlan/ipvlan ones. A container only gets its own MAC/IP
    shown (watched4/extra) when it has a macvlan/ipvlan network; otherwise
    those fields are "null".
  - Also maps to CurrentScan (scanMac/scanCreatesDevice/scanParentMAC/
    scanLastIP - see docs/PLUGINS_IMPORT_BEHAVIOR.md), gated by
    DOCKERDISC_IMPORT_ON (whether this run promotes to CurrentScan at all)
    and, independently, DOCKERDISC_CREATE_DEV (whether a container with
    its own MAC may originate a brand-new device via scanCreatesDevice -
    neither setting gates the other). A container without its own MAC
    (bridge/overlay/etc.) always gets a blank scanMac, which blocks device
    creation for the whole group regardless of scanCreatesDevice - it can
    never be its own device. One with a real MAC is parented to its host
    via scanParentMAC on every promoted run, whether or not CREATE_DEV
    lets it also originate a device.
  - One `hosts` entry = one Docker host: a read-only Docker Socket Proxy
    URL, plus a manual MAC fallback for when auto-detection (via the
    proxy's own /info endpoint) doesn't resolve to a known device. Never
    connects to /var/run/docker.sock directly.

`GET /containers/json`'s `NetworkSettings.Networks.<name>` does NOT carry
a `Driver` field inline (only NetworkID/Gateway/IPAddress/MacAddress/...) -
the driver has to come from a separate `GET /networks` call, filtered by
the unique NetworkIDs seen across a host's containers in one batched
request. This needs the Socket Proxy's NETWORKS=1 permission in addition
to CONTAINERS=1/INFO=1.

Structural references: server/plugins/internet_speedtest/config.json
(plugin_type "other", no mapped_to_column - this never writes into
Devices/CurrentScan) and server/plugins/vendor_update/script.py
("resolve for a device that must already exist, skip - never create -
otherwise" logic, applied here to the host instead of the container).
"""

import json
import os
import sys
import time
from urllib.parse import urlencode

import requests

INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import (  # noqa: E402
    Plugin_Objects,
    handleEmpty,
    normalize_mac,
    decode_settings_base64,
)
from logger import mylog, Logger  # noqa: E402
from helper import get_setting_value  # noqa: E402
from const import logPath  # noqa: E402
from models.device_instance import DeviceInstance  # noqa: E402
import conf  # noqa: E402
from pytz import timezone  # noqa: E402

conf.tz = timezone(get_setting_value('TIMEZONE'))
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'DOCKERDISC'

LOG_PATH = logPath + '/plugins'
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

REQUEST_TIMEOUT_DEFAULT = 30

# Docker network drivers with their own real LAN-visible MAC/IP - the only
# ones that can populate watched4/extra (container_mac/container_ip). Every
# other driver (bridge, overlay, host, none, ...) still gets its container
# listed, just without those two fields.
LAN_VISIBLE_DRIVERS = ('macvlan', 'ipvlan')


class DockerHost:
    """One configured `hosts` entry: a Docker Socket Proxy endpoint plus
    the manual host-MAC fallback for it. Does not connect on construction -
    call get_info()/get_containers() to actually talk to the proxy. Never
    raises - a failed host is logged and skipped, not fatal to the run.

    `deadline` is a shared `time.monotonic()` timestamp for the *whole*
    run (every host, every request) - not a per-request timeout. Each
    request gets whatever's left of that budget, capped at
    REQUEST_TIMEOUT_DEFAULT, so one slow/hanging call can't burn the
    entire RUN_TIMEOUT kill-timeout by itself and starve every other host
    still queued behind it (server/plugin.py enforces RUN_TIMEOUT as the
    whole subprocess's hard timeout, not a safe per-call one)."""

    def __init__(self, proxy_url, manual_mac, deadline):
        self.proxy_url = (proxy_url or '').rstrip('/')
        self.manual_mac = normalize_mac(manual_mac) if manual_mac else None
        self.deadline = deadline

    @property
    def configured(self):
        return bool(self.proxy_url)

    def _get(self, path, expected_type=None):
        """GET against this host's Socket Proxy. Returns the parsed JSON
        body, or None (logging why) on any failure - including the run's
        timeout budget already being exhausted, or a response whose shape
        doesn't match `expected_type` (a malformed/unexpected payload,
        e.g. from a misconfigured or incompatible Socket Proxy - a plain
        `dict`/`list` mismatch here would otherwise surface as a much
        less obvious AttributeError/TypeError further down in a caller)."""
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            mylog('none', [f'[{pluginName}] {self.proxy_url}: run timeout budget exhausted before requesting {path} - skipping.'])
            return None

        try:
            resp = requests.get(
                self.proxy_url + path,
                timeout=min(remaining, REQUEST_TIMEOUT_DEFAULT),
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            mylog('none', [f'[{pluginName}] {self.proxy_url}: request to {path} timed out. Try increasing the run timeout.'])
            return None
        except requests.exceptions.ConnectionError:
            mylog('none', [f'[{pluginName}] {self.proxy_url}: connection error on {path}. Check the Socket Proxy URL and that it is reachable.'])
            return None
        except Exception as e:
            mylog('none', [f'[{pluginName}] {self.proxy_url}: unexpected error on {path}: {e}'])
            return None

        if expected_type is not None and not isinstance(data, expected_type):
            mylog('none', [
                f'[{pluginName}] {self.proxy_url}: unexpected response shape from {path} '
                f'(expected {expected_type.__name__}, got {type(data).__name__}) - '
                'check the Socket Proxy version/URL.'
            ])
            return None

        return data

    def get_info(self):
        """Docker Engine API /info - used only for host-MAC auto-detection
        (the daemon's `Name`, i.e. hostname). Requires the Socket Proxy's
        INFO=1 permission; returns None if that's not granted or /info
        otherwise fails, in which case callers fall back to manual_mac."""
        return self._get('/info', expected_type=dict)

    def get_containers(self):
        """Docker Engine API /containers/json (running containers only,
        matching the default `all=false`) - includes NetworkSettings and
        Labels, which is all this plugin needs. Requires CONTAINERS=1."""
        return self._get('/containers/json', expected_type=list) or []

    def get_network_drivers(self, network_ids):
        """{NetworkID: Driver} for the given network IDs, in one batched
        `GET /networks?filters=...` call - NetworkSettings.Networks on a
        container does NOT carry Driver inline (confirmed against a real
        Socket Proxy 2026-09-08), so this is the only way to get it.
        Requires NETWORKS=1. Returns {} (not per-container failure) if the
        call fails - callers fall back to an empty/unknown driver rather
        than aborting the whole host."""
        network_ids = sorted(set(network_ids))
        if not network_ids:
            return {}

        query = urlencode({'filters': json.dumps({'id': network_ids})})
        networks = self._get(f'/networks?{query}', expected_type=list)
        if networks is None:
            mylog('verbose', [f'[{pluginName}] {self.proxy_url}: could not read /networks (needs the Socket Proxy NETWORKS=1 permission) - network driver will show as empty.'])
            return {}

        return {n['Id']: n.get('Driver') for n in networks if isinstance(n, dict) and 'Id' in n}


def resolve_host_mac(host):
    """Manually configured DOCKERDISC_HOST_MAC wins immediately, with no
    Socket Proxy call at all - a MAC address is stable and doesn't need
    runtime "confirmation" via hostname matching, so there's nothing to
    gain from spending an /info request on it every single scheduled run.
    Otherwise auto-detects via Socket Proxy /info -> Devices.devName
    match. Returns a normalized MAC string, or None if neither resolves
    to anything."""

    if host.manual_mac:
        return host.manual_mac

    info = host.get_info()
    hostname = (info or {}).get('Name')

    if hostname:
        rows = DeviceInstance().getAllByName(hostname.lstrip('/'))

        if len(rows) == 1:
            mylog('verbose', [f'[{pluginName}] {host.proxy_url}: auto-detected host MAC via hostname "{hostname}".'])
            return normalize_mac(rows[0]['devMac'])

        if len(rows) > 1:
            # devName isn't unique across Devices - guessing which one is
            # this host would risk attaching every container to the wrong
            # device. Ambiguous, same as "no match": fall back to manual.
            mylog(
                'verbose',
                [f'[{pluginName}] {host.proxy_url}: /info hostname "{hostname}" matches {len(rows)} devices, '
                 'ambiguous - falling back to the manually configured host MAC, if any.'],
            )
        else:
            mylog(
                'verbose',
                [f'[{pluginName}] {host.proxy_url}: /info hostname "{hostname}" has no matching Devices.devName - '
                 'falling back to the manually configured host MAC, if any.'],
            )
    else:
        mylog(
            'verbose',
            [f'[{pluginName}] {host.proxy_url}: could not read hostname via /info (needs the Socket Proxy '
             'INFO=1 permission) - falling back to the manually configured host MAC, if any.'],
        )

    return host.manual_mac


def lookup_device_mac(mac):
    """True if `mac` already exists as a Devices row - this plugin never
    creates the host device, same rule vendor_update applies to the
    devices it enriches. Delegates the actual matching (case sensitivity
    included) to DeviceInstance.getByMac() - the core's own contract for
    what "the same MAC" means, not something this plugin second-guesses."""
    return DeviceInstance().getByMac(mac) is not None


def pick_lan_network(networks, driver_by_id):
    """Given a container's NetworkSettings.Networks dict and a
    {NetworkID: Driver} lookup (from DockerHost.get_network_drivers - the
    per-network Driver isn't inline on `networks`, see module docstring),
    return the (name, driver, network) for its macvlan/ipvlan network if it
    has one, else None.

    If a container somehow has more than one macvlan/ipvlan network at
    once, the one with the alphabetically first network *name* wins - a
    deliberate, deterministic tie-break (spec §9), not "whatever order the
    Socket Proxy's JSON happened to list them in" (dict iteration order,
    which isn't a documented/guaranteed ordering from the Docker API and
    could in principle vary between runs)."""
    lan_networks = sorted(
        ((name, network) for name, network in (networks or {}).items()
         if driver_by_id.get(network.get('NetworkID')) in LAN_VISIBLE_DRIVERS),
        key=lambda item: item[0],
    )
    if not lan_networks:
        return None
    name, network = lan_networks[0]
    return name, driver_by_id[network['NetworkID']], network


def first_network_driver(networks, driver_by_id):
    """Best-effort driver name to show when the container has no
    macvlan/ipvlan network - whatever its first network reports."""
    for network in (networks or {}).values():
        driver = driver_by_id.get(network.get('NetworkID'))
        if driver:
            return driver
    return None


def process_host(host_entry, deadline, plugin_objects, create_dev):
    """Lists one Docker host's containers as plugin objects under that
    host's Device Details tab, and maps each to a CurrentScan row. Skips
    the whole host (no containers listed) if its Socket Proxy URL is
    missing, its MAC can't be resolved, or that MAC isn't a known device.
    Returns the number of containers reported."""

    host = DockerHost(
        proxy_url=host_entry.get('DOCKERDISC_SOCKET_PROXY_URL'),
        manual_mac=host_entry.get('DOCKERDISC_HOST_MAC'),
        deadline=deadline,
    )

    if not host.configured:
        mylog('none', [f'[{pluginName}] Skipping a configured host entry with no Socket Proxy URL.'])
        return 0

    host_mac = resolve_host_mac(host)
    if not host_mac:
        mylog('none', [f'[{pluginName}] {host.proxy_url}: no host MAC (auto-detect failed and no manual fallback set) - skipping.'])
        return 0

    if not lookup_device_mac(host_mac):
        mylog('none', [f'[{pluginName}] {host.proxy_url}: host MAC {host_mac} is not a known device (never created by this plugin) - skipping.'])
        return 0

    containers = host.get_containers()
    mylog('verbose', [f'[{pluginName}] {host.proxy_url} ({host_mac}): {len(containers)} container(s) found.'])

    # One batched /networks call for every unique NetworkID referenced by
    # this host's containers, instead of one call per container/network.
    network_ids = (
        network.get('NetworkID')
        for container in containers
        for network in ((container.get('NetworkSettings') or {}).get('Networks') or {}).values()
    )
    driver_by_id = host.get_network_drivers(n for n in network_ids if n)

    added = 0
    for container in containers:
        networks = (container.get('NetworkSettings') or {}).get('Networks') or {}
        lan_net = pick_lan_network(networks, driver_by_id)

        if lan_net:
            _, network_driver, network = lan_net
            container_mac = network.get('MacAddress') or ''
            container_ip = network.get('IPAddress') or ''
        else:
            network_driver = first_network_driver(networks, driver_by_id) or ''
            container_mac = ''
            container_ip = ''

        labels = container.get('Labels') or {}
        compose_project = labels.get('com.docker.compose.project')
        compose_service = labels.get('com.docker.compose.service')
        compose = ' / '.join(p for p in (compose_project, compose_service) if p) or None

        names = container.get('Names') or []
        container_name = names[0].lstrip('/') if names else container.get('Id', '')[:12]

        # scanMac/scanCreatesDevice (helpVal1/helpVal2, mapped in config.json)
        # drive whether this row can promote to its own CurrentScan/Devices
        # entry - see docs/PLUGINS_IMPORT_BEHAVIOR.md. A container without
        # its own LAN-visible MAC (bridge/overlay/etc.) always gets a blank
        # scanMac, which blocks device creation for the whole group
        # regardless of scanCreatesDevice - it can never be its own device.
        # One with a real MAC only creates/confirms a device when the user
        # opted in via DOCKERDISC_CREATE_DEV.
        can_create_device = bool(container_mac) and create_dev

        plugin_objects.add_object(
            primaryId=host_mac,
            secondaryId=handleEmpty(container_name),
            watched1=handleEmpty(container.get('Image')),
            watched2=handleEmpty(compose),
            watched3=handleEmpty(network_driver),
            watched4=handleEmpty(container_mac),
            extra=handleEmpty(container_ip),
            foreignKey=host_mac,
            helpVal1=container_mac,
            helpVal2='1' if can_create_device else '0',
        )
        added += 1

    return added


def main():
    """Entry point: reads the configured Docker hosts and DOCKERDISC_CREATE_DEV,
    processes each host in turn against a shared per-run request-time
    budget, and writes the combined result file."""

    mylog('verbose', [f'[{pluginName}] In script'])

    host_configs = get_setting_value('DOCKERDISC_hosts') or []
    create_dev = bool(get_setting_value('DOCKERDISC_CREATE_DEV'))
    run_timeout = get_setting_value('DOCKERDISC_RUN_TIMEOUT') or REQUEST_TIMEOUT_DEFAULT
    # One shared deadline for the whole run (every host, every request) -
    # config.json's "hosts" param has timeoutMultiplier set, so the outer
    # kill-timeout (server/plugin.py) already scales with host count; this
    # mirrors that budget inside the script itself, so one slow host can't
    # eat every other host's share of it. See DockerHost._get().
    deadline = time.monotonic() + run_timeout

    mylog('verbose', [f'[{pluginName}] number of configured hosts: {len(host_configs)}'])

    plugin_objects = Plugin_Objects(RESULT_FILE)

    total_added = 0
    for host_config in host_configs:
        host_entry = decode_settings_base64(host_config)
        total_added += process_host(host_entry, deadline, plugin_objects, create_dev)

    plugin_objects.write_result_file()

    mylog('verbose', [f'[{pluginName}] Update complete - {total_added} container(s) reported across {len(host_configs)} host(s).'])

    return 0


if __name__ == '__main__':
    main()
