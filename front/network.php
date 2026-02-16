<?php
  require 'php/templates/header.php';
  require 'php/templates/modals.php';
?>

<script>
  // show spinning icon
  showSpinner()
</script>

<!-- Page ------------------------------------------------------------------ -->
<div class="content-wrapper">
  <span class="helpIcon">
    <a target="_blank" href="https://docs.netalertx.com/NETWORK_TREE">
      <i class="fa fa-circle-question"></i>
    </a>
  </span>

  <div id="toggleFilters" class="">
      <div class="checkbox icheck col-xs-12">
        <label>
          <input type="checkbox" name="showOffline" checked>
            <div style="margin-left: 10px; display: inline-block; vertical-align: top;">
              <?= lang('Network_ShowOffline');?>
              <span id="showOfflineNumber">
                <!-- placeholder -->
              </span>
            </div>
        </label>
      </div>
      <div class="checkbox icheck col-xs-12">
        <label>
          <input type="checkbox" name="showArchived">
            <div style="margin-left: 10px; display: inline-block; vertical-align: top;">
              <?= lang('Network_ShowArchived');?>
              <span id="showArchivedNumber">
                <!-- placeholder -->
              </span>
            </div>
        </label>
      </div>
  </div>

  <div id="networkTree" class="drag">
    <!-- Tree topology Placeholder -->
  </div>

  <!-- Main content ---------------------------------------------------------- -->
  <section class="content networkTable">
    <!-- /.content -->
    <div class="nav-tabs-custom">
      <ul class="nav nav-tabs">
        <!-- Placeholder -->
      </ul>
    </div>
    <div class="tab-content">
      <!-- Placeholder -->
    </div>
  </section>
  <section id="unassigned-devices-wrapper">
      <!-- Placeholder -->
    </section>
    <!-- /.content -->
</div>
<!-- /.content-wrapper -->
<!-- ----------------------------------------------------------------------- -->

<?php
  require 'php/templates/footer.php';
?>

<script src="lib/treeviz/bundle.js"></script>

