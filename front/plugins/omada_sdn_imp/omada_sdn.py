#!/usr/bin/env python
__author__ = "ffsb"
__version__ = "0.1"  # initial
__version__ = "0.2"  # added logic to retry omada api call once as it seems to sometimes fail for some reasons, and error handling logic...
__version__ = "0.3"  # split devices API calls to allow multithreading but had to stop due to concurency issues.
__version__ = "0.6"  # found issue with multithreading - my omada calls redirect stdout which gets clubbered by normal stdout... not sure how to fix for now...
__version__ = "0.7"  # avoid updating omada sdn client name when it is the MAC, and naxname is also the same MAC...
__version__ = "1.0"  # fixed the timzone mylog issue by resetting the tz value at the begining of the script... I suspect it doesn't inherit the tz from the main.
__version__ = "1.1"  # added logic to handle gracefully a failure of omada devices so it won't try to populate uplinks on non-existent switches and AP.
__version__ = "1.2"  # finally got multiprocessing to work to parse devices AND to update names! yeah!
__version__ = "1.3"  # fix detection of the default gateway IP address that would pick loopback address instead of the actual gateway.


# query OMADA SDN to populate NetAlertX witch omada switches, access points, clients.
# try to identify and populate their connections by switch/accesspoints and ports/SSID
# try to differentiate root bridges from accessory

# sample code to update unbound on opnsense - for reference...
# curl -X POST -d '{"host":{"enabled":"1","hostname":"test","domain":"testdomain.com","rr":"A","mxprio":"","mx":"","server":"10.0.1.1","description":""}}'\
#  -H "Content-Type: application/json" -k -u $OPNS_KEY:$OPNS_SECRET https://$IPFW/api/unbound/settings/AddHostOverride
#
import os
import sys
import time
import io
import re

# import concurrent.futures
import subprocess
import multiprocessing


# Define the installation path and extend the system path for plugin imports
INSTALL_PATH = os.getenv('NETALERTX_APP', '/app')
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Objects  # noqa: E402 [flake8 lint suppression]
from logger import mylog, Logger  # noqa: E402 [flake8 lint suppression]
from const import logPath  # noqa: E402 [flake8 lint suppression]
from helper import get_setting_value  # noqa: E402 [flake8 lint suppression]
from pytz import timezone  # noqa: E402 [flake8 lint suppression]
import conf  # noqa: E402 [flake8 lint suppression]

# Make sure the TIMEZONE for logging is correct
conf.tz = timezone(get_setting_value('TIMEZONE'))

# Make sure log level is initialized correctly
Logger(get_setting_value('LOG_LEVEL'))

PARALLELISM = 4

pluginName = "OMDSDN"

# Define the current path and log file paths
LOG_PATH = logPath + '/plugins'
LOG_FILE = os.path.join(LOG_PATH, f'script.{pluginName}.log')
RESULT_FILE = os.path.join(LOG_PATH, f'last_result.{pluginName}.log')

OMADA_API_RETURN_FILE = os.path.join(LOG_PATH, "omada_api_return")

# Initialize the Plugin obj output file
plugin_objects = Plugin_Objects(RESULT_FILE)
#
# sample target output:
#  0 MAC, 1 IP, 2 Name, 3 switch/AP, 4 port/SSID, 5 TYPE
# 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-6F', '192.168.0.217', '1A-2B-3C-4D-5E-6F', '17', '40-AE-30-A5-A7-50, 'Switch']"

# Constants for array indices
MAC, IP, NAME, SWITCH_AP, PORT_SSID, TYPE = range(6)

# sample omada devices input format:
#
#  0.MAC                    1.IP    2.type  3.status           4.name              5.model
# 40-AE-30-A5-A7-50    192.168.0.11      ap CONNECTED        office_Access_point         EAP773(US) v1.0
# B0-95-75-46-0C-39     192.168.0.4  switch CONNECTED        pantry12             T1600G-52PS v4.0
dMAC, dIP, dTYPE, dSTATUS, dNAME, dMODEL = range(6)

