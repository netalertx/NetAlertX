// network-api.js
// API calls and data loading functions for network topology

/**
 * Load network nodes (network device types)
 * Creates top-level tabs for each network device
 */
function loadNetworkNodes() {
  // Create Top level tabs   (List of network devices), explanation of the terminology below:
  //
  //             Switch 1 (node)
  //              /(p1)    \ (p2)     <----- port numbers
  //             /          \
  //   Smart TV (leaf)      Switch 2 (node (for the PC) and leaf (for Switch 1))
  //                          \
  //                          PC (leaf) <------- leafs are not included in this SQL query
  const rawSql = `
      SELECT
          parent.devName,
          LOWER(parent.devMac) AS devMac,
          parent.devPresentLastScan,
          parent.devType,
          LOWER(parent.devParentMAC) AS devParentMAC,
          parent.devIcon,
          parent.devAlertDown,
          parent.devFlapping,
          parent.devIsSleeping,
          parent.devIsNew,
          COUNT(child.devMac) AS node_ports_count
      FROM DevicesView AS parent
      LEFT JOIN DevicesView AS child
          /* CRITICAL FIX: COLLATE NOCASE ensures the join works
             even if devParentMAC is uppercase and devMac is lowercase
          */
          ON child.devParentMAC = parent.devMac COLLATE NOCASE
      WHERE parent.devType IN (${networkDeviceTypes})
        AND parent.devIsArchived = 0
      GROUP BY parent.devMac, parent.devName, parent.devPresentLastScan,
               parent.devType, parent.devParentMAC, parent.devIcon, parent.devAlertDown, parent.devFlapping, parent.devIsSleeping, parent.devIsNew
      ORDER BY parent.devName;
  `;

  const { token: apiToken, apiBase, authHeader } = getAuthContext();

  // Verify token is available
  if (!apiToken || apiToken.trim() === '') {
    console.error("API_TOKEN not available. Settings may not be loaded yet.");
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
      const nodes = data.results || [];
      renderNetworkTabs(nodes);
      loadUnassignedDevices();
      checkTabsOverflow();
    },
    error: function(xhr, status, error) {
      console.error("Error loading network nodes:", status, error);
      // Check if it's an auth error
      if (xhr.status === 401) {
        console.error("Authorization failed. API_TOKEN may be invalid or not yet loaded.");
      }
    }
  });
}

/**
 * Load device table with configurable SQL and rendering
 * @param {Object} options - Configuration object
 * @param {string} options.sql - SQL query to fetch devices
 * @param {string} options.containerSelector - jQuery selector for container
 * @param {string} options.tableId - ID for DataTable instance
 * @param {string} options.wrapperHtml - HTML wrapper for table
 * @param {boolean} options.assignMode - Whether to show assign/unassign buttons
 */
function loadDeviceTable({ sql, containerSelector, tableId, wrapperHtml = null, assignMode = true }) {
  const { token: apiToken, apiBase, authHeader } = getAuthContext();

  // Verify token is available
  if (!apiToken || apiToken.trim() === '') {
    console.error("API_TOKEN not available. Settings may not be loaded yet.");
    return;
  }

  const url = `${apiBase}/dbquery/read`;

  $.ajax({
    url,
    method: "POST",
    headers: { ...authHeader, "Content-Type": "application/json" },
    data: JSON.stringify({ rawSql: btoa(unescape(encodeURIComponent(sql))) }),
    contentType: "application/json",
    success: function(data) {
      const devices = data.results || [];
      const $container = $(containerSelector);

      // end if nothing to show
      if(devices.length == 0)
      {
        return;
      }

      $container.html(wrapperHtml);

      const $table = $(`#${tableId}`);

      const columns = [
        {
          title: assignMode ? getString('Network_ManageAssign') : getString('Network_ManageUnassign'),
          data: 'devMac',
          orderable: false,
          width: '5%',
          render: function (mac) {
            // mac = mac.toLowerCase()
            const label = assignMode ? 'assign' : 'unassign';
            const btnClass = assignMode ? 'btn-primary' : 'btn-primary bg-red';
            const btnText = assignMode ? getString('Network_ManageAssign') : getString('Network_ManageUnassign');
            return `<button class="btn ${btnClass} btn-sm" data-myleafmac="${mac}" onclick="updateLeaf('${mac}','${label}')">
                      ${btnText}
                    </button>`;
          }
        },
        {
          title: getString('Device_TableHead_Name'),
          data: 'devName',
          width: '15%',
          render: function (name, type, device) {
            return `<a href="./deviceDetails.php?mac=${device.devMac}" target="_blank">
                      <b class="anonymize">${name || '-'}</b>
                    </a>`;
          }
        },
        {
          title: getString('Device_TableHead_Status'),
          data: 'devStatus',
          width: '15%',
          render: function (_, type, device) {
            const badge = badgeFromDevice(device);
            return `<a href="${badge.url}" class="badge ${badge.cssClass}">${badge.iconHtml} ${badge.label}</a>`;
          }
        },
        {
          title: 'MAC',
          data: 'devMac',
          width: '5%',
          render: (data) => `<span class="anonymize">${data}</span>`
        },
        {
          title: getString('Network_Table_IP'),
          data: 'devLastIP',
          width: '5%'
        },
        {
          title: getString('Device_TableHead_Port'),
          data: 'devParentPort',
          width: '5%'
        },
        {
          title: getString('Device_TableHead_Vendor'),
          data: 'devVendor',
          width: '20%'
        }
      ].filter(Boolean);

      tableConfig = {
          data: devices,
          columns: columns,
          pageLength: 10,
          order: assignMode ? [[2, 'asc']] : [],
          responsive: true,
          autoWidth: false,
          searching: true,
          createdRow: function (row, data) {
            $(row).attr('data-mac', data.devMac);
          }
      };

      if ($.fn.DataTable.isDataTable($table)) {
        $table.DataTable(tableConfig).clear().rows.add(devices).draw();
      } else {
        $table.DataTable(tableConfig);
      }
    },
    error: function(xhr, status, error) {
      console.error("Error loading device table:", status, error);
    }
  });
}