<script defer>

  // -----------------------------------------------------------------------
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
            parent.devName AS node_name,
            parent.devMac AS node_mac,
            parent.devPresentLastScan AS online,
            parent.devType AS node_type,
            parent.devParentMAC AS parent_mac,
            parent.devIcon AS node_icon,
            parent.devAlertDown AS node_alert,
            COUNT(child.devMac) AS node_ports_count
        FROM Devices AS parent
        LEFT JOIN Devices AS child
            /* CRITICAL FIX: COLLATE NOCASE ensures the join works
               even if devParentMAC is uppercase and devMac is lowercase
            */
            ON child.devParentMAC = parent.devMac COLLATE NOCASE
        WHERE parent.devType IN (${networkDeviceTypes})
          AND parent.devIsArchived = 0
        GROUP BY parent.devMac, parent.devName, parent.devPresentLastScan,
                 parent.devType, parent.devParentMAC, parent.devIcon, parent.devAlertDown
        ORDER BY parent.devName;
    `;

    const apiBase = getApiBase();
    const apiToken = getSetting("API_TOKEN");
    const url = `${apiBase}/dbquery/read`;

    $.ajax({
      url,
      method: "POST",
      headers: { "Authorization": `Bearer ${apiToken}` },
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
      }
    });
  }

  // -----------------------------------------------------------------------
  function renderNetworkTabs(nodes) {
    let html = '';
    nodes.forEach((node, i) => {
      const iconClass = node.online == 1 ? "text-green" :
                        (node.node_alert == 1 ? "text-red" : "text-gray50");

      const portLabel = node.node_ports_count ? ` (${node.node_ports_count})` : '';
      const icon = atob(node.node_icon);
      const id = node.node_mac.replace(/:/g, '_');

      html += `
        <li class="networkNodeTabHeaders ${i === 0 ? 'active' : ''}">
          <a href="#${id}" data-mytabmac="${node.node_mac}" id="${id}_id" data-toggle="tab" title="${node.node_name}">
            <div class="icon ${iconClass}">${icon}</div>
            <span class="node-name">${node.node_name}</span>${portLabel}
          </a>
        </li>`;
    });

    $('.nav-tabs').html(html);

    // populate tabs
    renderNetworkTabContent(nodes);

    // init selected (first) tab
    initTab();

    // init selected node highlighting
    initSelectedNodeHighlighting()

    // Register events on tab change
    $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
      initSelectedNodeHighlighting()
    });
  }

  // -----------------------------------------------------------------------
  function renderNetworkTabContent(nodes) {
    $('.tab-content').empty();

    nodes.forEach((node, i) => {
      const id = node.node_mac.replace(/:/g, '_');

      const badge = getStatusBadgeParts(
        node.online,
        node.node_alert,
        node.node_mac
      );

      const badgeHtml = `<a href="${badge.url}" class="badge ${badge.cssClass}">${badge.iconHtml} ${badge.status}</a>`;
      const parentId = node.parent_mac.replace(/:/g, '_');

      isRootNode = node.parent_mac == "";

      const paneHtml = `
                <div class="tab-pane box box-aqua box-body ${i === 0 ? 'active' : ''}" id="${id}">
                  <h5><i class="fa fa-server"></i> ${getString('Network_Node')}</h5>

                  <div class="mb-3 row">
                    <label class="col-sm-3 col-form-label fw-bold">${getString('DevDetail_Tab_Details')}</label>
                    <div class="col-sm-9">
                      <a href="./deviceDetails.php?mac=${node.node_mac}" target="_blank" class="anonymize">${node.node_name}</a>
                    </div>
                  </div>

                  <div class="mb-3 row">
                    <label class="col-sm-3 col-form-label fw-bold">MAC</label>
                    <div class="col-sm-9 anonymize">${node.node_mac}</div>
                  </div>

                  <div class="mb-3 row">
                    <label class="col-sm-3 col-form-label fw-bold">${getString('Device_TableHead_Type')}</label>
                    <div class="col-sm-9">${node.node_type}</div>
                  </div>

                  <div class="mb-3 row">
                    <label class="col-sm-3 col-form-label fw-bold">${getString('Device_TableHead_Status')}</label>
                    <div class="col-sm-9">${badgeHtml}</div>
                  </div>

                  <div class="mb-3 row">
                    <label class="col-sm-3 col-form-label fw-bold">${getString('Network_Parent')}</label>
                    <div class="col-sm-9">
                      ${isRootNode ? '' : `<a class="anonymize" href="#">`}
                        <span my-data-mac="${node.parent_mac}" data-mac="${node.parent_mac}" data-devIsNetworkNodeDynamic="1" onclick="handleNodeClick(this)">
                          ${isRootNode ? getString('Network_Root') : getDevDataByMac(node.parent_mac, "devName")}
                        </span>
                      ${isRootNode ? '' : `</a>`}
                    </div>
                  </div>
                  <hr/>
                  <div class="box box-aqua box-body" id="connected">
                    <h5>
                      <i class="fa fa-sitemap fa-rotate-270"></i>
                      ${getString('Network_Connected')}
                    </h5>

                    <div id="leafs_${id}" class="table-responsive"></div>
                  </div>
                </div>
              `;


      $('.tab-content').append(paneHtml);
      loadConnectedDevices(node.node_mac);
    });
  }

  // ----------------------------------------------------
  function loadDeviceTable({ sql, containerSelector, tableId, wrapperHtml = null, assignMode = true }) {
    const apiBase = getApiBase();
    const apiToken = getSetting("API_TOKEN");
    const url = `${apiBase}/dbquery/read`;

    $.ajax({
      url,
      method: "POST",
      headers: { "Authorization": `Bearer ${apiToken}` },
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
            const badge = getStatusBadgeParts(
              device.devPresentLastScan,
              device.devAlertDown,
              device.devMac,
              device.devStatus
            );
            return `<a href="${badge.url}" class="badge ${badge.cssClass}">${badge.iconHtml} ${badge.text}</a>`;
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

  // ----------------------------------------------------
  function loadUnassignedDevices() {
    const sql = `
      SELECT devMac, devPresentLastScan, devName, devLastIP, devVendor, devAlertDown, devParentPort
      FROM Devices
      WHERE (devParentMAC IS NULL OR devParentMAC IN ("", " ", "undefined", "null"))
        AND devMac NOT LIKE "%internet%"
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

  // ----------------------------------------------------
 function loadConnectedDevices(node_mac) {
    // Standardize the input just in case
    const normalized_mac = node_mac.toLowerCase();

    const sql = `
      SELECT devName, devMac, devLastIP, devVendor, devPresentLastScan, devAlertDown, devParentPort,
        CASE
            WHEN devIsNew = 1 THEN 'New'
            WHEN devPresentLastScan = 1 THEN 'On-line'
            WHEN devPresentLastScan = 0 AND devAlertDown != 0 THEN 'Down'
            WHEN devIsArchived = 1 THEN 'Archived'
            WHEN devPresentLastScan = 0 THEN 'Off-line'
            ELSE 'Unknown status'
        END AS devStatus
      FROM Devices
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

  // -----------------------------------------------------------
  // INIT
  // -----------------------------------------------------------

  const networkDeviceTypes = getSetting("NETWORK_DEVICE_TYPES").replace("[", "").replace("]", "");
  const showArchived = getCache('showArchived') === "true";
  const showOffline = getCache('showOffline') === "true";

  console.log('showArchived:', showArchived);
  console.log('showOffline:', showOffline);

  // Always get all devices
  const rawSql = `
    SELECT *,
      CASE
        WHEN devAlertDown != 0 AND devPresentLastScan = 0 THEN "Down"
        WHEN devPresentLastScan = 1 THEN "On-line"
        ELSE "Off-line"
      END AS devStatus,
      CASE
        WHEN devType IN (${networkDeviceTypes}) THEN 1
        ELSE 0
      END AS devIsNetworkNodeDynamic
    FROM Devices a
  `;

  const apiBase = getApiBase();
  const apiToken = getSetting("API_TOKEN");
  const url = `${apiBase}/dbquery/read`;

  $.ajax({
    url,
    method: "POST",
    headers: { "Authorization": `Bearer ${apiToken}` },
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

    setCache('devicesListNew', JSON.stringify(devicesSorted));
    deviceListGlobal = devicesSorted;

    // Render filtered result
    initTree(getHierarchy());
    loadNetworkNodes();
    attachTreeEvents();
  },
  error: function(xhr, status, error) {
    console.error("Error loading topology data:", status, error);
  }
});

</script>


<script defer>
// ---------------------------------------------------------------------------
// Tree functionality
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
var leafNodesCount = 0;
var visibleNodesCount = 0;
var parentNodesCount = 0;
var hiddenMacs = []; // hidden children
var hiddenChildren = [];
var deviceListGlobal = null;

// ---------------------------------------------------------------------------
// Recursively get children nodes and build a tree
function getChildren(node, list, path, visited = [])
{
    var children = [];

    // Check for infinite recursion by seeing if the node has been visited before
    if (visited.includes(node.devMac.toLowerCase())) {
        console.error("Infinite recursion detected at node:", node.devMac);
        write_notification("[ERROR] ⚠ Infinite recursion detected. You probably have assigned the Internet node to another children node or to itself. Please open a new issue on GitHub and describe how you did it.", 'interrupt')
        return { error: "Infinite recursion detected", node: node.devMac };
    }

    // Add current node to visited list
    visited.push(node.devMac.toLowerCase());

    // Loop through all items to find children of the current node
    for (var i in list) {
      const item = list[i];
      const parentMac = item.devParentMAC || "";       // null-safe
      const nodeMac = node.devMac || "";               // null-safe

      if (parentMac != "" && parentMac.toLowerCase() == nodeMac.toLowerCase() && !hiddenMacs.includes(parentMac)) {

        visibleNodesCount++;

        // Process children recursively, passing a copy of the visited list
        children.push(getChildren(list[i], list, path + ((path == "") ? "" : '|') + parentMac, visited));
      }
    }

    // Track leaf and parent node counts
    if (children.length == 0) {
        leafNodesCount++;
    } else {
        parentNodesCount++;
    }

    return {
        name: node.devName,
        path: path,
        mac: node.devMac,
        port: node.devParentPort,
        id: node.devMac,
        parentMac: node.devParentMAC,
        icon: node.devIcon,
        type: node.devType,
        devIsNetworkNodeDynamic: node.devIsNetworkNodeDynamic,
        vendor: node.devVendor,
        lastseen: node.devLastConnection,
        firstseen: node.devFirstConnection,
        ip: node.devLastIP,
        status: node.devStatus,
        presentLastScan: node.devPresentLastScan,
        alertDown: node.devAlertDown,
        hasChildren: children.length > 0 || hiddenMacs.includes(node.devMac),
        relType: node.devParentRelType,
        hiddenChildren: hiddenMacs.includes(node.devMac),
        qty: children.length,
        children: children
    };
}

// ---------------------------------------------------------------------------
function getHierarchy()
{
  // reset counters before rebuilding the hierarchy
  leafNodesCount = 0;
  visibleNodesCount = 0;
  parentNodesCount = 0;

  let internetNode = null;

  for(i in deviceListGlobal)
  {
    if(deviceListGlobal[i].devMac == 'Internet')
    {
      internetNode = deviceListGlobal[i];

      return (getChildren(internetNode, deviceListGlobal, ''))
      break;
    }
  }

  if (!internetNode) {
    showModalOk(
      getString('Network_Configuration_Error'),
      getString('Network_Root_Not_Configured')
    );
    console.error("getHierarchy(): Internet node not found");
    return null;
  }
}

//---------------------------------------------------------------------------
function toggleSubTree(parentMac, treePath)
{
  treePath = treePath.split('|')

  if(!hiddenMacs.includes(parentMac))
  {
    hiddenMacs.push(parentMac)
  }
  else
  {
    removeItemFromArray(hiddenMacs, parentMac)
  }

  updatedTree = getHierarchy()
  myTree.refresh(updatedTree);

  // re-attach any onclick events
  attachTreeEvents();
}

// ---------------------------------------------------------------------------
function attachTreeEvents()
{
  //  toggle subtree functionality
  $("div[data-mytreemac]").each(function(){
      $(this).attr('onclick', 'toggleSubTree("'+$(this).attr('data-mytreemac')+'","'+ $(this).attr('data-mytreepath')+'")')
  });
}

// ---------------------------------------------------------------------------
// Handle network node click - select correct tab in the bottom table
function handleNodeClick(el)
{

  isNetworkDevice = $(el).data("devisnetworknodedynamic") == 1;
  targetTabMAC = ""
  thisDevMac= $(el).data("mac");

  if (isNetworkDevice == false)
  {
    targetTabMAC = $(el).data("parentmac");
  } else
  {
    targetTabMAC = thisDevMac;
  }

  var targetTab = $(`a[data-mytabmac="${targetTabMAC}"]`);

  if (targetTab.length) {
    // Simulate a click event on the target tab
    targetTab.click();


  }

  if (isNetworkDevice) {
    // Smooth scroll to the tab content
    $('html, body').animate({
      scrollTop: targetTab.offset().top - 50
    }, 500); // Adjust the duration as needed
  }  else {
    $("tr.selected").removeClass("selected");
    $(`tr[data-mac="${thisDevMac}"]`).addClass("selected");

    const tableId = "table_leafs_" + targetTabMAC.replace(/:/g, '_');
    const $table = $(`#${tableId}`).DataTable();

    // Find the row index (in the full data set) that matches
    const rowIndex = $table
      .rows()
      .eq(0)
      .filter(function(idx) {
        return $table.row(idx).node().getAttribute("data-mac") === thisDevMac;
      });

    if (rowIndex.length > 0) {
      // Change to the page where this row is
      $table.page(Math.floor(rowIndex[0] / $table.page.len())).draw(false);

      // Delay needed so the row is in the DOM after page draw
      setTimeout(() => {
        const rowNode = $table.row(rowIndex[0]).node();
        $(rowNode).addClass("selected");

        // Smooth scroll to the row
        $('html, body').animate({
          scrollTop: $(rowNode).offset().top - 50
        }, 500);
      }, 0);
    }
  }
}

