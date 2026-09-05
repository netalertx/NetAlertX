# Custom Properties for Devices

![Custom Properties](./img/CUSTOM_PROPERTIES/Device_Custom_Properties.png)

## Overview

This functionality allows you to define **custom properties** for devices, which can store and display additional information on the device listing page. By marking properties as "Show", you can enhance the user interface with quick actions, notes, or external links.

### Key Features:
- **Customizable Properties**: Define specific properties for each device.
- **Visibility Control**: Choose which properties are displayed on the device listing page.
- **Interactive Elements**: Include actions like links, modals, and device management directly in the interface.

---


## Usage on the Device Listing Page

![Custom Properties](./img/CUSTOM_PROPERTIES/Device_Custom_Properties_vid.gif)

Visible properties (`CUSTPROP_show: true`) are displayed as interactive icons in the device listing. Each icon can perform one of the following actions based on the `CUSTPROP_type`:

1. **Modals (e.g., Show Notes)**:

   - Displays detailed information in a popup modal.
   - Example: Firmware version details.

2. **Links**:

   - Redirect to an external or internal URL.
   - Example: Open a device's documentation or external site.

3. **Device Actions**:

   - Manage devices with actions like delete.
   - Example: Quickly remove a device from the network.

4. **Plugins (Experimental 🧪)**:

   - Manually trigger an on-demand run of a plugin, regardless of its configured `RUN` schedule.
   - Example: Add a button to re-run a scan-type plugin like `NMAPDEV` on demand.
   - **Note**: The plugin runs with whatever settings/params it already has configured - it is not passed any device-specific or ad-hoc arguments. Some plugins require settings (credentials, target host, subnet, etc.) to be configured before they'll run properly; triggering an unconfigured plugin this way may fail or do nothing useful.

---

## Example Use Cases

1. **Device Documentation Link**:

   - Add a custom property with `CUSTPROP_type` set to `link` or `link_new_tab` to allow quick navigation to the external documentation of the device.

2. **Firmware Details**:

   - Use `CUSTPROP_type: show_notes` to display firmware versions or upgrade instructions in a modal.

3. **Device Removal**:

   - Enable device removal functionality using `CUSTPROP_type: delete_dev`.

4. **Run a Plugin On Demand (Experimental 🧪)**:

   - Use `CUSTPROP_type: run_plugin` with `CUSTPROP_args` set to the target plugin's unique prefix (e.g. `NMAPDEV`) to add a button that triggers that plugin immediately. Make sure the plugin's own settings (credentials, target host, subnet, etc.) are already configured, since none are passed in via this action.

---

## Defining Custom Properties

Custom properties are structured as a list of objects, where each property includes the following fields:

| Field             | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `CUSTPROP_icon`    | The icon (Base64-encoded HTML) displayed for the property.                 |
| `CUSTPROP_type`    | The action type (e.g., `show_notes`, `link`, `delete_dev`).                |
| `CUSTPROP_name`    | A short name or title for the property. Supports `{{fieldName}}` wildcards. |
| `CUSTPROP_args`    | Arguments for the action (e.g., URL or modal text). Supports `{{fieldName}}` wildcards. |
| `CUSTPROP_notes`   | Additional notes or details displayed when applicable.                    |
| `CUSTPROP_show`    | A boolean to control visibility (`true` to show on the listing page).      |

---

## Wildcards in `CUSTPROP_name` / `CUSTPROP_args`

`CUSTPROP_name` and `CUSTPROP_args` are resolved per-device before rendering, so you can reference any of that device's own fields with `{{fieldName}}` - field names are matched case-insensitively, so `{{devLastIp}}` and `{{devLastIP}}` are equivalent. If a field name doesn't exist, the placeholder is left as-is (e.g. `{{devTypo}}` stays visible) rather than silently disappearing, to make a typo obvious while you're setting one up.

This is what makes a single `link`/`link_new_tab` custom property work across every device rather than one URL per device - e.g. to jump to a device's traffic log in an AdGuard Home instance, filtered to that device's IP:

```
CUSTPROP_type: link_new_tab
CUSTPROP_args: http://my_adguard_url/#logs?search={{devLastIP}}
```

Because this is set once (either directly on a device, or as a default applied to every new device via the `NEWDEV_devCustomProps` setting), it applies across your whole device list, not just one device at a time.

Commonly useful fields: `devMac`, `devLastIP`, `devName`, `devVendor`, `devType`, `devGUID`.

---

## Available Action Types

- **Show Notes**: Displays a modal with a title and additional notes.
  - **Example**: Show firmware details or custom messages.
- **Link**: Redirects to a specified URL in the current browser tab. (**Arguments** Needs to contain the full URL.)
- **Link (New Tab)**: Opens a specified URL in a new browser tab. (**Arguments** Needs to contain the full URL.)
- **Delete Device**: Deletes the device using its MAC address.
- **Run Plugin (Experimental 🧪)**: Triggers an on-demand run of the plugin named in **Arguments** (its unique prefix, e.g. `NMAPDEV`), regardless of that plugin's configured `RUN` schedule.


---

## Notes

- **Plugin Functionality (Experimental 🧪)**: `run_plugin` requires `CUSTPROP_args` to exactly match an enabled plugin's unique prefix (as listed in the `LOADED_PLUGINS` setting); an unrecognized or disabled prefix is rejected by the backend. It simply re-runs the plugin with its existing configuration - some plugins need required settings/params (e.g. credentials, target host, subnet) filled in first, or the run will fail or silently do nothing. Marked experimental until this is more clearly surfaced in the UI.
- **Custom Icons (Experimental 🧪)**: Use Base64-encoded HTML to provide custom icons for each property. You can add your icons in Setttings via the `CUSTPROP_icon` settings
- **Visibility Control**: Only properties with `CUSTPROP_show: true` will appear on the listing page.

This feature provides a flexible way to enhance device management and display with interactive elements tailored to your needs.
