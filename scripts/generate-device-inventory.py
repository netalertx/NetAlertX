#!/usr/bin/env python3
"""
Generate a synthetic NetAlertX device CSV using the same column order as the shipped
sample inventory. This is intended for test data and keeps a simple parent/child
topology: one router, a few switches, a few APs, then leaf nodes. MACs, IPs, names,
and timestamps are random but reproducible with --seed.
"""

import argparse
import csv
import datetime as dt
import random
import sys
import uuid
from pathlib import Path
import ipaddress

# Default header copied from the sample inventory CSV to preserve column order.
DEFAULT_HEADER = [
    "devMac",
    "devName",
    "devOwner",
    "devType",
    "devVendor",
    "devFavorite",
    "devGroup",
    "devComments",
    "devFirstConnection",
    "devLastConnection",
    "devLastIP",
    "devStaticIP",
    "devScan",
    "devLogEvents",
    "devAlertEvents",
    "devAlertDown",
    "devSkipRepeated",
    "devLastNotification",
    "devPresentLastScan",
    "devIsNew",
    "devLocation",
    "devIsArchived",
    "devParentPort",
    "devParentMAC",
    "devIcon",
    "devGUID",
    "devSyncHubNode",
    "devSite",
    "devSSID",
    "devSourcePlugin",
    "devCustomProps",
    "devFQDN",
    "devParentRelType",
    "devReqNicsOnline",
]

ICON_DEFAULT = "PGkgY2xhc3M9J2ZhIGZhLWFuY2hvci1ub2RlJz48L2k+"  # simple placeholder icon

VENDORS = [
    "Raspberry Pi Trading Ltd",
    "Dell Inc.",
    "Intel Corporate",
    "Espressif Inc.",
    "Micro-Star INTL CO., LTD.",
    "Google, Inc.",
    "Hewlett Packard",
    "ASUSTek COMPUTER INC.",
    "TP-LINK TECHNOLOGIES CO.,LTD.",
]

LOCATIONS = [
    "Com Closet",
    "Office",
    "Garage",
    "Living Room",
    "Master Bedroom",
    "Kitchen",
    "Attic",
    "Outside",
]

DEVICE_TYPES = [
    "Server",
    "Laptop",
    "NAS",
    "Phone",
    "TV Decoder",
    "Printer",
    "IoT",
    "Camera",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a synthetic device CSV for NetAlertX")
    parser.add_argument("--output", "-o", type=Path, default=Path("generated-devices.csv"), help="Output CSV path")
    parser.add_argument("--seed", type=int, default=None, help="Seed for reproducible output")
    parser.add_argument("--devices", type=int, default=40, help="Number of leaf nodes to generate")
    parser.add_argument("--switches", type=int, default=2, help="Number of switches under the router")
    parser.add_argument("--aps", type=int, default=3, help="Number of APs under switches")
    parser.add_argument("--site", default="default", help="Site name")
    parser.add_argument("--ssid", default="lab", help="SSID placeholder")
    parser.add_argument("--owner", default="Test Lab", help="Owner name for devices")
    parser.add_argument(
        "--network",
        default="192.168.50.0/22",
        help="IPv4 network to draw addresses from (must have enough hosts for requested devices)",
    )
    parser.add_argument(
        "--template",
        type=Path,
        help="Optional CSV to pull header from; defaults to the sample inventory layout",
    )
    return parser.parse_args(argv)


def load_header(template_path: Path | None) -> list[str]:
    if not template_path:
        return DEFAULT_HEADER
    try:
        with template_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            return header if header else DEFAULT_HEADER
    except FileNotFoundError:
        return DEFAULT_HEADER


def random_mac(existing: set[str]) -> str:
    while True:
        mac = ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))
        if mac not in existing:
            existing.add(mac)
            return mac


def prepare_ip_pool(network_cidr: str) -> list[str]:
    network = ipaddress.ip_network(network_cidr, strict=False)
    hosts = list(network.hosts())
    if not hosts:
        raise ValueError(f"Network {network} has no usable hosts")
    return [str(host) for host in hosts]