# sample omada clients input format:
#  0 MAC, 1 IP, 2 Name, 3 switch/AP, 4 port/SSID,
# 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-6F', '192.168.0.217', '1A-2B-3C-4D-5E-6F', 'myssid_name2', '(office_Access_point)']"
# 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-01', '192.168.0.153', 'frontyard_ESP_29E753', 'pantry12', '(48)']"
# 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-02', '192.168.0.1', 'bastion', 'office24', '(23)']"
# 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-03', '192.168.0.226', 'brick', 'myssid_name3', '(office_Access_point)']"
cMAC, cIP, cNAME, cSWITCH_AP, cPORT_SSID = range(5)

OMDLOGLEVEL = "debug"


# translate MAC address from standard ieee model to ietf draft
# AA-BB-CC-DD-EE-FF to aa:bb:cc:dd:ee:ff
# tplink adheres to ieee,  Nax adheres to ietf
def ieee2ietf_mac_formater(inputmac):
    return inputmac.lower().replace("-", ":")


def ietf2ieee_mac_formater(inputmac):
    if not inputmac or not isinstance(inputmac, str):
        mylog(
            "minimal",
            [
                f"[{pluginName}] ietf2ieee_mac_formater ERROR: inputmac is not a string: {inputmac}"
            ],
        )
        return None
    return inputmac.upper().replace(":", "-")


def get_mac_from_IP(target_IP):
    from scapy.all import ARP, Ether, srp

    try:
        arp_request = ARP(pdst=target_IP)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp_request
        result = srp(packet, timeout=3, verbose=0)[0]
        if result:
            return result[0][1].hwsrc
        else:
            return None
    except Exception as e:
        mylog("minimal", [f"[{pluginName}] get_mac_from_IP ERROR:{e}"])
        return None


#
# wrapper to call the omada python library's own wrapper
# it returns the output as a multiline python string
#
def callomada(myargs):
    arguments = " ".join(myargs)
    mylog("verbose", [f"[{pluginName}] callomada:{arguments}"])
    from tplink_omada_client.cli import main as omada
    from contextlib import redirect_stdout

    omada_output = ""
    retries = 2
    while omada_output == "" and retries > 0:
        retries = retries - 1
        try:
            mf = io.StringIO()
            with redirect_stdout(mf):
                omada(myargs)
            omada_output = mf.getvalue()
        except Exception:
            mylog(
                "minimal",
                [f"[{pluginName}] ERROR WHILE CALLING callomada:{arguments}\n {mf}"],
            )
            omada_output = ""
    return omada_output


#
# extract all the mac addresses from a multilines text...
# return a list of MAC as 'string'
#
def extract_mac_addresses(text):
    mac_pattern = r"([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})"
    mac_addresses = re.findall(mac_pattern, text)
    return ["".join(parts) for parts in mac_addresses]


def find_default_gateway_ip():
    # Get the routing table
    from scapy.all import conf

    routing_table = conf.route.routes
    for route in routing_table:
        # Each route is a tuple: (destination, netmask, gateway, iface, output_ip, metric)
        destination, netmask, gateway, iface, output_ip, metric = route
        # Look for the default route (destination and netmask are both 0.0.0.0)
        if destination == 0 and netmask == 0 and gateway != "0.0.0.0":
            mylog("verbose", [f"[DEBUG] Default Gateway IP: {gateway}"])
            return gateway  # Found the default gateway

    return None  # Default gateway not found