// ---------------------------------------------------------------------------
var myTree;
var emSize;
var nodeHeight;
// var sizeCoefficient = 1.4

function pxToEm(px, element) {
    var baseFontSize = parseFloat($(element || "body").css("font-size"));
    return px / baseFontSize;
}

function emToPx(em, element) {
    var baseFontSize = parseFloat($(element || "body").css("font-size"));
    return Math.round(em * baseFontSize);
}

function initTree(myHierarchy)
{
  if(myHierarchy && myHierarchy.type !== "")
  {
    // calculate the drawing area based on the tree width and available screen size
    let baseFontSize = parseFloat($('html').css('font-size'));
    let treeAreaHeight = ($(window).height() - 155); ;
    let minNodeWidth = 60 // min safe node width not breaking the tree

    // calculate the font size of the leaf nodes to fit everything into the tree area
    leafNodesCount == 0 ? 1 : leafNodesCount;

    emSize = pxToEm((treeAreaHeight/(leafNodesCount)).toFixed(2));

    // let screenWidthEm = pxToEm($('.networkTable').width()-15);
    let minTreeWidthPx = parentNodesCount * minNodeWidth;
    let actualWidthPx = $('.networkTable').width() - 15;

    let finalWidthPx = Math.max(actualWidthPx, minTreeWidthPx);

    // override original value
    let screenWidthEm = pxToEm(finalWidthPx);

        // handle canvas and node size if only a few nodes
    emSize > 1 ? emSize = 1 : emSize = emSize;

    let nodeHeightPx = emToPx(emSize*1);
    let nodeWidthPx = emToPx(screenWidthEm / (parentNodesCount));

    // handle if only a few nodes
    nodeWidthPx > 160 ? nodeWidthPx = 160 : nodeWidthPx = nodeWidthPx;
    if (nodeWidthPx < minNodeWidth) nodeWidthPx = minNodeWidth;  // minimum safe width

    console.log("Calculated nodeWidthPx =", nodeWidthPx, "emSize =", emSize , " screenWidthEm:", screenWidthEm, " emToPx(screenWidthEm):" , emToPx(screenWidthEm));

    // init the drawing area size
    $("#networkTree").attr('style', `height:${treeAreaHeight}px; width:${emToPx(screenWidthEm)}px`)

    console.log(Treeviz);

    myTree = Treeviz.create({
      htmlId: "networkTree",
      renderNode:  nodeData =>  {

        (!emptyArr.includes(nodeData.data.port )) ? port =  nodeData.data.port : port = "";

        (port == "" || port == 0 || port == 'None' ) ? portBckgIcon = `<i class="fa fa-wifi"></i>` : portBckgIcon = `<i class="fa fa-ethernet"></i>`;

        portHtml = (port == "" || port == 0 || port == 'None' ) ? " &nbsp " : port;

        // Build HTML for individual nodes in the network diagram
        deviceIcon = (!emptyArr.includes(nodeData.data.icon )) ?
                  `<div class="netIcon">
                        ${atob(nodeData.data.icon)}
                  </div>` : "";
        devicePort = `<div  class="netPort"
                            style="width:${emSize}em;height:${emSize}em">
                        ${portHtml}</div>
                      <div  class="portBckgIcon"
                            style="margin-left:-${emSize*0.7}em;">
                            ${portBckgIcon}
                      </div>`;
        collapseExpandIcon = nodeData.data.hiddenChildren ?
                            "square-plus" : "square-minus";

        // generate +/- icon if node has children nodes
        collapseExpandHtml = nodeData.data.hasChildren ?
                      `<div class="netCollapse"
                            style="font-size:${nodeHeightPx/2}px;top:${Math.floor(nodeHeightPx / 4)}px"
                            data-mytreepath="${nodeData.data.path}"
                            data-mytreemac="${nodeData.data.mac}">
                        <i class="fa fa-${collapseExpandIcon} pointer"></i>
                      </div>` : "";

        selectedNodeMac = $(".nav-tabs-custom .active a").attr('data-mytabmac')

        highlightedCss = nodeData.data.mac == selectedNodeMac ?
                      " highlightedNode " : "";
        cssNodeType = nodeData.data.devIsNetworkNodeDynamic  ?
                      " node-network-device " : " node-standard-device ";

        networkHardwareIcon = nodeData.data.devIsNetworkNodeDynamic ? `<span class="network-hw-icon">
                                  <i class="fa-solid fa-hard-drive"></i>
                              </span>` : "";

        const badgeConf = getStatusBadgeParts(nodeData.data.presentLastScan, nodeData.data.alertDown, nodeData.data.mac, statusText = '')

        return result = `<div
                              class="node-inner hover-node-info box pointer ${highlightedCss} ${cssNodeType}"
                              style="height:${nodeHeightPx}px;font-size:${nodeHeightPx-5}px;"
                              onclick="handleNodeClick(this)"
                              data-mac="${nodeData.data.mac}"
                              data-parentMac="${nodeData.data.parentMac}"
                              data-name="${nodeData.data.name}"
                              data-ip="${nodeData.data.ip}"
                              data-mac="${nodeData.data.mac}"
                              data-vendor="${nodeData.data.vendor}"
                              data-type="${nodeData.data.type}"
                              data-devIsNetworkNodeDynamic="${nodeData.data.devIsNetworkNodeDynamic}"
                              data-lastseen="${nodeData.data.lastseen}"
                              data-firstseen="${nodeData.data.firstseen}"
                              data-relationship="${nodeData.data.relType}"
                              data-status="${nodeData.data.status}"
                              data-present="${nodeData.data.presentLastScan}"
                              data-alert="${nodeData.data.alertDown}"
                              data-icon="${nodeData.data.icon}"
                          >
                            <div class="netNodeText">
                              <strong><span>${devicePort}  <span class="${badgeConf.cssText}">${deviceIcon}</span></span>
                                <span class="spanNetworkTree anonymizeDev" style="width:${nodeWidthPx-50}px">${nodeData.data.name}</span>
                                ${networkHardwareIcon}
                              </strong>
                            </div>
                          </div>
                          ${collapseExpandHtml}`;
      },
      mainAxisNodeSpacing: 'auto',
      // secondaryAxisNodeSpacing: 0.3,
      nodeHeight: nodeHeightPx,
      nodeWidth: nodeWidthPx,
      marginTop: '5',
      isHorizontal : true,
      hasZoom: true,
      hasPan: true,
      marginLeft: '10',
      marginRight: '10',
      idKey: "mac",
      hasFlatData: false,
      relationnalField: "children",
      linkWidth: (nodeData) => 2,
      linkColor: (nodeData) => {
        relConf = getRelationshipConf(nodeData.data.relType)
        return relConf.color;
      }
      // onNodeClick: (nodeData) => handleNodeClick(nodeData),
    });

    console.log(deviceListGlobal);
    myTree.refresh(myHierarchy);

    // hide spinning icon
    hideSpinner()
  } else
  {
    console.error("getHierarchy() not returning expected result");
  }
}


