## ADVISORY: Best Practices for Monitoring Multiple Networks with NetAlertX

### 1. Define Monitoring Scope & Architecture

Effective multi-network monitoring starts with understanding how NetAlertX "sees" your traffic.

* **A. Understand Network Accessibility:** Local ARP-based scanning (**ARPSCAN**) only discovers devices on directly accessible subnets due to Layer 2 limitations. It cannot traverse VPNs or routed borders without specific configuration.
* **B. Plan Subnet & Scan Interfaces:** Explicitly configure each accessible segment in `SCAN_SUBNETS` with the corresponding interfaces.
* **C. Remote & Inaccessible Networks:** For networks unreachable via ARP, use these strategies:
* **Alternate Plugins:** Supplement discovery with [SNMPDSC](SNMPDSC) or [DHCP lease imports](https://docs.netalertx.com/PLUGINS/?h=DHCPLSS#available-plugins).
* **Centralized Multi-Tenant Management using Sync Nodes:** Run secondary NetAlertX instances on isolated networks and aggregate data using the **SYNC plugin**.
* **Manual Entry:** For static assets where only ICMP (ping) status is needed.

> [!TIP]
> Explore the [remote networks](./REMOTE_NETWORKS.md) documentation for more details on how to set up the approaches menationed above.

---

### 2. Automating IT Asset Inventory with Workflows

[Workflows](./WORKFLOWS.md) are the "engine" of NetAlertX, reducing manual overhead as your device list grows.

* **A. Logical Ownership & VLAN Tagging:** Create a workflow triggered on **Device Creation** to:
1. Inspect the IP/Subnet.
2. Set `devVlan` or `devOwner` custom fields automatically.


* **B. Auto-Grouping:** Use conditional logic to categorize devices.
* *Example:* If `devLastIP == 10.10.20.*`, then `Set devLocation = "BranchOffice"`.

```json
{
  "name": "Assign Location - BranchOffice",
  "trigger": {
    "object_type": "Devices",
    "event_type": "update"
  },
  "conditions": [
    {
      "logic": "AND",
      "conditions": [
        {
          "field": "devLastIP",
          "operator": "contains",
          "value": "10.10.20."
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "update_field",
      "field": "devLocation",
      "value": "BranchOffice"
    }
  ]
}
```


* **C. Sync Node Tracking:** When using multiple instances, ensure all synchub nodes have a descriptive `SYNC_node_name` name to distinguish between sites.

> [!TIP]
> Always test new workflows in a "Staging" instance. A misconfigured workflow can trigger thousands of unintended updates across your database.

---

### 3. Notification Strategy: Low Noise, High Signal

A multi-network environment can generate significant "alert fatigue." Use a layered filtering approach.

| Level | Strategy | Recommended Action |
| --- | --- | --- |
| **Device** | Silence Flapping | Use "Skip repeated notifications" for unstable IoT devices. |
| **Plugin** | Tune Watchers | Only enable `_WATCH` on reliable plugins (e.g., ICMP/SNMP). |
| **Global** | Filter Sections | Limit `NTFPRCS_INCLUDED_SECTIONS` to `new_devices` and `down_devices`. |


> [!TIP]
> **Ignore Rules:** Maintain strict **Ignored MAC** (`NEWDEV_ignored_MACs`) and **Ignored IP** (`NEWDEV_ignored_IPs`) lists for guest networks or broadcast scanners to keep your logs clean.

---

### 4. UI Filters for Multi-Network Clarity

Don't let a massive device list overwhelm you. Use the [Multi-edit features](./DEVICES_BULK_EDITING.md) to categorize devices and create focused views:

* **By Zone:** Filter by "Location", "Site" or "Sync Node" you et up in Section 2.
* **By Criticality:** Use custom the device Type field to separate "Core Infrastructure" from "Ephemeral Clients."
* **By Status:** Use predefined views specifically for "Devices currently Down" to act as a Network Operations Center (NOC) dashboard.

> [!TIP]
> If you are providing services as a Managed Service Provider (MSP) customize your default UI to be exactly how you need it, by hiding parts of the UI that you are not interested in, or by configuring a auto-refreshed screen monitoring your most important clients. See the [Eyes on glass](./ADVISORY_EYES_ON_GLASS.md) advisory for more details.

---

### 5. Operational Stability & Sync Health

* **Health Checks:** Regularly monitor the [Logs](https://docs.netalertx.com/LOGGING/?h=logs) to ensure remote nodes are reporting in.
* **Backups:** Use the **CSV Devices Backup** plugin. Standardize your workflow templates and [back up](./BACKUPS.md) you `/config` folders so that if a node fails, you can redeploy it with the same logic instantly.


### 6. Optimize Performance

As your environment grows, tuning the underlying engine is vital to maintain a snappy UI and reliable discovery cycles.

* **Plugin Scheduling:** Avoid "Scan Storms" by staggering plugin execution. Running intensive tasks like `NMAP` or `MASS_DNS` simultaneously can spike CPU and cause database locks.
* **Database Health:** Large-scale monitoring generates massive event logs. Use the **[DBCLNP (Database Cleanup)](https://www.google.com/search?q=https://docs.netalertx.com/PLUGINS/%23dbclnp)** plugin to prune old records and keep the SQLite database performant.
* **Resource Management:** For high-device counts, consider increasing the memory limit for the container and utilizing `tmpfs` for temporary files to reduce SD card/disk I/O bottlenecks.

> [!IMPORTANT]
> For a deep dive into hardware requirements, database vacuuming, and specific environment variables for high-load instances, refer to the full **[Performance Optimization Guide](https://docs.netalertx.com/PERFORMANCE/)**.

---

### Summary Checklist

* [ ] **Discovery:** Are all subnets explicitly defined?
* [ ] **Automation:** Do new devices get auto-assigned to a VLAN/Owner?
* [ ] **Noise Control:** Are transient "Down" alerts delayed via `NTFPRCS_alert_down_time`?
* [ ] **Remote Sites:** Is the SYNC plugin authenticated and heartbeat-active?