def random_time(now: dt.datetime) -> str:
    delta_days = random.randint(0, 180)
    delta_seconds = random.randint(0, 86400)
    ts = now - dt.timedelta(days=delta_days, seconds=delta_seconds)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def build_row(
    name: str,
    dev_type: str,
    vendor: str,
    mac: str,
    parent_mac: str,
    ip: str,
    header: list[str],
    owner: str,
    site: str,
    ssid: str,
    now: dt.datetime,
) -> dict[str, str]:
    comments = "Synthetic device generated for testing."
    t1 = random_time(now)
    t2 = random_time(now)
    first_seen, last_seen = (t1, t2) if t1 <= t2 else (t2, t1)
    fqdn = f"{name.lower().replace(' ', '-')}.{site}" if name else ""

    # Minimal fields set; missing ones default to empty string for CSV compatibility.
    base = {
        "devMac": mac,
        "devName": name,
        "devOwner": owner,
        "devType": dev_type,
        "devVendor": vendor,
        "devFavorite": "0",
        "devGroup": "Always on" if dev_type in {"Router", "Switch", "AP", "Firewall"} else "",
        "devComments": comments,
        "devFirstConnection": first_seen,
        "devLastConnection": last_seen,
        "devLastIP": ip,
        "devStaticIP": "1",
        "devScan": "1",
        "devLogEvents": "1",
        "devAlertEvents": "1",
        "devAlertDown": "0",
        "devSkipRepeated": "0",
        "devLastNotification": "",
        "devPresentLastScan": "0",
        "devIsNew": "0",
        "devLocation": random.choice(LOCATIONS),
        "devIsArchived": "0",
        "devParentPort": "0",
        "devParentMAC": parent_mac,
        "devIcon": ICON_DEFAULT,
        "devGUID": str(uuid.uuid4()),
        "devSyncHubNode": "",
        "devSite": site,
        "devSSID": ssid,
        "devSourcePlugin": "GENERATOR",
        "devCustomProps": "",
        "devFQDN": fqdn,
        "devParentRelType": "None",
        "devReqNicsOnline": "0",
    }

    # Ensure all header columns exist; extra columns are ignored by writer.
    return {key: base.get(key, "") for key in header}


def generate_rows(args: argparse.Namespace, header: list[str]) -> list[dict[str, str]]:
    now = dt.datetime.now(dt.timezone.utc)
    macs: set[str] = set()
    ip_pool = prepare_ip_pool(args.network)

    rows: list[dict[str, str]] = []

    # Include one internet root device that anchors the tree; it does not consume an IP.
    required_devices = 1 + args.switches + args.aps + args.devices
    if required_devices > len(ip_pool):
        raise ValueError(
            f"Not enough IPs in {args.network}: need {required_devices}, available {len(ip_pool)}. "
            "Use --network with a larger range (e.g., 192.168.50.0/21)."
        )

    def take_ip() -> str:
        choice = random.choice(ip_pool)
        ip_pool.remove(choice)
        return choice

    # Root "internet" device (no parent, no IP) so the topology has a defined root.
    root_row = build_row(
        name="internet",
        dev_type="Gateway",
        vendor="NetAlertX",
        mac="internet",
        parent_mac="",
        ip="",
        header=header,
        owner=args.owner,
        site=args.site,
        ssid=args.ssid,
        now=now,
    )
    root_row["devComments"] = "Synthetic root device representing the internet."
    root_row["devParentRelType"] = "Root"
    root_row["devStaticIP"] = "0"
    root_row["devScan"] = "0"
    root_row["devAlertEvents"] = "0"
    root_row["devAlertDown"] = "0"
    root_row["devLogEvents"] = "0"
    root_row["devPresentLastScan"] = "0"
    rows.append(root_row)

    router_mac = random_mac(macs)
    router_ip = take_ip()
    rows.append(
        build_row(
            name="Router-1",
            dev_type="Firewall",
            vendor=random.choice(VENDORS),
            mac=router_mac,
            parent_mac="internet",
            ip=router_ip,
            header=header,
            owner=args.owner,
            site=args.site,
            ssid=args.ssid,
            now=now,
        )
    )

    switch_macs: list[str] = []
    for idx in range(1, args.switches + 1):
        mac = random_mac(macs)
        ip = take_ip()
        switch_macs.append(mac)
        rows.append(
            build_row(
                name=f"Switch-{idx}",
                dev_type="Switch",
                vendor=random.choice(VENDORS),
                mac=mac,
                parent_mac=router_mac,
                ip=ip,
                header=header,
                owner=args.owner,
                site=args.site,
                ssid=args.ssid,
                now=now,
            )
        )

    ap_macs: list[str] = []
    for idx in range(1, args.aps + 1):
        mac = random_mac(macs)
        ip = take_ip()
        parent_mac = random.choice(switch_macs) if switch_macs else router_mac
        ap_macs.append(mac)
        rows.append(
            build_row(
                name=f"AP-{idx}",
                dev_type="AP",
                vendor=random.choice(VENDORS),
                mac=mac,
                parent_mac=parent_mac,
                ip=ip,
                header=header,
                owner=args.owner,
                site=args.site,
                ssid=args.ssid,
                now=now,
            )
        )

    for idx in range(1, args.devices + 1):
        mac = random_mac(macs)
        ip = take_ip()
        parent_pool = ap_macs or switch_macs or [router_mac]
        parent_mac = random.choice(parent_pool)
        dev_type = random.choice(DEVICE_TYPES)
        name_prefix = "Node" if dev_type == "Server" else "Node"
        name = f"{name_prefix}-{idx:02d}"
        rows.append(
            build_row(
                name=name,
                dev_type=dev_type,
                vendor=random.choice(VENDORS),
                mac=mac,
                parent_mac=parent_mac,
                ip=ip,
                header=header,
                owner=args.owner,
                site=args.site,
                ssid=args.ssid,
                now=now,
            )
        )

    return rows


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.seed is not None:
        random.seed(args.seed)

    header = load_header(args.template)
    rows = generate_rows(args, header)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} devices to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