// ---------------------------------------------------------------------------
// Tabs functionality
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
function initTab()
{
  key = "activeNetworkTab"

  // default selection
  selectedTab = "Internet_id"

  // the #target from the url
  target = getQueryString('mac')

  // update cookie if target specified
  if(target != "")
  {
    setCache(key, target.replaceAll(":","_")+'_id') // _id is added so it doesn't conflict with AdminLTE tab behavior
  }

  // get the tab id from the cookie (already overridden by the target)
  if(!emptyArr.includes(getCache(key)))
  {
    selectedTab = getCache(key);
  }

  // Activate panel
  $('.nav-tabs a[id='+ selectedTab +']').tab('show');

  // When changed save new current tab
  $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
    setCache(key, $(e.target).attr('id'))
  });

}

// ---------------------------------------------------------------------------
function initSelectedNodeHighlighting()
{

  var currentNodeMac = $(".networkNodeTabHeaders.active a").data("mytabmac");

  // change highlighted node in the tree
  selNode = $("#networkTree .highlightedNode")[0]

  console.log(selNode)

  if(selNode)
  {
    $(selNode).attr('class',  $(selNode).attr('class').replace('highlightedNode'))
  }

  newSelNode = $("#networkTree div[data-mac='"+currentNodeMac+"']")[0]

  console.log(newSelNode)

  $(newSelNode).attr('class',  $(newSelNode).attr('class') + ' highlightedNode')
}

