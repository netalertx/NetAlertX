#!/usr/bin/env python

import os
import sys
from pytz import timezone
import asyncio
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from typing import cast
import socket
import freebox_api
from freebox_api import Freepybox
from freebox_api.api.lan import Lan
from freebox_api.api.system import System
from freebox_api.exceptions import NotOpenError, AuthorizationError

# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC, DATETIME_PATTERN  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value("TIMEZONE"))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'FREEBOX'

# Define the current path and log file paths
LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)

device_type_map = {
    "workstation": "PC",
    "laptop": "Laptop",
    "smartphone": "Smartphone",
    "tablet": "Tablet",
    "printer": "Printer",
    "vg_console": "Game Console",
    "television": "SmartTV",
    "nas": "NAS",
    "ip_camera": "IP Camera",
    "ip_phone": "Phone",
    "freebox_player": "TV Decoder",
    "freebox_hd": "TV Decoder",
    "freebox_crystal": "TV Decoder",
    "freebox_mini": "TV Decoder",
    "freebox_delta": "Gateway",
    "freebox_one": "Gateway",
    "freebox_wifi": "Gateway",
    "freebox_pop": "AP",
    "networking_device": "Router",
    "multimedia_device": "TV Decoder",
    "car": "House Appliance",
    "watch": "Clock",
    "light": "Domotic",
    "outlet": "Domotic",
    "appliances": "House Appliance",
    "thermostat": "Domotic",
    "shutter": "Domotic",
    "other": "(Unknown)",
}


def map_device_type(type: str):
    try:
        return device_type_map[type]
    except KeyError:
        # This device type has not been mapped yet
        mylog("minimal", [f"[{pluginName}] Unknown device type: {type}"])
        return device_type_map["other"]


def select_l3_entries_for_presence(host):
    """
    Select which l3connectivities entries represent presence for a host this
    cycle: every currently-reachable entry if at least one exists; otherwise,
    if the host itself is active, a single best-effort entry (preferring one
    Freebox still marks active even though unreachable, else the first
    entry, else an empty dict if there are no L3 entries at all); otherwise
    (host not active) an empty list.
    """
    l3 = host.get("l3connectivities")
    if not isinstance(l3, list):
        l3 = []

    reachable = [ip for ip in l3 if ip.get("reachable")]
    if reachable:
        return reachable

    # Default True if the API unexpectedly omits "active", so a schema
    # surprise fails open instead of silently reintroducing the #1828 bug.
    if not host.get("active", True):
        return []

    mylog("verbose", [f"[{pluginName}] Host active but no reachable L3 address - using fallback IP"])
    if l3:
        # Each l3connectivities entry has its own "active" flag, independent
        # of "reachable" - prefer one Freebox still considers active over an
        # arbitrary stale entry; fall back to the first entry if none are.
        return [next((e for e in l3 if e.get("active")), l3[0])]

    # No L3 data at all for this host this cycle - still assert presence
    # (primaryId/MAC alone is enough), but don't fabricate an address or
    # timestamp. main() leaves secondaryId/watched4 blank for an empty dict.
    return [{}]


async def get_device_data(api_version: int, api_address: str, api_port: int):
    # ensure existence of db path
    data_dir = Path(os.getenv("NETALERTX_CONFIG", "/data/config")) / "freeboxdb"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Instantiate Freepybox class using default application descriptor
    # and custom token_file location
    fbx = Freepybox(
        app_desc={
            "app_id": "netalertx",
            "app_name": "NetAlertX",
            "app_version": freebox_api.__version__,
            "device_name": socket.gethostname(),
        },
        api_version="v" + str(api_version),
        token_file=data_dir / "token",
    )

    # Connect to the freebox
    # Be ready to authorize the application on the Freebox if you run this
    # for the first time
    try:
        await fbx.open(host=api_address, port=str(api_port))
    except NotOpenError as e:
        mylog("verbose", [f"[{pluginName}] Error connecting to freebox: {e}"])
        return None, []
    except AuthorizationError as e:
        mylog("verbose", [f"[{pluginName}] Auth error: {str(e)}"])
        return None, []

    # get also info of the freebox itself
    config = await cast(System, fbx.system).get_config()
    freebox = await cast(Lan, fbx.lan).get_config()
    hosts = await cast(Lan, fbx.lan).get_hosts_list()
    assert config is not None
    assert freebox is not None
    freebox["mac"] = config["mac"]
    freebox["operator"] = config["model_info"]["net_operator"]

    # Close the freebox session
    await fbx.close()

    return freebox, hosts


def main():
    mylog("verbose", [f"[{pluginName}] In script"])

    # Retrieve configuration settings
    api_settings = {
        "api_address": get_setting_value("FREEBOX_address"),
        "api_version": get_setting_value("FREEBOX_api_version"),
        "api_port": get_setting_value("FREEBOX_api_port"),
    }

    mylog("verbose", [f"[{pluginName}] Settings: {api_settings}"])

    # retrieve data
    loop = asyncio.new_event_loop()
    freebox, hosts = loop.run_until_complete(get_device_data(**api_settings))
    loop.close()

    mylog("verbose", [freebox])
    mylog("verbose", [hosts])

    if freebox:
        plugin_objects.add_object(
            primaryId=freebox["mac"],
            secondaryId=freebox["ip"],
            watched1=freebox["name"],
            watched2=freebox["operator"],
            watched3="Gateway",
            watched4=timeNowUTC(),
            extra="",
            foreignKey=freebox["mac"],
        )
    for host in hosts:
        mac: str = host.get("l2ident", {}).get("id", "(unknown)")
        if mac == '(unknown)':
            continue
        for ip in select_l3_entries_for_presence(host):
            if "last_time_reachable" in ip:
                # .get(..., 0) alone isn't enough: the Freebox API can return this
                # key present but explicitly null, and dict.get()'s default only
                # applies when the key is absent, not when its value is None -
                # `or 0` catches both, avoiding a TypeError from fromtimestamp(None).
                watched4 = datetime.fromtimestamp(ip.get("last_time_reachable") or 0, tz=dt_timezone.utc).strftime(DATETIME_PATTERN)
            else:
                # select_l3_entries_for_presence()'s no-L3-data fallback ({}) -
                # leave blank rather than fabricating an epoch-zero timestamp.
                watched4 = ""
            plugin_objects.add_object(
                primaryId=mac,
                secondaryId=ip.get("addr", ""),
                watched1=host.get("primary_name", "(unknown)"),
                watched2=host.get("vendor_name", "(unknown)"),
                watched3=map_device_type(host.get("host_type", "")),
                watched4=watched4,
                extra="",
                foreignKey=mac,
            )

    # Commit result
    plugin_objects.write_result_file()

    return 0


if __name__ == "__main__":
    main()
