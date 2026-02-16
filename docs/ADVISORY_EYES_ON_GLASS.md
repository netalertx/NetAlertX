### Build an MSP Wallboard for Network Monitoring

For Managed Service Providers (MSPs) and Network Operations Centers (NOC), "Eyes on Glass" monitoring requires a UI that is both self-healing (auto-refreshing) and focused only on critical data. By leveraging the **UI Settings Plugin**, you can transform NetAlertX from a management tool into a dedicated live monitor.

![filters](./img/ADVISORIES/filters.png)

---

### 1. Configure Auto-Refresh for Live Monitoring

Static dashboards are the enemy of real-time response. NetAlertX allows you to force the UI to pull fresh data without manual page reloads.

* **Setting:** Locate the `UI_REFRESH` (or similar "Auto-refresh UI") setting within the **UI Settings plugin**.
* **Optimal Interval:** Set this between **60 to 120 seconds**.
* *Note:* Refreshing too frequently (e.g., <30s) on large networks can lead to high browser and server CPU usage.

![ui_customization_settings](./img/ADVISORIES/ui_customization_settings.png)

### 2. Streamlining the Dashboard (MSP Mode)

An MSP's focus is on what is *broken*, not what is working. Hide the noise to increase reaction speed.

* **Hide Unnecessary Blocks:** Under UI Settings, disable dashboard blocks that don't provide immediate utility, such as **Online presence** or **Tiles**.
* **Hide virtual connections:** You can specify which relationships shoudl be hidden from the main view to remove any virtual devices that are not essential from your views.
* **Browser Full-Screen:** Use the built-in "Full Screen" toggle in the top bar to remove browser chrome (URL bars/tabs) for a cleaner "Wallboard" look.

### 3. Creating Custom NOC Views

Use the UI Filters in tandem with UI Settings to create custom views.

![NetAlertX NOC dashboard showing offline network devices for MSP monitoring](./img/ADVISORIES/down_devices.png)

| Feature | NOC/MSP Application |
| --- | --- |
| **Site-Specific Nodes** | Filter the view by a specific "Sync Node" or "Location" filter to monitor a single client site. |
| **Filter by Criticality** | Filter devices where `Group == "Infrastructure"` or `"Server"`. (depending on your predefined values) |
| **Predefined "Down" View** | Bookmark the URL with the `/devices.php#down` path to ensure the dashboard always loads into an "Alert Only" mode. |

### 4. Browser & Cache Stability

Because the UI is a web application, long-running sessions can occasionally experience cache drift.

* **Cache Refresh:** If you notice the "Show # Entries" resetting or icons failing to load after days of uptime, use the **Reload** icon in the application header (not the browser refresh) to clear the internal app cache.
* **Dedicated Hardware:** For 24/7 monitoring, use a dedicated thin client or Raspberry Pi running in "Kiosk Mode" to prevent OS-level popups from obscuring the dashboard.

> [!TIP]
> [NetAlertX - Detailed Dashboard Guide](https://www.youtube.com/watch?v=umh1c_40HW8)
> This video provides a visual walkthrough of the NetAlertX dashboard features, including how to map and visualize devices which is crucial for setting up a clear "Eyes on Glass" monitoring environment.

### Summary Checklist

* [ ] **Automate Refresh:** Set `UI_REFRESH` to **60-120s** in UI Settings to ensure the dashboard stays current without manual intervention.
* [ ] **Filter for Criticality:** Bookmark the **`/devices.php#down`** view to instantly focus on offline assets rather than the entire inventory.
* [ ] **Remove UI Noise:** Use UI Settings to hide non-essential dashboard blocks (e.g., **Tiles** or remove **Virtual Connections** devices) to maximize screen real estate for alerts.
* [ ] **Segment by Site:** Use **Location** or **Sync Node** filters to create dedicated views for specific client networks or physical branches.
* [ ] **Ensure Stability:** Run on a dedicated "Kiosk" browser and use the internal **Reload icon** occasionally to maintain a clean application cache.