def add_uplink(
    uplink_mac,
    switch_mac,
    device_data_bymac,
    sadevices_linksbymac,
    port_byswitchmac_byclientmac,
):
    # Ensure switch exists
    if switch_mac not in device_data_bymac:
        mylog("none", [f"[{pluginName}] switch_mac '{switch_mac}' not found in device_data_bymac"])
        return

    dev_switch = device_data_bymac[switch_mac]

    # Ensure list is long enough to contain SWITCH_AP index
    if len(dev_switch) <= SWITCH_AP:
        mylog("none", [f"[{pluginName}] SWITCH_AP index {SWITCH_AP} missing in record for {switch_mac}"])
        return

    # Add uplink only if empty
    if dev_switch[SWITCH_AP] in (None, "null"):
        dev_switch[SWITCH_AP] = uplink_mac

        # Validate uplink_mac exists
        if uplink_mac not in device_data_bymac:
            mylog("none", [f"[{pluginName}] uplink_mac '{uplink_mac}' not found in device_data_bymac"])
            return

        dev_uplink = device_data_bymac[uplink_mac]

        # Get TYPE safely
        switch_type = dev_switch[TYPE] if len(dev_switch) > TYPE else None
        uplink_type = dev_uplink[TYPE] if len(dev_uplink) > TYPE else None

        # Switch-to-switch link → use port mapping
        if switch_type == "Switch" and uplink_type == "Switch":
            port_to_uplink = port_byswitchmac_byclientmac.get(switch_mac, {}).get(uplink_mac)
            if port_to_uplink is None:
                mylog("none", [
                    f"[{pluginName}] Missing port info for {switch_mac} → {uplink_mac}"
                ])
                return
        else:
            # Other device types → read PORT_SSID index
            if len(dev_uplink) <= PORT_SSID:
                mylog("none", [
                    f"[{pluginName}] PORT_SSID index missing for uplink {uplink_mac}"
                ])
                return
            port_to_uplink = dev_uplink[PORT_SSID]

        # Assign port to switch
        if len(dev_switch) > PORT_SSID:
            dev_switch[PORT_SSID] = port_to_uplink
        else:
            mylog("none", [
                f"[{pluginName}] PORT_SSID index missing in switch {switch_mac}"
            ])

    # Process children recursively
    for link in sadevices_linksbymac.get(switch_mac, []):
        if (
            link in device_data_bymac and len(device_data_bymac[link]) > SWITCH_AP and device_data_bymac[link][SWITCH_AP] in (None, "null") and len(dev_switch) > TYPE
        ):
            if dev_switch[TYPE] == "Switch":
                add_uplink(
                    switch_mac,
                    link,
                    device_data_bymac,
                    sadevices_linksbymac,
                    port_byswitchmac_byclientmac,
                )


# ----------------------------------------------
# Main initialization
def main():
    start_time = time.time()

    mylog("verbose", [f"[{pluginName}] starting execution"])

    from models.device_instance import DeviceInstance

    # Create a DeviceInstance instance
    device_handler = DeviceInstance()
    # Retrieve configuration settings
    # these should be self-explanatory
    omada_sites = []
    omada_username = get_setting_value("OMDSDN_username")
    omada_password = get_setting_value("OMDSDN_password")
    omada_sites = get_setting_value("OMDSDN_sites")
    omada_site = omada_sites[0]
    omada_url = get_setting_value("OMDSDN_url")

    omada_login = callomada(
        [
            "-t",
            "myomada",
            "target",
            "--url",
            omada_url,
            "--user",
            omada_username,
            "--password",
            omada_password,
            "--site",
            omada_site,
            "--set-default",
        ]
    )
    mylog("verbose", [f"[{pluginName}] login to omada result is: {omada_login}"])

    clients_list = callomada(["-t", "myomada", "clients"])
    client_list_count = clients_list.count("\n")
    mylog(
        "verbose",
        [f'[{pluginName}] clients found:"{client_list_count}"\n{clients_list}'],
    )

    switches_and_aps = callomada(["-t", "myomada", "devices"])
    switches_and_aps_count = switches_and_aps.count("\n")
    mylog(
        "verbose",
        [
            f'[{pluginName}] omada devices (switches, access points) found:"{switches_and_aps_count}" \n  {switches_and_aps}'
        ],
    )

    # some_setting = get_setting_value('OMDSDN_url')

    # mylog(OMDLOGLEVEL, [f'[{pluginName}] some_setting value {some_setting}'])
    mylog(OMDLOGLEVEL, [f"[{pluginName}] ffsb"])

    # retrieve data
    device_data = get_device_data(clients_list, switches_and_aps, device_handler)

    #  Process the data into native application tables
    mylog("verbose", [f'[{pluginName}] New entries to create: "{len(device_data)}"'])
    if len(device_data) > 0:
        # insert devices into the lats_result.log
        # make sure the below mapping is mapped in config.json, for example:
        # "database_column_definitions": [
        # {
        #   "column": "Object_PrimaryID",                 <--------- the value I save into primaryId
        #   "mapped_to_column": "scanMac",                <--------- gets unserted into the CurrentScan DB table column scanMac
        #  watched1    = 'null' ,
        #  figure a way to run my udpate script delayed

        for device in device_data:
            mylog(OMDLOGLEVEL, [f'[{pluginName}] main parsing device: "{device}"'])
            myport = device[PORT_SSID] if device[PORT_SSID].isdigit() else ""
            myssid = device[PORT_SSID] if not device[PORT_SSID].isdigit() else ""
            ParentNetworkNode = (
                ieee2ietf_mac_formater(device[SWITCH_AP])
                if device[SWITCH_AP].lower() != "internet"
                else "internet"
            )
            mymac = ieee2ietf_mac_formater(device[MAC])
            plugin_objects.add_object(
                primaryId=mymac,  # MAC
                secondaryId=device[IP],  # IP
                watched1=device[NAME],  # NAME/HOSTNAME
                watched2=ParentNetworkNode,  # PARENT NETWORK NODE MAC
                watched3=myport,  # PORT
                watched4=myssid,  # SSID
                extra=device[TYPE],
                # omada_site,    #  SITENAME (scanSite) or VENDOR (scanVendor) (PICK one and adjust config.json -> "column": "Extra")
                foreignKey=device[MAC].lower().replace("-", ":"),
            )  # usually MAC

            mylog(
                "verbose",
                [
                    f'[{pluginName}] New entries: "{mymac:<18}, {device[IP]:<16}, {device[NAME]:<63}, {ParentNetworkNode:<18}, {myport:<4}, {myssid:<32}, {device[TYPE]}"'
                ],
            )
        mylog("verbose", [f'[{pluginName}] New entries: "{len(device_data)}"'])

    # log result
    plugin_objects.write_result_file()

    # mylog(OMDLOGLEVEL, [f'[{pluginName}] TEST name from MAC: {device_handler.getValueWithMac('devName','00:e2:59:00:a0:8e')}'])
    # mylog(OMDLOGLEVEL, [f'[{pluginName}] TEST MAC from IP: {get_mac_from_IP('192.168.0.1')} also {ietf2ieee_mac_formater(get_mac_from_IP('192.168.0.1'))}'])
    end_time = time.time()
    mylog(
        "verbose",
        [f"[{pluginName}] execution completed in {end_time - start_time:.2f} seconds"],
    )

    return 0


