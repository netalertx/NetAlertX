// network-init.js
// Main initialization and data loading logic for network topology

// Global variables needed by other modules
var networkDeviceTypes = "";
var showArchived = false;
var showOffline = false;

/**
 * Initialize network topology on page load
 * Fetches all devices and sets up the tree visualization
 */
function initNetworkTopology() {
  networkDeviceTypes = getSetting("NETWORK_DEVICE_TYPES").replace("[", "").replace("]", "");
  showArchived = getCache(CACHE_KEYS.SHOW_ARCHIVED) === "true";
  showOffline = getCache(CACHE_KEYS.SHOW_OFFLINE) === "true";

  console.log('showArchived:', showArchived);
  console.log('showOffline:', showOffline);

  // Always get all devices
  const rawSql = `
    SELECT *,
      LOWER(devMac) AS devMac,
      LOWER(devParentMAC) AS devParentMAC,
      CASE
        WHEN devPresentLastScan = 1 THEN 'On-line'
        WHEN devIsSleeping = 1 THEN 'Sleeping'
        WHEN devAlertDown != 0 AND devPresentLastScan = 0 THEN 'Down'
        ELSE 'Off-line'
      END AS devStatus,
      CASE
        WHEN devType IN (${networkDeviceTypes}) THEN 1
        ELSE 0
      END AS devIsNetworkNodeDynamic
    FROM DevicesView a
  `;


  const { token: apiToken, apiBase, authHeader } = getAuthContext();

  // Verify token is available before making API call
  if (!apiToken || apiToken.trim() === '') {
    console.error("API_TOKEN not available. Settings may not be loaded yet. Retrying in 500ms...");
    // Retry after a short delay to allow settings to load
    setTimeout(() => {
      initNetworkTopology();
    }, 500);
    return;
  }

  const url = `${apiBase}/dbquery/read`;

  $.ajax({
    url,
    method: "POST",
    headers: { ...authHeader, "Content-Type": "application/json" },
    data: JSON.stringify({ rawSql: btoa(unescape(encodeURIComponent(rawSql))) }),
    contentType: "application/json",
    success: function(data) {
      console.log(data);

      const allDevices = data.results || [];

      console.log(allDevices);

      if (!allDevices || allDevices.length === 0) {
        showModalOK(getString('Gen_Warning'), getString('Network_NoDevices'));
        return;
      }

      // Count totals for UI
      let archivedCount = 0;
      let offlineCount = 0;

      allDevices.forEach(device => {
        if (parseInt(device.devIsArchived) === 1) archivedCount++;
        if (parseInt(device.devPresentLastScan) === 0 && parseInt(device.devIsArchived) === 0) offlineCount++;
      });

      if(archivedCount > 0)
      {
        $('#showArchivedNumber').text(`(${archivedCount})`);
      }

      if(offlineCount > 0)
      {
        $('#showOfflineNumber').text(`(${offlineCount})`);
      }

      // Now apply UI filter based on toggles (always keep root)
      const filteredDevices = allDevices.filter(device => {
        const isRoot = (device.devMac || '').toLowerCase() === 'internet';

        if (isRoot) return true;
        if (!showArchived && parseInt(device.devIsArchived) === 1) return false;
        if (!showOffline && parseInt(device.devPresentLastScan) === 0) return false;
        return true;
      });

      // Sort filtered devices
      const orderTopologyBy = createArray(getSetting("UI_TOPOLOGY_ORDER"));
      const devicesSorted = filteredDevices.sort((a, b) => {
        const parsePort = (port) => {
          const parsed = parseInt(port, 10);
          return isNaN(parsed) ? Infinity : parsed;
        };

        switch (orderTopologyBy[0]) {
          case "Name":
            // ensuring string
            const nameA = (a.devName ?? "").toString();
            const nameB = (b.devName ?? "").toString();
            const nameCompare = nameA.localeCompare(nameB);
            return nameCompare !== 0
              ? nameCompare
              : parsePort(a.devParentPort) - parsePort(b.devParentPort);

          case "Port":
            return parsePort(a.devParentPort) - parsePort(b.devParentPort);

          default:
            return a.rowid - b.rowid;
        }
      });

      setCache(CACHE_KEYS.DEVICES_TOPOLOGY, JSON.stringify(devicesSorted));
      deviceListGlobal = devicesSorted;

      // Render filtered result
      initTree(getHierarchy());
      loadNetworkNodes();
      attachTreeEvents();
    },
    error: function(xhr, status, error) {
      console.error("Error loading topology data:", status, error);
      if (xhr.status === 401) {
        console.error("Authorization failed! API_TOKEN may be invalid. Check that API_TOKEN setting is correct and not empty.");
        showMessage("Authorization Failed: API_TOKEN setting may be invalid or not loaded. Please refresh the page.");
      }
    }
  });
}

// Initialize on page load
$(document).ready(function () {
  // show spinning icon
  showSpinner();

  // Start loading the network topology
  initNetworkTopology();
});