// ---------------------------------------------------------------------------
function updateLeaf(leafMac, action) {
  console.log(leafMac); // child
  console.log(action);  // action

  const nodeMac = $(".networkNodeTabHeaders.active a").data("mytabmac") || "";

  if (action === "assign") {
    if (!nodeMac) {
      showMessage(getString("Network_Cant_Assign_No_Node_Selected"));
    } else if (leafMac.toLowerCase().includes("internet")) {
      showMessage(getString("Network_Cant_Assign"));
    } else {
      saveData("updateNetworkLeaf", leafMac, nodeMac);
      setTimeout(() => location.reload(), 500);
    }

  } else if (action === "unassign") {
    saveData("updateNetworkLeaf", leafMac, "");
    setTimeout(() => location.reload(), 500);

  } else {
    console.warn("Unknown action:", action);
  }
}

// ---------------------------------------------------------------------------
// showing icons or device names in tabs depending on available screen size
function checkTabsOverflow() {
  const $ul = $('.nav-tabs');
  const $lis = $ul.find('li');

  // First measure widths with current state
  let totalWidth = 0;
  $lis.each(function () {
    totalWidth += $(this).outerWidth(true);
  });

  const ulWidth = $ul.width();
  const isOverflowing = totalWidth > ulWidth;

  if (isOverflowing) {
    if (!$ul.hasClass('hide-node-names')) {
      $ul.addClass('hide-node-names');

      // Re-check: did hiding fix it?
      requestAnimationFrame(() => {
        let newTotal = 0;
        $lis.each(function () {
          newTotal += $(this).outerWidth(true);
        });

        if (newTotal > $ul.width()) {
          // Still overflowing — do nothing, keep class
        }
      });
    }
  } else {
    if ($ul.hasClass('hide-node-names')) {
      $ul.removeClass('hide-node-names');

      // Re-check: did un-hiding break it?
      requestAnimationFrame(() => {
        let newTotal = 0;
        $lis.each(function () {
          newTotal += $(this).outerWidth(true);
        });

        if (newTotal > $ul.width()) {
          // Oops, that broke it — re-hide
          $ul.addClass('hide-node-names');
        }
      });
    }
  }
}

