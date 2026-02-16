#!/usr/bin/env python

import os
import argparse
import sys
import subprocess

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger, append_line_to_file  # noqa: E402 [flake8 lint suppression]
from utils.datetime_utils import timeNowUTC  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value   # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'NMAP'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)


# -------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Scan ports of devices specified by IP addresses'
    )

    # Accept ANY key=value pairs
    parser.add_argument('params', nargs='+', help="key=value style params")

    raw = parser.parse_args()

    try:
        args = parse_kv_args(raw.params)
    except ValueError as e:
        mylog('error', [f"[{pluginName}] Argument error: {e}"])
        sys.exit(1)

    # Required keys
    required = ['ips', 'macs']
    for key in required:
        if key not in args:
            mylog('error', [f"[{pluginName}] Missing required parameter: {key}"])
            sys.exit(1)

    # Parse lists
    ip_list = safe_split_list(args['ips'], "ips")
    mac_list = safe_split_list(args['macs'], "macs")

    if len(ip_list) != len(mac_list):
        mylog('error', [
            f"[{pluginName}] Mismatch: {len(ip_list)} IPs but {len(mac_list)} MACs"
        ])
        sys.exit(1)

    # Optional
    timeout = int(args.get("timeout", get_setting_value("NMAP_RUN_TIMEOUT")))

    NMAP_ARGS = get_setting_value("NMAP_ARGS")

    mylog('debug', [f'[{pluginName}] Parsed IPs: {ip_list}'])
    mylog('debug', [f'[{pluginName}] Parsed MACs: {mac_list}'])
    mylog('debug', [f'[{pluginName}] Timeout: {timeout}'])
    mylog('debug', [f'[{pluginName}] NMAP_ARGS: {NMAP_ARGS}'])

    entries = performNmapScan(
        ip_list,
        mac_list,
        timeout,
        NMAP_ARGS
    )

    mylog('verbose', [f'[{pluginName}] Total number of ports found by NMAP: ', len(entries)])

    for entry in entries:

        plugin_objects.add_object(
            primaryId   = entry.mac,    # MAC (Device Name)
            secondaryId = entry.port,   # IP Address (always 0.0.0.0)
            watched1    = entry.state,  # Device Name
            watched2    = entry.service,
            watched3    = entry.ip + ":" + entry.port,
            watched4    = "",
            extra       = entry.extra,
            foreignKey  = entry.mac
        )

    plugin_objects.write_result_file()


# -------------------------------------------------------------------------------
class nmap_entry:
    def __init__(self, ip, mac, time, port, state, service, name = '', extra = '', index = 0):
        self.ip = ip
        self.mac = mac
        self.time = time
        self.port = port
        self.state = state
        self.service = service
        self.extra = extra
        self.index = index
        self.hash = str(mac) + str(port) + str(state) + str(service)


# -------------------------------------------------------------------------------
def parse_kv_args(raw_args):
    """
    Converts ['ips=a,b,c', 'macs=x,y,z', 'timeout=5'] to a dict.
    Ignores unknown keys.
    """
    parsed = {}

    for item in raw_args:
        if '=' not in item:
            mylog('none', [f"[{pluginName}] Scan: Invalid parameter (missing '='): {item}"])

        key, value = item.split('=', 1)

        if key in parsed:
            mylog('none', [f"[{pluginName}] Scan: Duplicate parameter supplied: {key}"])

        parsed[key] = value

    return parsed


# -------------------------------------------------------------------------------
def safe_split_list(value, keyname):
    """Split comma list safely and ensure no empty items."""
    items = [x.strip() for x in value.split(',') if x.strip()]
    if not items:
        mylog('none', [f"[{pluginName}] Scan: {keyname} list is empty or invalid"])
    return items


# -------------------------------------------------------------------------------
def performNmapScan(deviceIPs, deviceMACs, timeoutSec, args):
    """
    run nmap scan on a list of devices
    discovers open ports and keeps track existing and new open ports
    """

    # collect ports / new Nmap Entries
    newEntriesTmp = []

    if len(deviceIPs) > 0:

        devTotal = len(deviceIPs)

        mylog('verbose', [f'[{pluginName}] Scan: Nmap for max ', str(timeoutSec), 's (' + str(round(int(timeoutSec) / 60, 1)) + 'min) per device'])
        mylog('verbose', ["[NMAP Scan] Estimated max delay: ", (devTotal * int(timeoutSec)), 's ', '(', round((devTotal * int(timeoutSec)) / 60, 1) , 'min)'])

        devIndex = 0
        for ip in deviceIPs:
            # Execute command
            output = ""
            # prepare arguments from user supplied ones
            nmapArgs = ['nmap'] + args.split() + [ip]

            progress = ' (' + str(devIndex + 1) + '/' + str(devTotal) + ')'

            try:
                # try runnning a subprocess with a forced (timeout)  in case the subprocess hangs
                output = subprocess.check_output(
                    nmapArgs,
                    universal_newlines=True,
                    stderr=subprocess.STDOUT,
                    timeout=(float(timeoutSec))
                )
            except subprocess.CalledProcessError as e:
                # An error occured, handle it
                mylog('none', ["[NMAP Scan] ", e.output])
                mylog('none', ["[NMAP Scan] ⚠ ERROR - Nmap Scan - check logs", progress])
            except subprocess.TimeoutExpired:
                mylog('verbose', [f'[{pluginName}] Nmap TIMEOUT - the process forcefully terminated as timeout reached for ', ip, progress])

            if output == "":  # check if the subprocess failed
                mylog('minimal', [f'[{pluginName}] Nmap FAIL for ', ip, progress, ' check logs for details'])
            else:
                mylog('verbose', [f'[{pluginName}] Nmap SUCCESS for ', ip, progress])

            #  check the last run output
            newLines = output.split('\n')

            # regular logging
            for line in newLines:
                append_line_to_file(logPath + '/app_nmap.log', line + '\n')

            index = 0
            startCollecting = False
            duration = ""
            newPortsPerDevice = 0
            for line in newLines:
                if 'Starting Nmap' in line:
                    if len(newLines) > index + 1 and 'Note: Host seems down' in newLines[index + 1]:
                        break  # this entry is empty
                elif 'PORT' in line and 'STATE' in line and 'SERVICE' in line:
                    startCollecting = True
                elif 'PORT' in line and 'STATE' in line and 'SERVICE' in line:
                    startCollecting = False  # end reached
                elif startCollecting and len(line.split()) == 3:
                    newEntriesTmp.append(nmap_entry(ip, deviceMACs[devIndex], timeNowUTC(), line.split()[0], line.split()[1], line.split()[2]))
                    newPortsPerDevice += 1
                elif 'Nmap done' in line:
                    duration = line.split('scanned in ')[1]

            mylog('verbose', [f'[{pluginName}] {newPortsPerDevice} ports found on {deviceMACs[devIndex]} after {duration}'])

            index += 1
            devIndex += 1

        return newEntriesTmp


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == '__main__':
    main()
