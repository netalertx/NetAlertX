#!/usr/bin/env python
# adguard_export/script.py
#
# NetAlertX plugin: adguard_export
# Syncs known devices from the NetAlertX database to AdGuard Home as
# persistent clients, keeping names, MACs, and IP addresses in sync.
#
# AdGuard Home API reference:
#   GET  /control/clients          – list all persistent clients
#   POST /control/clients/add      – create a new persistent client
#   POST /control/clients/update   – update an existing persistent client
#   POST /control/clients/delete   – remove a persistent client

import os
import sys
import json
import requests
from pytz import timezone
from typing import Dict, List, Optional, Set, Tuple

# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from const import dataPath, logPath  # noqa: E402, E261
from plugin_helper import Plugin_Objects  # noqa: E402, E261
from logger import mylog, Logger  # noqa: E402, E261
from helper import get_setting_value  # noqa: E402, E261
from models.device_instance import DeviceInstance  # noqa: E402, E261
import conf  # noqa: E402, E261

# ----------------------------
# Plugin metadata
# ----------------------------
pluginName = "ADGUARDEXP"

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value("TIMEZONE"))

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

# Define paths
LOG_PATH = logPath + "/plugins"
RESULT_FILE = os.path.join(LOG_PATH, f"last_result.{pluginName}.log")
STATE_FILE = os.path.join(dataPath, f"state.{pluginName}.json")

plugin_objects = Plugin_Objects(RESULT_FILE)


