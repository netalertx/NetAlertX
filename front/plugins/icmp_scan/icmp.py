#!/usr/bin/env python
# test script by running:
# tbc

import os
import subprocess
import sys
import re
import ipaddress

# Register NetAlertX directories
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects, parse_scan_subnets  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from models.device_instance import DeviceInstance  # noqa: E402 [flake8 lint suppression]
from utils.crypto_utils import string_to_fake_mac  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

pluginName = 'ICMP'

LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')


def get_device_by_ip(ip, all_devices):
    """Get existing device based on IP"""
    for device in all_devices:
        if device["devLastIP"] == ip:
            return device

    return None


def main():

    mylog('verbose', [f'[{pluginName}] In script'])

    timeout = get_setting_value('ICMP_RUN_TIMEOUT')
    args = get_setting_value('ICMP_ARGS')
    regex  = get_setting_value('ICMP_IN_REGEX')
    mode = get_setting_value('ICMP_MODE')
    fakeMac = get_setting_value('ICMP_FAKE_MAC')
    scan_subnets = get_setting_value("SCAN_SUBNETS")

    parsed = parse_scan_subnets(scan_subnets)

    subnets = [x.subnet for x in parsed]
    interfaces = [
        x.resolved_interface
        for x in parsed
        if x.resolved_interface
    ]

    # Initialize the Plugin obj output file
    plugin_objects = Plugin_Objects(RESULT_FILE)

    # Create a DeviceInstance instance
    device_handler = DeviceInstance()

    # Retrieve devices
    all_devices = device_handler.getAll()

    # Compile the regex for efficiency if it will be used multiple times
    regex_pattern = re.compile(regex)

    if mode == "ping":
        plugin_objects = execute_ping(timeout, args, all_devices, regex_pattern, plugin_objects)

    elif mode == "fping":
        plugin_objects = execute_fping(timeout, args, all_devices, plugin_objects, subnets, interfaces, fakeMac)

    plugin_objects.write_result_file()

    mylog('verbose', [f'[{pluginName}] Script finished - {len(plugin_objects)} added or updated'])

    return 0


# ===============================================================================
# Execute scan
# ===============================================================================
def execute_ping(timeout, args, all_devices, regex_pattern, plugin_objects):
    """
    Execute ICMP command on filtered devices.
    """

    # Filter devices based on the regex match
    filtered_devices = [
        device for device in all_devices
        if regex_pattern.match(device['devLastIP'])
    ]

    mylog('verbose', [f'[{pluginName}] Devices to PING: {len(filtered_devices)}'])

    for device in filtered_devices:

        cmd = ["ping"] + args.split() + [device['devLastIP']]

        output = ""

        # Parse output using case-insensitive regular expressions
        # Synology-NAS:/# ping -i 0.5 -c 3 -W 8 -w 9 192.168.1.82
        # PING 192.168.1.82 (192.168.1.82): 56 data bytes
        # 64 bytes from 192.168.1.82: seq=0 ttl=64 time=0.080 ms
        # 64 bytes from 192.168.1.82: seq=1 ttl=64 time=0.081 ms
        # 64 bytes from 192.168.1.82: seq=2 ttl=64 time=0.089 ms

        # --- 192.168.1.82 ping statistics ---
        # 3 packets transmitted, 3 packets received, 0% packet loss
        # round-trip min/avg/max = 0.080/0.083/0.089 ms
        # Synology-NAS:/# ping -i 0.5 -c 3 -W 8 -w 9 192.168.1.82a
        # ping: bad address '192.168.1.82a'
        # Synology-NAS:/# ping -i 0.5 -c 3 -W 8 -w 9 192.168.1.92
        # PING 192.168.1.92 (192.168.1.92): 56 data bytes

        # --- 192.168.1.92 ping statistics ---
        # 3 packets transmitted, 0 packets received, 100% packet loss

        try:
            output = subprocess.check_output(
                cmd, universal_newlines=True, stderr=subprocess.STDOUT, timeout=timeout, text=True
            )

            mylog("verbose", [f"[{pluginName}] DEBUG OUTPUT : {output}"])

            is_online = True
            if re.search(r"0% packet loss", output, re.IGNORECASE):
                is_online = True
            elif re.search(r"bad address", output, re.IGNORECASE):
                is_online = False
            elif re.search(r"100% packet loss", output, re.IGNORECASE):
                is_online = False

            if is_online:

                plugin_objects.add_object(
                    # "MAC", "IP", "Name", "Output"
                    primaryId   = device['devMac'],
                    secondaryId = device['devLastIP'],
                    watched1    = device['devName'],
                    watched2    = output.replace('\n', ''),
                    watched3    = 'ping',  # mode
                    watched4    = '',
                    extra       = '',
                    foreignKey  = device['devMac']
                )

            mylog('verbose', [f"[{pluginName}] ip: {device['devLastIP']} is_online: {is_online}"])

        except subprocess.CalledProcessError as e:
            mylog("verbose", [f"[{pluginName}] ⚠ ERROR - check logs"])
            mylog("verbose", [f"[{pluginName}]", e.output])
        except subprocess.TimeoutExpired:
            mylog("verbose", [f"[{pluginName}] TIMEOUT - process terminated"])

    return plugin_objects