let resizeTimeout;
$(window).on('resize', function () {
  clearTimeout(resizeTimeout);
  resizeTimeout = setTimeout(() => {
    checkTabsOverflow();
  }, 100);
});


// init pop up hover  boxes for device details
initHoverNodeInfo();

$(document).ready(function () {
  // Restore cached values on load
  const cachedOffline = getCache('showOffline');
  if (cachedOffline !== null) {
    $('input[name="showOffline"]').prop('checked', cachedOffline === 'true');
  }

  const cachedArchived = getCache('showArchived');
  if (cachedArchived !== null) {
    $('input[name="showArchived"]').prop('checked', cachedArchived === 'true');
  }

  // Function to enable/disable showArchived based on showOffline
  function updateArchivedToggle() {
    const isOfflineChecked = $('input[name="showOffline"]').is(':checked');
    const archivedToggle = $('input[name="showArchived"]');

    if (!isOfflineChecked) {
      archivedToggle.prop('checked', false);
      archivedToggle.prop('disabled', true);
      setCache('showArchived', false);
    } else {
      archivedToggle.prop('disabled', false);
    }
  }

  // Initial state on load
  updateArchivedToggle();

  // Bind change event for both toggles
  $('input[name="showOffline"], input[name="showArchived"]').on('change', function () {
    const name = $(this).attr('name');
    const value = $(this).is(':checked');
    setCache(name, value);

    // Update state of showArchived if showOffline changed
    if (name === 'showOffline') {
      updateArchivedToggle();
    }

    // Refresh page after a brief delay to ensure cache is written
    setTimeout(() => {
      location.reload();
    }, 100);
  });
});


</script>