def load_managed_names() -> Set[str]:
    """Return the set of AdGuard client names we previously added."""
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f).get("managed", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_managed_names(names: Set[str]) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump({"managed": sorted(names)}, f, indent=2)


# ---------------------------------------------------------------------------
# Device type → AdGuard tag mapping
# ---------------------------------------------------------------------------
_TYPE_TAG_MAP: Dict[str, str] = {
    "ap":                 "device_other",
    "desktop":            "device_pc",
    "game console":       "device_gameconsole",
    "gameconsole":        "device_gameconsole",
    "gateway":            "device_other",
    "house appliance":    "device_other",
    "hypervisor":         "device_pc",
    "ip camera":          "device_camera",
    "camera":             "device_camera",
    "laptop":             "device_laptop",
    "notebook":           "device_laptop",
    "nas":                "device_nas",
    "printer":            "device_printer",
    "router":             "device_other",
    "server":             "device_pc",
    "smarttv":            "device_tv",
    "smart tv":           "device_tv",
    "tv":                 "device_tv",
    "smartphone":         "device_phone",
    "phone":              "device_phone",
    "mobile":             "device_phone",
    "smartwatch":         "device_phone",
    "watch":              "device_phone",
    "tablet":             "device_tablet",
    "virtual assistance": "device_audio",
    "assistant":          "device_audio",
    "speaker":            "device_audio",
}


def device_type_to_tag(dev_type: str) -> str:
    """Map a NetAlertX devType string to a valid AdGuard Home tag, or ''."""
    if not dev_type:
        return ""
    key = dev_type.strip().lower()
    if key in _TYPE_TAG_MAP:
        return _TYPE_TAG_MAP[key]
    # Substring fallback for partial matches
    for pattern, tag in _TYPE_TAG_MAP.items():
        if pattern in key:
            return tag
    return ""


# ---------------------------------------------------------------------------
# AdGuard Home client
# ---------------------------------------------------------------------------
class AdGuardClient:
    """Thin wrapper around the AdGuard Home /control/clients* API."""

    def __init__(self, base_url: str, username: str, password: str, verify_ssl: bool = True):
        self.base_url   = base_url.rstrip("/")
        self.auth       = (username, password)
        self.verify_ssl = verify_ssl
        self.session    = requests.Session()
        self.session.auth = self.auth

    def _url(self, path: str) -> str:
        return f"{self.base_url}/control/{path.lstrip('/')}"

    def get_clients(self) -> List[dict]:
        """Return the list of persistent (manually added) clients."""
        resp = self.session.get(self._url("clients"), verify=self.verify_ssl, timeout=15)
        resp.raise_for_status()
        return resp.json().get("clients") or []

    def add_client(self, client: dict) -> None:
        resp = self.session.post(
            self._url("clients/add"),
            json=client,
            verify=self.verify_ssl,
            timeout=15,
        )
        resp.raise_for_status()

    def update_client(self, old_name: str, client: dict) -> None:
        payload = {"name": old_name, "data": client}
        resp = self.session.post(
            self._url("clients/update"),
            json=payload,
            verify=self.verify_ssl,
            timeout=15,
        )
        resp.raise_for_status()

    def delete_client(self, name: str) -> None:
        resp = self.session.post(
            self._url("clients/delete"),
            json={"name": name},
            verify=self.verify_ssl,
            timeout=15,
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_netalertx_devices(include_offline: bool, include_new: bool) -> List[dict]:
    """
    Return filtered devices from NetAlertX using the DeviceInstance model.
    Fields returned per device: mac, name, last_ip, dev_type
    """
    devices = []
    try:
        for d in DeviceInstance().getAll():
            if d.get("devIsArchived", 0):
                continue
            if not include_offline and not d.get("devPresentLastScan", 1):
                continue
            if not include_new and d.get("devIsNew", 0):
                continue

            mac      = (d.get("devMac",    "") or "").strip()
            last_ip  = (d.get("devLastIP", "") or "").strip()
            name     = (d.get("devName",   "") or "").strip()
            dev_type = (d.get("devType",   "") or "").strip()

            if not mac and not last_ip:
                continue
            if not name:
                name = mac or last_ip

            devices.append({"mac": mac, "name": name, "last_ip": last_ip, "dev_type": dev_type})

    except Exception as exc:
        mylog("verbose", [f"[{pluginName}] ERROR reading devices: {exc}"])

    return devices


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------
def build_agrd_client(device: dict, use_mac: bool) -> dict:
    """
    Build an AdGuard Home client object from a NetAlertX device row.

    AdGuard Home identifies a client by its 'ids' list, which may contain
    MACs, IPs, CIDRs, or ClientIDs.  We prefer MAC when available; fall
    back to IP otherwise.
    """
    ids = []
    if use_mac and device["mac"] and device["mac"] not in ("", "00:00:00:00:00:00"):
        ids.append(device["mac"].lower())
    if device["last_ip"] and device["last_ip"] not in ("", "0.0.0.0"):
        ids.append(device["last_ip"])

    if not ids:
        return {}   # nothing useful to identify the device

    tag = device_type_to_tag(device.get("dev_type", ""))
    return {
        "name": device["name"],
        "ids":  ids,
        "tags": [tag] if tag else [],
        "use_global_settings":         True,
        "use_global_blocked_services": True,
        "filtering_enabled":           False,
        "parental_enabled":            False,
        "safebrowsing_enabled":        False,
        "safesearch_enabled":          False,
        "blocked_services":            [],
        "upstreams":                   [],
    }


def sync_to_adguard(
    agrd: AdGuardClient,
    devices: List[dict],
    use_mac: bool,
    delete_missing: bool,
    existing_clients: Optional[List[dict]] = None,
) -> Tuple[int, int, int, int]:
    """
    Core sync routine.  Returns (added, updated, skipped, deleted).
    Pass existing_clients to reuse a list already fetched (avoids a second
    round-trip when the caller performed a connectivity check first).
    """
    if existing_clients is None:
        existing_clients = agrd.get_clients()
    mylog("verbose", [f"[{pluginName}] AdGuard Home currently has {len(existing_clients)} persistent client(s)."])

    # Build a lookup: identifier → client dict
    existing_by_id: Dict[str, dict] = {}
    for client in existing_clients:
        for cid in client.get("ids", []):
            existing_by_id[cid.lower()] = client

    # Also index by name for update / delete operations (warn if AdGuard has duplicate names)
    existing_by_name: Dict[str, dict] = {}
    for c in existing_clients:
        if c["name"] in existing_by_name:
            mylog("verbose", [f"[{pluginName}] WARNING duplicate client name in AdGuard Home: {c['name']!r}"])
        existing_by_name[c["name"]] = c

    # Load the set of client names we've previously added so that DELETE mode
    # only removes clients we created, not manually-added ones.
    managed_names = load_managed_names()

    added = updated = skipped = deleted = 0

    # ----- add / update -----
    for device in devices:
        client_data = build_agrd_client(device, use_mac)
        if not client_data:
            if not use_mac and not device["last_ip"]:
                reason = "no IP address (USEMAC is disabled, IP required)"
            else:
                reason = "no usable MAC or IP"
            mylog("verbose", [f"[{pluginName}]   SKIP  {device['name']!r} – {reason}"])
            skipped += 1
            continue

        # Check whether any of the ids already exist in AdGuard
        existing = None
        for cid in client_data["ids"]:
            if cid.lower() in existing_by_id:
                existing = existing_by_id[cid.lower()]
                break

        if existing is None and device["name"] in managed_names:
            # Fall back to name match only for clients we previously added — avoids
            # accidentally matching a manually-created AdGuard client with the same name.
            existing = existing_by_name.get(device["name"])
            if existing:
                mylog("verbose", [f"[{pluginName}]   WARN matched {device['name']!r} by name (no ID match) — verify no duplicate clients"])

        if existing:
            old_name = existing["name"]
            # Preserve existing per-client AdGuard settings; we only manage name, ids, tags.
            _our_keys = frozenset(("name", "ids", "tags"))
            merged_data = {**client_data, **{k: v for k, v in existing.items() if k not in _our_keys}}
            # Only call update when something actually changed to avoid noise
            if (
                sorted(i.lower() for i in existing.get("ids", [])) != sorted(i.lower() for i in client_data["ids"])
                or existing.get("name") != client_data["name"]
                or sorted(existing.get("tags", [])) != sorted(client_data["tags"])
            ):
                try:
                    agrd.update_client(old_name, merged_data)
                    mylog("verbose", [f"[{pluginName}]   UPDATE  {old_name!r} → {device['name']!r}  ids={client_data['ids']}"])
                    # Only track the rename for clients we already own — never adopt a manually-created client.
                    if old_name in managed_names:
                        managed_names.discard(old_name)
                        managed_names.add(device["name"])
                    updated += 1
                except requests.HTTPError as exc:
                    mylog("verbose", [f"[{pluginName}]   ERROR updating {device['name']!r}: {exc}"])
                    skipped += 1
            else:
                mylog("verbose", [f"[{pluginName}]   SKIP (no change)  {device['name']!r}"])
                # No managed_names update: if we created this client it's already in the state
                # file; if it's a manually-created client we must not claim ownership of it.
                skipped += 1
        else:
            try:
                agrd.add_client(client_data)
                mylog("verbose", [f"[{pluginName}]   ADD  {device['name']!r}  ids={client_data['ids']}"])
                managed_names.add(device["name"])
                added += 1
            except requests.HTTPError as exc:
                mylog("verbose", [f"[{pluginName}]   ERROR adding {device['name']!r}: {exc}"])
                skipped += 1

    # ----- optional delete of AdGuard clients no longer in NetAlertX -----
    if delete_missing:
        export_names = {d["name"] for d in devices}
        for client in existing_clients:
            cname = client.get("name", "")
            # Only delete clients that we previously added (tracked in state file)
            # so we don't accidentally remove manually-added clients.
            if cname in managed_names and cname not in export_names:
                try:
                    agrd.delete_client(cname)
                    mylog("verbose", [f"[{pluginName}]   DELETE  {cname!r} (no longer in NetAlertX)"])
                    managed_names.discard(cname)
                    deleted += 1
                except requests.HTTPError as exc:
                    mylog("verbose", [f"[{pluginName}]   ERROR deleting {cname!r}: {exc}"])

    save_managed_names(managed_names)
    return added, updated, skipped, deleted


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    mylog("verbose", [f"[{pluginName}] In script"])

    # ------------------------------------------------------------------
    # Read settings
    # ------------------------------------------------------------------
    agrd_url        = get_setting_value("ADGUARDEXP_URL")       or "http://localhost:3000"
    agrd_user       = get_setting_value("ADGUARDEXP_USER")      or ""
    agrd_pass       = get_setting_value("ADGUARDEXP_PASSWORD")  or ""
    verify_ssl_str      = get_setting_value("ADGUARDEXP_VERIFYSSL")       or "true"
    include_offline_str = get_setting_value("ADGUARDEXP_INCLUDE_OFFLINE") or "true"
    include_new_str     = get_setting_value("ADGUARDEXP_INCLUDE_NEW")     or "false"
    use_mac_str         = get_setting_value("ADGUARDEXP_USEMAC")          or "true"
    delete_str          = get_setting_value("ADGUARDEXP_DELETE")          or "false"

    verify_ssl      = verify_ssl_str.strip().lower()      not in ("false", "0", "no")
    include_offline = include_offline_str.strip().lower() not in ("false", "0", "no")
    include_new     = include_new_str.strip().lower()     not in ("false", "0", "no")
    use_mac         = use_mac_str.strip().lower()         not in ("false", "0", "no")
    delete_miss     = delete_str.strip().lower()          not in ("false", "0", "no")

    mylog("verbose", [f"[{pluginName}] " + ("=" * 60)])
    mylog("verbose", [f"[{pluginName}] AdGuard Home URL    : {agrd_url}"])
    mylog("verbose", [f"[{pluginName}] Include offline devs: {include_offline}"])
    mylog("verbose", [f"[{pluginName}] Include new/unknown : {include_new}"])
    mylog("verbose", [f"[{pluginName}] Use MAC as id       : {use_mac}"])
    mylog("verbose", [f"[{pluginName}] Delete missing      : {delete_miss}"])
    mylog("verbose", [f"[{pluginName}] " + ("=" * 60)])

    # ------------------------------------------------------------------
    # Load devices from NetAlertX
    # ------------------------------------------------------------------
    devices = get_netalertx_devices(include_offline, include_new)
    mylog("verbose", [f"[{pluginName}] Loaded {len(devices)} device(s) from NetAlertX database."])

    if not devices:
        mylog("verbose", ["No devices to sync – exiting."])
        plugin_objects.add_object(
            primaryId   = "adguard_export",
            secondaryId = "summary",
            watched1    = "0",
            watched2    = "0",
            watched3    = "0",
            watched4    = "0",
            extra       = "No devices found in NetAlertX",
        )
        plugin_objects.write_result_file()
        return

    # ------------------------------------------------------------------
    # Connect to AdGuard Home and sync
    # ------------------------------------------------------------------
    try:
        agrd = AdGuardClient(agrd_url, agrd_user, agrd_pass, verify_ssl)
        existing_clients = agrd.get_clients()
    except requests.exceptions.ConnectionError as exc:
        mylog("verbose", [f"[{pluginName}] ERROR – cannot connect to AdGuard Home at {agrd_url}: {exc}"])
        plugin_objects.add_object(
            primaryId   = "adguard_export",
            secondaryId = "error",
            extra       = f"Connection failed: {exc}",
        )
        plugin_objects.write_result_file()
        return
    except requests.HTTPError as exc:
        mylog("verbose", [f"[{pluginName}] ERROR – AdGuard Home returned an HTTP error: {exc}"])
        plugin_objects.add_object(
            primaryId   = "adguard_export",
            secondaryId = "error",
            extra       = f"HTTP error: {exc}",
        )
        plugin_objects.write_result_file()
        return
    except Exception as exc:
        mylog("verbose", [f"[{pluginName}] ERROR – AdGuard Home returned an unknown error: {exc}"])
        plugin_objects.add_object(
            primaryId   = "adguard_export",
            secondaryId = "error",
            extra       = f"Unknown error: {exc}",
        )
        plugin_objects.write_result_file()
        return

    added, updated, skipped, deleted = sync_to_adguard(
        agrd, devices, use_mac, delete_miss, existing_clients=existing_clients
    )

    summary = (
        f"Sync complete – added={added} updated={updated} "
        f"skipped={skipped} deleted={deleted}"
    )

    # ------------------------------------------------------------------
    # Write plugin result (one summary row + one row per touched device)
    # ------------------------------------------------------------------
    plugin_objects.add_object(
        primaryId   = "adguard_export",
        secondaryId = "summary",
        watched1    = str(added),
        watched2    = str(updated),
        watched3    = str(skipped),
        watched4    = str(deleted),
        extra       = summary,
    )

    for device in devices:
        plugin_objects.add_object(
            primaryId   = device["mac"] or device["last_ip"],
            secondaryId = device["last_ip"],
            watched1    = device["name"],
            watched2    = device["mac"],
            watched3    = device["last_ip"],
            watched4    = agrd_url,
            extra       = "exported",
            foreignKey  = device["mac"] or "",
        )

    mylog("verbose", [f"[{pluginName}] {summary}"])
    plugin_objects.write_result_file()
    return


if __name__ == "__main__":
    main()