def execute_fping(timeout, args, all_devices, plugin_objects, subnets, interfaces, fakeMac):
    """
    Run fping command and return alive IPs (IPv4 and IPv6).
    Handles:
      - fping exit code 1 (some hosts unreachable)
      - Mixed subnets, known IPs, and IPv6
      - Automatic CIDR subnet expansion
    """

    device_map = {d["devLastIP"]: d for d in all_devices if d.get("devLastIP")}
    known_ips = list(device_map.keys())
    online_results = []  # list of tuples (ip, full_line)

    # Regex patterns
    ipv4_pattern = r'\d{1,3}(?:\.\d{1,3}){3}'
    ipv6_pattern = r'([0-9a-fA-F:]+)'
    ip_pattern = f'{ipv4_pattern}|{ipv6_pattern}'
    ip_regex = re.compile(ip_pattern)

    def expand_subnets(targets):
        """Expand CIDR subnets to list of IPs if needed."""
        expanded = []
        for t in targets:
            t = t.strip()
            if "/" in t:
                try:
                    net = ipaddress.ip_network(t, strict=False)
                    expanded.extend([str(ip) for ip in net.hosts()])
                except ValueError:
                    expanded.append(t)
            else:
                expanded.append(t)
        return expanded

    def run_fping(targets):
        targets = expand_subnets(targets)

        if not targets:
            return []

        ipv4_targets = [t for t in targets if ':' not in t]
        ipv6_targets = [t for t in targets if ':' in t]

        def run_family(family_targets, ipv6=False):
            if not family_targets:
                return []

            interface_list = interfaces if interfaces else [None]

            all_results = []
            seen_ips = set()

            for interface in interface_list:

                cmd = ["fping", "-a"]

                if ipv6:
                    cmd.append("-6")

                cmd += args.split()

                if interface:
                    cmd += ["-I", interface]

                cmd += family_targets

                mylog("verbose", [f"[{pluginName}] fping cmd: {' '.join(cmd)}"])

                try:
                    output = subprocess.check_output(
                        cmd,
                        stderr=subprocess.DEVNULL,
                        timeout=timeout,
                        text=True
                    )

                except subprocess.CalledProcessError as e:
                    output = e.output
                    mylog("none", [
                        f"[{pluginName}] fping returned non-zero exit code "
                        f"on interface {interface}, reading alive hosts anyway"
                    ])

                except subprocess.TimeoutExpired:
                    mylog("none", [
                        f"[{pluginName}] fping timeout on interface {interface}"
                    ])
                    continue

                for line in output.splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    lower_line = line.lower()

                    if "unreachable" in lower_line or "timed out" in lower_line or "100% loss" in lower_line:
                        continue

                    match = ip_regex.search(line)

                    if match:
                        ip = match.group(0)

                        if ip in seen_ips:
                            continue

                        seen_ips.add(ip)
                        all_results.append((ip, line))

            return all_results

        return run_family(ipv4_targets, ipv6=False) + run_family(ipv6_targets, ipv6=True)

    # Scan subnets
    mylog("verbose", [f"[{pluginName}] run_fping: subnets {subnets}"])
    online_results += run_fping(subnets)

    # Scan known IPs
    mylog("verbose", [f"[{pluginName}] run_fping: known_ips {known_ips}"])
    online_results += run_fping(known_ips)

    # Remove duplicates by IP
    seen = set()
    online_results_unique = []
    for ip, full_line in online_results:
        if ip not in seen:
            seen.add(ip)
            online_results_unique.append((ip, full_line))

    # Process all online IPs
    for onlineIp, full_line in online_results_unique:
        if onlineIp in device_map:
            device = device_map[onlineIp]
            plugin_objects.add_object(
                primaryId   = device['devMac'],
                secondaryId = device['devLastIP'],
                watched1    = device['devName'],
                watched2    = full_line,
                watched3    = 'fping',  # mode
                watched4    = '',
                extra       = '',
                foreignKey  = device['devMac']
            )
        elif fakeMac:
            fakeMacFromIp = string_to_fake_mac(onlineIp)
            plugin_objects.add_object(
                primaryId   = fakeMacFromIp,
                secondaryId = onlineIp,
                watched1    = "(unknown)",
                watched2    = full_line,
                watched3    = 'fping',  # mode
                watched4    = '',
                extra       = '',
                foreignKey  = fakeMacFromIp
            )
        else:
            mylog('verbose', [f"[{pluginName}] Skipping: {onlineIp}, as new IP and ICMP_FAKE_MAC not enabled"])

    # log only the IPs
    mylog('verbose', [f"[{pluginName}] online_ips: {[ip for ip, _ in online_results_unique]}"])

    return plugin_objects


# ===============================================================================
# BEGIN
# ===============================================================================
if __name__ == '__main__':
    main()
