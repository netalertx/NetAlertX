# Workflow examples

Workflows in NetAlertX automate actions based on real-time events and conditions. Below are practical examples that demonstrate how to build automation using triggers, conditions, and actions.

## Example 1: Un-archive devices if detected online

This workflow automatically unarchives a device if it was previously archived but has now been detected as online.

### 📋 Use Case

Sometimes devices are manually archived (e.g., no longer expected on the network), but they reappear unexpectedly. This workflow reverses the archive status when such devices are detected during a scan.

### ⚙️ Workflow Configuration

```json
{
  "name": "Un-archive devices if detected online",
  "trigger": {
    "object_type": "Devices",
    "event_type": "update"
  },
  "conditions": [
    {
      "logic": "AND",
      "conditions": [
        {
          "field": "devIsArchived",
          "operator": "equals",
          "value": "1"
        },
        {
          "field": "devPresentLastScan",
          "operator": "equals",
          "value": "1"
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "update_field",
      "field": "devIsArchived",
      "value": "0"
    }
  ],
  "enabled": "Yes"
}
```

### 🔍 Explanation

* **Trigger**: Listens for updates to device records.
* **Conditions**:

  * `devIsArchived` is `1` (archived).
  * `devPresentLastScan` is `1` (device was detected in the latest scan).
* **Action**:

  * Updates the device to set `devIsArchived` to `0` (unarchived).

### ✅ Result

Whenever a previously archived device shows up during a network scan, it will be automatically unarchived — allowing it to reappear in your device lists and dashboards.

---

## Example 2: Assign Device to Network Node Based on IP

This workflow assigns newly added devices with IP addresses in the `192.168.1.*` range to a specific network node with MAC address `6c:6d:6d:6c:6c:6c`.

### 📋 Use Case

When new devices join your network, assigning them to the correct network node is important for accurate topology and grouping. This workflow ensures devices in a specific subnet are automatically linked to the intended node.

### ⚙️ Workflow Configuration

```json
{
  "name": "Assign Device to Network Node Based on IP",
  "trigger": {
    "object_type": "Devices",
    "event_type": "insert"
  },
  "conditions": [
    {
      "logic": "AND",
      "conditions": [
        {
          "field": "devLastIP",
          "operator": "contains",
          "value": "192.168.1."
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "update_field",
      "field": "devNetworkNode",
      "value": "6c:6d:6d:6c:6c:6c"
    }
  ],
  "enabled": "Yes"
}
```

### 🔍 Explanation

* **Trigger**: Activates when a new device is added.
* **Conditions**:

  * `devLastIP` contains `192.168.1.` (matches subnet).
* **Action**:

  * Sets `devNetworkNode` to the specified MAC address.

### ✅ Result

New devices with IPs in the `192.168.1.*` subnet are automatically assigned to the correct network node, streamlining device organization and reducing manual work.

---

## Example 3: Mark Device as Not New and Delete If from Google Vendor

This workflow automatically marks newly detected Google devices as not new and deletes them immediately.

### 📋 Use Case

You may want to automatically clear out newly detected Google devices (such as Chromecast or Google Home) if they’re not needed in your device database. This workflow handles that clean-up automatically.

### ⚙️ Workflow Configuration

```json
{
  "name": "Mark Device as Not New and Delete If from Google Vendor",
  "trigger": {
    "object_type": "Devices",
    "event_type": "update"
  },
  "conditions": [
    {
      "logic": "AND",
      "conditions": [
        {
          "field": "devVendor",
          "operator": "contains",
          "value": "Google"
        },
        {
          "field": "devIsNew",
          "operator": "equals",
          "value": "1"
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "update_field",
      "field": "devIsNew",
      "value": "0"
    },
    {
      "type": "delete_device"
    }
  ],
  "enabled": "Yes"
}
```

### 🔍 Explanation

* **Trigger**: Runs on device updates.
* **Conditions**:

  * `devVendor` contains `Google`.
  * `devIsNew` is `1` (device marked as new).
* **Actions**:

  1. Sets `devIsNew` to `0` (mark as not new).
  2. Deletes the device.

### ✅ Result

Any newly detected Google devices are cleaned up instantly — first marked as not new, then deleted — helping you avoid clutter in your device records.