def get_omada_devices_details(msadevice_data):
    mthisswitch = msadevice_data[dMAC]
    mtype = msadevice_data[dTYPE]
    mswitch_detail = ""
    mswitch_dump = ""
    if mtype == "ap":
        mswitch_detail = callomada(["access-point", mthisswitch])
    elif mtype == "switch":
        mswitch_detail = callomada(["switch", mthisswitch])
        mswitch_dump = callomada(["-t", "myomada", "switch", "-d", mthisswitch])
    else:
        mswitch_detail = ""
    return mswitch_detail, mswitch_dump


def get_omada_devices_details_parallel(msadevice_data):
    mthisswitch = msadevice_data[dMAC]
    mtype = msadevice_data[dTYPE]
    mswitch_detail = ""
    mswitch_dump = ""
    if mtype == "ap":
        mswitch_detail = subprocess.run(
            "omada access-point " + mthisswitch,
            capture_output=True,
            text=True,
            shell=True,
        ).stdout
    elif mtype == "switch":
        mswitch_detail = subprocess.run(
            "omada switch " + mthisswitch, capture_output=True, text=True, shell=True
        ).stdout
        mswitch_dump = subprocess.run(
            "omada access-point " + mthisswitch,
            capture_output=True,
            text=True,
            shell=True,
        ).stdout
    else:
        mswitch_detail = ""
        mswitch_dump = ""
    return mthisswitch, mswitch_detail, mswitch_dump


