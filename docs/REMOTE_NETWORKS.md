# Scanning Remote or Inaccessible Networks

By design, local network scanners such as `arp-scan` use ARP (Address Resolution Protocol) to map IP addresses to MAC addresses on the local network. Since ARP operates at Layer 2 (Data Link Layer), it typically works only within a single broadcast domain, usually limited to a single router or network segment.

> [!NOTE]
> Ping and `ARPSCAN` use different protocols so even if you can ping devices it doesn't mean `ARPSCAN` can detect them.

To scan multiple locally accessible network segments, add them as subnets according to the [subnets](./SUBNETS.md) documentation. If `ARPSCAN` is not suitable for your setup, read on.

## Complex Use Cases

The following network setups might make some devices undetectable with `ARPSCAN`. Check the specific setup to understand the cause and find potential workarounds to report on these devices.

### Wi-Fi Extenders

Wi-Fi extenders often **block or proxy Layer-2 broadcast traffic**, which can prevent network scanning tools like `arp-scan` from detecting devices behind the extender. This can happen **even when the extender uses the same SSID and the same IP subnet** as the main network.

Please note that being able to `ping` a device does **not** mean it is discoverable via `arp-scan`.

* `arp-scan` relies on **Layer 2 (ARP broadcast)**
* ICMP (`ping`) operates at **Layer 3 (routed traffic)**

That’s why devices behind extenders may respond to ping but remain undiscoverable via `arp-scan`.

> **Possible workaround**:
> If the extender uses a separate subnet, scan that subnet directly. Otherwise, use DHCP-based discovery plugins or router integration instead of ARP. See the **Other Workarounds** section below for more details.

### VPNs

ARP operates at Layer 2 (Data Link Layer) and works only within a local area network (LAN). VPNs, which operate at Layer 3 (Network Layer), route traffic between networks, preventing ARP requests from discovering devices outside the local network.

VPNs use virtual interfaces (e.g., `tun0`, `tap0`) to encapsulate traffic, bypassing ARP-based discovery. Additionally, many VPNs use NAT, which masks individual devices behind a shared IP address.

> **Possible workaround**: Configure the VPN to bridge networks instead of routing to enable ARP, though this depends on the VPN setup and security requirements.

# Other Workarounds

The following workarounds should work for most complex network setups.

## Supplementing Plugins

You can use supplementary plugins that employ alternate methods. Protocols used by the `SNMPDSC` or `DHCPLSS` plugins are widely supported on different routers and can be effective as workarounds. Check the [plugins list](./PLUGINS.md) to find a plugin that works with your router and network setup.

## Multiple NetAlertX Instances

If you have servers in different networks, you can set up separate NetAlertX instances on those subnets and synchronize the results into one instance using the [`SYNC` plugin](https://github.com/jokob-sk/NetAlertX/tree/main/front/plugins/sync).

## Manual Entry

If you don't need to discover new devices and only need to report on their status (`online`, `offline`, `down`), you can manually enter devices and check their status using the [`ICMP` plugin](https://github.com/jokob-sk/NetAlertX/blob/main/front/plugins/icmp_scan/), which uses the `ping` command internally.

For more information on how to add devices manually (or dummy devices), refer to the [Device Management](./DEVICE_MANAGEMENT.md) documentation.

To create truly dummy devices, you can use a loopback IP address (e.g., `0.0.0.0` or `127.0.0.1`) or the `Force Status` field so they appear online.

## NMAP and Fake MAC Addresses

Scanning remote networks with NMAP is possible (via the `NMAPDEV` plugin), but since it cannot retrieve the MAC address, you need to enable the `NMAPDEV_FAKE_MAC` setting. This will generate a fake MAC address based on the IP address, allowing you to track devices. However, this can lead to inconsistencies, especially if the IP address changes or a previously logged device is rediscovered. If this setting is disabled, only the IP address will be discovered, and devices with missing MAC addresses will be skipped.

Check the [NMAPDEV plugin](https://github.com/jokob-sk/NetAlertX/tree/main/front/plugins/nmap_dev_scan) for details
