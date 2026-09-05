#!/usr/bin/env python

from __future__ import unicode_literals
import subprocess
import argparse
import os
import sys

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/server/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects, handleEmpty, normalize_mac  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value   # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = "SNMPDSC"

LOG_PATH = logPath + '/plugins'
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def main():
    mylog('verbose', f"[{pluginName}] In script ")

    # init global variables
    global snmpWalkCmds

    parser = argparse.ArgumentParser(description='This plugin is used to discover devices via the arp table(s) of a RFC1213 compliant router or switch.')
    parser.add_argument(
        'routers',
        action="store",
        help="IP(s) of routers, separated by comma (,) if passing multiple"
    )

    values = parser.parse_args()

    timeoutSetting = get_setting_value("SNMPDSC_RUN_TIMEOUT")

    plugin_objects = Plugin_Objects(RESULT_FILE)

    if values.routers:
        snmpWalkCmds = values.routers.split('=')[1].replace('\'', '')

        if ',' in snmpWalkCmds:
            commands = snmpWalkCmds.split(',')
        else:
            commands = [snmpWalkCmds]

        for cmd in commands:
            mylog('verbose', [f"[{pluginName}] Router snmpwalk command: ", cmd])
            # split the string, remove white spaces around each item, and exclude any empty strings
            snmpwalkArgs = [arg.strip() for arg in cmd.split(' ') if arg.strip()]

            # Execute N probes and insert in list
            probes = 1  # N probes

            for _ in range(probes):
                output = subprocess.check_output(
                    snmpwalkArgs,
                    universal_newlines=True,
                    stderr=subprocess.STDOUT,
                    timeout=(timeoutSetting)
                )

                mylog('verbose', [f"[{pluginName}] output: ", output])

                lines = output.split('\n')

                for line in lines:

                    tmpSplt = line.split('"')

                    # Expected Format:
                    # mib-2.3.1.1.2.15.1.192.168.1.14 "2C F4 32 18 61 43 "
                    if len(tmpSplt) == 3:

                        ipStr = tmpSplt[0].split('.')[-4:]  # Get the last 4 elements to extract the IP
                        macStr = tmpSplt[1].split()  # Split on any whitespace run, discarding empty tokens

                        if len(ipStr) == 4:
                            macAddress = normalize_mac(':'.join(macStr))
                            ipAddress = '.'.join(ipStr)

                            mylog('verbose', [f"[{pluginName}] IP: {ipAddress} MAC: {macAddress}"])

                            plugin_objects.add_object(
                                primaryId   = handleEmpty(macAddress),
                                secondaryId = handleEmpty(ipAddress.strip()),  # Remove leading/trailing spaces from IP
                                watched1    = '(unknown)',
                                watched2    = handleEmpty(snmpwalkArgs[6]),  # router IP
                                extra       = handleEmpty(line),
                                foreignKey  = handleEmpty(macAddress)  # Use the primary ID as the foreign key
                            )
                        else:
                            mylog('verbose', [f"[{pluginName}] ipStr does not seem to contain a valid IP:", ipStr])

                    # Expected Format:
                    # IP-MIB::ipNetToMediaPhysAddress.17.10.10.3.202 = STRING: f8:81:1a:ef:ef:ef
                    elif "ipNetToMediaPhysAddress" in line and "=" in line and "STRING:" in line:

                        # Split on "=" → ["IP-MIB::ipNetToMediaPhysAddress.xxx.xxx.xxx.xxx ", " STRING: aa:bb:cc:dd:ee:ff"]
                        left, right = line.split("=", 1)

                        # Extract the MAC (right side)
                        macAddress = right.split("STRING:")[-1].strip()
                        macAddress = normalize_mac(macAddress)

                        # Extract IP address from the left side
                        # tail of the OID: last 4 integers = IPv4 address
                        oid_parts = left.strip().split('.')
                        ip_parts  = oid_parts[-4:]
                        ipAddress = ".".join(ip_parts)

                        mylog('verbose', [f"[{pluginName}] (fallback) IP: {ipAddress} MAC: {macAddress}"])

                        plugin_objects.add_object(
                            primaryId   = handleEmpty(macAddress),
                            secondaryId = handleEmpty(ipAddress),
                            watched1    = '(unknown)',
                            watched2    = handleEmpty(snmpwalkArgs[6]),
                            extra       = handleEmpty(line),
                            foreignKey  = handleEmpty(macAddress)
                        )

                        continue

                    # Expected Format:
                    # ipNetToMediaPhysAddress[3][192.168.1.9] 6C:6C:6C:6C:6C:b6C1
                    elif line.startswith('ipNetToMediaPhysAddress'):
                        # Format: snmpwalk -OXsq output
                        parts = line.split()
                        if len(parts) == 2:

                            ipAddress  = parts[0].split('[')[-1][:-1]
                            macAddress = normalize_mac(parts[1])

                            mylog('verbose', [f"[{pluginName}] IP: {ipAddress} MAC: {macAddress}"])

                            plugin_objects.add_object(
                                primaryId   = handleEmpty(macAddress),
                                secondaryId = handleEmpty(ipAddress.strip()),
                                watched1    = '(unknown)',
                                watched2    = handleEmpty(snmpwalkArgs[6]),
                                extra       = handleEmpty(line),
                                foreignKey  = handleEmpty(macAddress)
                            )

    mylog('verbose', [f"[{pluginName}] Entries found: ", len(plugin_objects)])

    plugin_objects.write_result_file()


# BEGIN
if __name__ == '__main__':
    main()
