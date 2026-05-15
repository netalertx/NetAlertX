#!/usr/bin/env python

import os
import sys
import requests
from pytz import timezone

# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from const import logPath  # noqa: E402, E261
from plugin_helper import Plugin_Objects  # noqa: E402, E261
from utils.crypto_utils import string_to_fake_mac  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402, E261
from helper import get_setting_value  # noqa: E402, E261
import conf  # noqa: E402, E261

# ----------------------------
# Plugin metadata
# ----------------------------
pluginName = "ADGUARDIMP"

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value("TIMEZONE"))

# Make sure log level is initialized correctly
Logger(get_setting_value("LOG_LEVEL"))

# Define paths
LOG_PATH = logPath + "/plugins"
LOG_FILE = os.path.join(LOG_PATH, f"script.{pluginName}.log")
RESULT_FILE = os.path.join(LOG_PATH, f"last_result.{pluginName}.log")

plugin_objects = Plugin_Objects(RESULT_FILE)


# ----------------------------
# Helpers
# ----------------------------
def ag_request(path, server, port, protocol, auth, timeout):
    """Unified request handler"""
    url = f"{protocol}://{server}:{port}{path}"

    try:
r = requests.get(url, auth=auth, timeout=timeout, verify=True)
        if r.status_code != 200:
            mylog("none", [f"[{pluginName}] Failed request {url} -> {r.status_code}"])
            return None
        return r.json()
    except Exception as e:
        mylog("none", [f"[{pluginName}] Exception accessing {url}: {e}"])
        return None


# ----------------------------
# MAIN
# ----------------------------
def main():
    mylog("verbose", [f"[{pluginName}] In script"])

    # Retrieve plugin settings
    server = get_setting_value("ADGUARDIMP_SERVER")
    port = get_setting_value("ADGUARDIMP_PORT")
    protocol = get_setting_value("ADGUARDIMP_PROTOCOL") or "http"
    user = get_setting_value("ADGUARDIMP_USER")
    pw = get_setting_value("ADGUARDIMP_PASS")
    fake_mac_enabled = get_setting_value("ADGUARDIMP_FAKE_MAC")
    timeout = int(get_setting_value("ADGUARDIMP_RUN_TIMEOUT") or 5)

    auth = (user, pw) if user or pw else None

    # -------------------------------------------
    # Fetch clients from AdGuard Home
    # -------------------------------------------
    clients_json = ag_request(
        "/control/clients",
        server, port, protocol, auth, timeout
    )

    if not clients_json:
        mylog("none", [f"[{pluginName}] No clients returned"])
        plugin_objects.write_result_file()
        return 1

    raw_clients = clients_json.get("auto_clients", []) or []

    # -------------------------------------------
    # Fetch DHCP leases if DHCP enabled
    # -------------------------------------------
    dhcp_json = ag_request(
        "/control/dhcp/status",
        server, port, protocol, auth, timeout
    )

    dhcp_leases = []
    if dhcp_json and dhcp_json.get("enabled"):
        dhcp_leases = dhcp_json.get("leases", [])

    # Build MAC lookup table for DHCP
    dhcp_mac_map = {}
    for lease in dhcp_leases:
        ip = lease.get("ip")
        mac = lease.get("mac")
        if ip and mac:
            dhcp_mac_map[ip] = mac.upper()

    # -------------------------------------------
    # Process devices
    # -------------------------------------------
    device_data = []

    for cl in raw_clients:
        ip = cl.get("ip")
        hostname = cl.get("name") or ""
        dsource = cl.get("source") or ""

        # Determine MAC
        mac = dhcp_mac_map.get(ip)

        if not mac and fake_mac_enabled:
            mylog("verbose", [f"[{pluginName}] Generating FAKE MAC for ip: {ip}"])
            mac = string_to_fake_mac(ip)

        if not mac:
            # Skip devices without MAC if fake MAC not allowed
            mylog("verbose", [f"[{pluginName}] Skipping device with {ip} as no MAC supplied and ADGUARDIMP_FAKE_MAC set to False"])
            continue

        device_data.append({
            "mac_address": mac,
            "ip_address": ip,
            "hostname": hostname,
            "device_type": dsource
        })

    # -------------------------------------------
    # Write plugin objects
    # -------------------------------------------
    for dev in device_data:
        plugin_objects.add_object(
            primaryId   = dev["mac_address"],
            secondaryId = dev["ip_address"],
            watched1    = dev["hostname"],
            watched2    = dev["device_type"],
            watched3    = '',
            watched4    = '',
            extra       = '',
            foreignKey  = dev["mac_address"],
        )

    mylog("verbose", [f"[{pluginName}] New entries: {len(device_data)}"])
    plugin_objects.write_result_file()
    return 0


if __name__ == "__main__":
    main()