# ----------------------------------------------
#  retrieve data
def get_device_data(omada_clients_output, switches_and_aps, device_handler):
    # sample omada devices input format:
    #  0.MAC                    1.IP    2.type  3.status           4.name              5.model
    # 40-AE-30-A5-A7-50    192.168.0.11      ap CONNECTED        office_Access_point         EAP773(US) v1.0
    # B0-95-75-46-0C-39     192.168.0.4  switch CONNECTED        pantry12             T1600G-52PS v4.0
    #
    # sample target output:
    #  0 MAC, 1 IP, 2 Name, 3 switch/AP, 4 port/SSID, 5 TYPE
    # 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-6F', '192.168.0.217', '1A-2B-3C-4D-5E-6F', '17', '40-AE-30-A5-A7-50, 'Switch']"
    # constants
    sadevices_macbyname = {}
    sadevices_linksbymac = {}
    port_byswitchmac_byclientmac = {}
    device_data_bymac = {}
    device_data_mac_byip = {}
    omada_force_overwrite = get_setting_value("OMDSDN_force_overwrite")
    switch_details = {}
    switch_dumps = {}
    """
    command = 'which omada'
    def run_command(command, index):
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        return str(index), result.stdout.strip()

    myindex, command_output= run_command(command, 2)
    mylog('verbose', [f'[{pluginName}] command={command} index={myindex} results={command_output}'])
    """
    sadevices = switches_and_aps.splitlines()
    mylog(OMDLOGLEVEL, [f'[{pluginName}] switches_and_aps rows: "{len(sadevices)}"'])

    with multiprocessing.Pool(processes=PARALLELISM) as mypool:
        oresults = mypool.map(
            get_omada_devices_details_parallel,
            [sadevice.split() for sadevice in sadevices],
        )

    for thisswitch, details, dump in oresults:
        switch_details[thisswitch] = details
        switch_dumps[thisswitch] = dump
        mylog(OMDLOGLEVEL, [f"[{pluginName}] switch={thisswitch} details={details}"])

    """
    for sadevice in sadevices:
        sadevice_data = sadevice.split()
        thisswitch = sadevice_data[dMAC]
        thistype = sadevice_data[dTYPE]
        switch_details[thisswitch], switch_dumps[thisswitch] = get_omada_devices_details(sadevice_data)
    """

    mylog(
        "verbose",
        [f'[{pluginName}] switches details collected "{len(switch_details)}"'],
    )
    mylog("verbose", [f'[{pluginName}] dump details collected "{len(switch_details)}"'])

    for sadevice in sadevices:
        sadevice_data = sadevice.split()
        thisswitch = sadevice_data[dMAC]
        sadevices_macbyname[sadevice_data[4]] = thisswitch
        if sadevice_data[dTYPE] == "ap":
            sadevice_type = "AP"
            # sadevice_details = callomada(['access-point', thisswitch])
            sadevice_details = switch_details[thisswitch]
            if sadevice_details == "":
                sadevice_links = [thisswitch]
            else:
                sadevice_links = extract_mac_addresses(sadevice_details)
            sadevices_linksbymac[thisswitch] = sadevice_links[1:]
            # mylog(OMDLOGLEVEL, [f'[{pluginName}]adding switch details: "{sadevice_details}"'])
            # mylog(OMDLOGLEVEL, [f'[{pluginName}]links are: "{sadevice_links}"'])
            # mylog(OMDLOGLEVEL, [f'[{pluginName}]linksbymac are: "{sadevices_linksbymac[thisswitch]}"'])
        elif sadevice_data[dTYPE] == "switch":
            sadevice_type = "Switch"
            # sadevice_details=callomada(['switch', thisswitch])
            sadevice_details = switch_details[thisswitch]
            if sadevice_details == "":
                sadevice_links = [thisswitch]
            else:
                sadevice_links = extract_mac_addresses(sadevice_details)
            sadevices_linksbymac[thisswitch] = sadevice_links[1:]
            # recovering the list of switches connected to sadevice switch and on which port...
            # switchdump = callomada(['-t','myomada','switch','-d',thisswitch])
            switchdump = switch_dumps[thisswitch]
            mylog(OMDLOGLEVEL, [f"[{pluginName}] switchdump: {switchdump}"])
            port_byswitchmac_byclientmac[thisswitch] = {}
            for link in sadevices_linksbymac[thisswitch]:
                port_pattern = (
                    r"(?:{[^}]*\"port\"\: )([0-9]+)(?=[^}]*" + re.escape(link) + r")"
                )
                myport = re.findall(port_pattern, switchdump, re.DOTALL)
                # mylog(OMDLOGLEVEL, [f'[{pluginName}] switchdump: link={link} myport:{myport}'])
                port_byswitchmac_byclientmac[thisswitch][link] = (
                    myport[0] if myport else ""
                )
            # mylog(OMDLOGLEVEL, [f'[{pluginName}]links are: "{sadevice_links}"'])
            # mylog(OMDLOGLEVEL, [f'[{pluginName}]linksbymac are: "{sadevices_linksbymac[thisswitch]}"'])
            # mylog(OMDLOGLEVEL, [f'[{pluginName}]ports of each links  are: "{port_byswitchmac_byclientmac[thisswitch]}"'])
            # mylog(OMDLOGLEVEL, [f'[{pluginName}]adding switch details: "{sadevice_details}"'])
        else:
            sadevice_type = "null"
            sadevice_details = "null"
        device_data_bymac[thisswitch] = [
            thisswitch,
            sadevice_data[dIP],
            sadevice_data[dNAME],
            "null",
            "null",
            sadevice_type,
        ]
        device_data_mac_byip[sadevice_data[dIP]] = thisswitch
        foo = [thisswitch, sadevice_data[1], sadevice_data[4], "null", "null"]
        mylog(OMDLOGLEVEL, [f'[{pluginName}]adding switch: "{foo}"'])

    #    sadevices_macbymac[thisswitch] = thisswitch

    mylog(OMDLOGLEVEL, [f'[{pluginName}] switch_macbyname: "{sadevices_macbyname}"'])
    mylog(OMDLOGLEVEL, [f'[{pluginName}] switches: "{device_data_bymac}"'])

    # do some processing, call exteranl APIs, and return a device list
    #  ...
    # sample omada clients input format:
    #  0 MAC, 1 IP, 2 Name, 3 switch/AP, 4 port/SSID,
    # 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-6F', '192.168.0.217', '1A-2B-3C-4D-5E-6F', 'myssid_name2', '(office_Access_point)']"
    # 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-01', '192.168.0.153', 'frontyard_ESP_29E753', 'pantry12', '(48)']"
    # 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-02', '192.168.0.1', 'bastion', 'office24', '(23)']"
    # 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-03', '192.168.0.226', 'brick', 'myssid_name3', '(office_Access_point)']"

    # sample target output:
    #  0 MAC, 1 IP, 2 Name, 3 MAC of switch/AP, 4 port/SSID, 5 TYPE
    # 17:27:10 [<unique_prefix>] token: "['1A-2B-3C-4D-5E-6F', '192.168.0.217', 'brick', 'office_Access_point','myssid_name2', , 'Switch']"

    odevices = omada_clients_output.splitlines()
    mylog(
        OMDLOGLEVEL, [f'[{pluginName}] omada_clients_outputs rows: "{len(odevices)}"']
    )
    omada_clients_to_rename = []

    for odevice in odevices:
        odevice_data = odevice.split()
        odevice_data_reordered = [MAC, IP, NAME, SWITCH_AP, PORT_SSID, TYPE]
        odevice_data_reordered[MAC] = odevice_data[cMAC]
        odevice_data_reordered[IP] = odevice_data[cIP]
        real_naxname = device_handler.getValueWithMac(
            "devName", ieee2ietf_mac_formater(odevice_data[cMAC])
        )

        #
        # if the name stored in Nax for a device is empty or the MAC addres or has some parenthhesis or is the same as in omada
        # don't bother updating omada's name at all.
        #

        naxname = real_naxname
        if real_naxname is not None:
            if "(" in real_naxname:
                # removing parenthesis and domains from the name
                naxname = real_naxname.split("(")[0]
            if naxname is not None and "." in naxname:
                naxname = naxname.split(".")[0]
        if naxname in (None, "null", ""):
            naxname = (
                odevice_data[cNAME] if odevice_data[cNAME] != "" else odevice_data[cMAC]
            )
        naxname = naxname.strip()
        mylog("debug", [f"[{pluginName}] TEST name from MAC: {naxname}"])
        if odevice_data[cNAME] in ("null", ""):
            mylog(
                "verbose",
                [
                    f'[{pluginName}] updating omada server because odevice_data is: {odevice_data[cNAME]} and naxname is: "{naxname}"'
                ],
            )
            omada_clients_to_rename.append(
                ["set-client-name", odevice_data[cMAC], naxname]
            )
            # callomada(['set-client-name', odevice_data[cMAC], naxname])
            odevice_data_reordered[NAME] = naxname
        elif odevice_data[cNAME] == odevice_data[cMAC] and ieee2ietf_mac_formater(
            naxname
        ) != ieee2ietf_mac_formater(odevice_data[cNAME]):
            mylog(
                "verbose",
                [
                    f'[{pluginName}] updating omada server because odevice_data is: "{odevice_data[cNAME]} and naxname is: "{naxname}"'
                ],
            )
            omada_clients_to_rename.append(
                ["set-client-name", odevice_data[cMAC], naxname]
            )
            # callomada(['set-client-name', odevice_data[cMAC], naxname])
            odevice_data_reordered[NAME] = naxname
        else:
            if omada_force_overwrite and naxname != odevice_data[cNAME]:
                mylog(
                    "verbose",
                    [
                        f'[{pluginName}] updating omada server because odevice_data is: "{odevice_data[cNAME]} and naxname is: "{naxname}"'
                    ],
                )
                omada_clients_to_rename.append(
                    ["set-client-name", odevice_data[cMAC], naxname]
                )
                # callomada(['set-client-name', odevice_data[cMAC], naxname])
            odevice_data_reordered[NAME] = naxname

        mightbeport = odevice_data[cPORT_SSID].lstrip("(")
        mightbeport = mightbeport.rstrip(")")
        if mightbeport.isdigit():
            odevice_data_reordered[SWITCH_AP] = odevice_data[cSWITCH_AP]
            odevice_data_reordered[PORT_SSID] = mightbeport
        else:
            odevice_data_reordered[SWITCH_AP] = mightbeport
            odevice_data_reordered[PORT_SSID] = odevice_data[cSWITCH_AP]

        # replacing the switch name with its MAC...
        try:
            mightbemac = sadevices_macbyname[odevice_data_reordered[SWITCH_AP]]
            odevice_data_reordered[SWITCH_AP] = mightbemac
        except KeyError:
            mylog(
                OMDLOGLEVEL,
                [
                    f'[{pluginName}] could not find the mac adddress for: "{odevice_data_reordered[SWITCH_AP]}"'
                ],
            )
        # adding the type
        odevice_data_reordered[TYPE] = "null"
        device_data_bymac[odevice_data_reordered[MAC]] = odevice_data_reordered
        device_data_mac_byip[odevice_data_reordered[IP]] = odevice_data_reordered[MAC]
        mylog(OMDLOGLEVEL, [f'[{pluginName}] tokens: "{odevice_data}"'])
        mylog(
            OMDLOGLEVEL,
            [f'[{pluginName}] tokens_reordered: "{odevice_data_reordered}"'],
        )
    # RENAMING
    # for omada_client_to_rename in omada_clients_to_rename:
    #   mylog('verbose', [f'[{pluginName}] calling omada: "{omada_client_to_rename}"'])
    # callomada(omada_client_to_rename)

    # populating the uplinks nodes of the omada switches and access points manually
    # since OMADA SDN makes is unreliable if the gateway is not their own tplink hardware...
    #
    with multiprocessing.Pool(processes=PARALLELISM) as mypool2:
        oresults = mypool2.map(callomada, omada_clients_to_rename)
    mylog(OMDLOGLEVEL, [f'[{pluginName}] results are: "{oresults}"'])

    # step1 let's find the the default router
    #
    default_router_ip = find_default_gateway_ip()
    default_router_mac = ietf2ieee_mac_formater(get_mac_from_IP(default_router_ip))
    device_data_bymac[default_router_mac][TYPE] = "Firewall"
    # step2 let's find the first switch and set the default router parent to internet
    first_switch = device_data_bymac[default_router_mac][SWITCH_AP]
    device_data_bymac[default_router_mac][SWITCH_AP] = "internet"
    # step3 let's set the switch connected to the default gateway uplink to the default gateway and hardcode port to 1 for now:
    # device_data_bymac[first_switch][SWITCH_AP]=default_router_mac
    # device_data_bymac[first_switch][SWITCH_AP][PORT_SSID] = '1'
    # step4, let's go recursively through switches other links to mark update their uplinks
    #  and pray it ends one day...
    #
    if len(sadevices) > 0:
        add_uplink(
            default_router_mac,
            first_switch,
            device_data_bymac,
            sadevices_linksbymac,
            port_byswitchmac_byclientmac,
        )
    return device_data_bymac.values()


if __name__ == "__main__":
    main()
