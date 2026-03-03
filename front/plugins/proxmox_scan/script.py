import sys
import requests
import json
import os
import traceback

def debug_log(msg):
    with open("debug.log", "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")

def get_auth_headers(api_user, api_token):
    # Proxmox API Token format: USER@REALM!TOKENID=SECRET
    if not api_token or "=" not in api_token:
        raise Exception("API token must be in format USER@REALM!TOKENID=SECRET")
    user_token, secret = api_token.split("=", 1)
    return {
        "Authorization": f"PVEAPIToken={user_token}={secret}"
    }

def get_nodes(api_url, headers):
    url = f"{api_url}/api2/json/nodes"
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()["data"]

def get_vms(api_url, node, headers):
    url = f"{api_url}/api2/json/nodes/{node}/qemu"
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()["data"]

def get_cts(api_url, node, headers):
    url = f"{api_url}/api2/json/nodes/{node}/lxc"
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()["data"]

def get_vm_config(api_url, node, vmid, headers):
    url = f"{api_url}/api2/json/nodes/{node}/qemu/{vmid}/config"
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()["data"]

def get_ct_config(api_url, node, vmid, headers):
    url = f"{api_url}/api2/json/nodes/{node}/lxc/{vmid}/config"
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()["data"]

def get_node_network(api_url, node, headers):
    url = f"{api_url}/api2/json/nodes/{node}/network"
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()["data"]

def extract_mac_from_net0(net0):
    # Example: 'virtio=DE:AD:BE:EF:00:01,bridge=vmbr0,firewall=1' -> DE:AD:BE:EF:00:01
    if not net0:
        return ""
    parts = net0.split(",")
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() in ("virtio", "e1000", "net0", "net1", "net2", "net3"):
                return v.strip()
    return ""

def get_node_macs(networks):
    macs = []
    for iface in networks:
        # Look for 'altnames' with 'enx' (USB/Ethernet MAC)
        altnames = iface.get("altnames", "")
        if "enx" in altnames:
            # enx<mac> (hex, no colons)
            for name in altnames.split(" "):
                if name.startswith("enx") and len(name) == 15:
                    mac_hex = name[3:]
                    mac = ":".join([mac_hex[i:i+2] for i in range(0,12,2)]).upper()
                    macs.append(mac)
        # Fallback: try 'hwaddr'
        elif iface.get("hwaddr"):
            macs.append(iface["hwaddr"].upper())
    return macs

def main():
    try:
        # Read config from environment or stdin
        config = {}
        if os.environ.get("api_url"):
            config = {
                "api_url": os.environ.get("api_url"),
                "api_user": os.environ.get("api_user"),
                "api_token": os.environ.get("api_token"),
            }
        else:
            config = json.load(sys.stdin)
        api_url = config["api_url"].rstrip("/")
        api_user = config["api_user"]
        api_token = config["api_token"]
        headers = get_auth_headers(api_user, api_token)
        # Output header
        print("id|parent_id|type|name|mac|ip|desc|os|extra")
        nodes = get_nodes(api_url, headers)
        for node in nodes:
            node_id = f"node-{node['node']}"
            node_name = node["node"]
            # Get node MACs
            try:
                networks = get_node_network(api_url, node_name, headers)
                node_macs = get_node_macs(networks)
                node_mac = ",".join(node_macs)
            except Exception as e:
                debug_log(f"Node network error: {e}")
                node_mac = ""
            print(f"{node_id}||node|{node_name}|{node_mac}|||Proxmox Node|")
            # VMs
            vms = get_vms(api_url, node_name, headers)
            for vm in vms:
                vm_id = f"vm-{vm['vmid']}"
                vm_name = vm.get("name", f"VM-{vm['vmid']}")
                parent_id = node_id
                # Get VM config for MAC
                try:
                    config = get_vm_config(api_url, node_name, vm["vmid"], headers)
                    mac = extract_mac_from_net0(config.get("net0", ""))
                except Exception as e:
                    debug_log(f"VM config error: {e}")
                    mac = ""
                print(f"{vm_id}|{parent_id}|vm|{vm_name}|{mac}|||{config.get('ostype','')}|")
            # Containers
            cts = get_cts(api_url, node_name, headers)
            for ct in cts:
                ct_id = f"ct-{ct['vmid']}"
                ct_name = ct.get("name", f"CT-{ct['vmid']}")
                parent_id = node_id
                # Get CT config for MAC (not always present)
                try:
                    config = get_ct_config(api_url, node_name, ct["vmid"], headers)
                    mac = extract_mac_from_net0(config.get("net0", ""))
                except Exception as e:
                    debug_log(f"CT config error: {e}")
                    mac = ""
                print(f"{ct_id}|{parent_id}|ct|{ct_name}|{mac}|||{config.get('ostype','')}|")
    except Exception as e:
        debug_log(traceback.format_exc())
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