/**
 * Load unassigned devices (devices without parent)
 */
function loadUnassignedDevices() {
  const sql = `
    SELECT devMac, devPresentLastScan, devName, devLastIP, devVendor, devAlertDown, devParentPort, devFlapping, devIsSleeping, devIsNew, devStatus
    FROM DevicesView
    WHERE (devParentMAC IS NULL OR devParentMAC IN ("", " ", "undefined", "null"))
      AND LOWER(devMac) NOT LIKE "%internet%"
      AND devIsArchived = 0
    ORDER BY devName ASC`;

  const wrapperHtml = `
    <div class="content">
      <div id="unassignedDevices" class="box box-aqua box-body table-responsive">
        <section>
          <h5><i class="fa-solid fa-plug-circle-xmark"></i>  ${getString('Network_UnassignedDevices')}</h5>
          <table id="unassignedDevicesTable" class="table table-striped" width="100%"></table>
        </section>
      </div>
    </div>`;

  loadDeviceTable({
    sql,
    containerSelector: '#unassigned-devices-wrapper',
    tableId: 'unassignedDevicesTable',
    wrapperHtml,
    assignMode: true
  });
}

/**
 * Load devices connected to a specific node
 * @param {string} node_mac - MAC address of the parent node
 */
function loadConnectedDevices(node_mac) {
  // Standardize the input just in case
  const normalized_mac = node_mac.toLowerCase();

  const sql = `
    SELECT devName, devMac, devLastIP, devVendor, devPresentLastScan, devAlertDown, devParentPort, devVlan, devFlapping, devIsSleeping, devIsNew, devIsArchived,
      CASE
          WHEN devIsNew = 1 THEN 'New'
          WHEN devPresentLastScan = 1 THEN 'On-line'
          WHEN devIsSleeping = 1 THEN 'Sleeping'
          WHEN devPresentLastScan = 0 AND devAlertDown != 0 THEN 'Down'
          WHEN devIsArchived = 1 THEN 'Archived'
          WHEN devPresentLastScan = 0 THEN 'Off-line'
          ELSE 'Unknown status'
      END AS devStatus
    FROM DevicesView
    /* Using COLLATE NOCASE here solves the 'TEXT' vs 'NOCASE' mismatch */
    WHERE devParentMac = '${normalized_mac}' COLLATE NOCASE`;

  // Keep the ID generation consistent
  const id = normalized_mac.replace(/:/g, '_');

  const wrapperHtml = `
    <table class="table table-bordered table-striped node-leafs-table " id="table_leafs_${id}" data-node-mac="${normalized_mac}">
    </table>`;

  loadDeviceTable({
    sql,
    containerSelector: `#leafs_${id}`,
    tableId: `table_leafs_${id}`,
    wrapperHtml,
    assignMode: false
  });
}
