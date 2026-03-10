// network-tree.js
// Tree hierarchy construction and rendering functions

// Global state variables
var leafNodesCount = 0;
var visibleNodesCount = 0;
var parentNodesCount = 0;
var hiddenMacs = []; // hidden children
var hiddenChildren = [];
var deviceListGlobal = null;
var myTree;

/**
 * Recursively get children nodes and build a tree
 * @param {Object} node - Current node
 * @param {Array} list - Full device list
 * @param {string} path - Path to current node
 * @param {Array} visited - Visited nodes (for cycle detection)
 * @returns {Object} Tree node with children
 */
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
      const parentMac = item.devParentMAC?.toLowerCase() || "";       // null-safe
      const nodeMac = node.devMac?.toLowerCase() || "";               // null-safe

      if (parentMac != "" && parentMac == nodeMac && !hiddenMacs.includes(parentMac)) {

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

    // console.log(node);

    return {
        devName: node.devName,
        path: path,
        devMac: node.devMac,
        devParentPort: node.devParentPort,
        id: node.devMac,
        devParentMAC: node.devParentMAC,
        devIcon: node.devIcon,
        devType: node.devType,
        devIsNetworkNodeDynamic: node.devIsNetworkNodeDynamic,
        devVendor: node.devVendor,
        devLastConnection: node.devLastConnection,
        devFirstConnection: node.devFirstConnection,
        devLastIP: node.devLastIP,
        devStatus: node.devStatus,
        devPresentLastScan: node.devPresentLastScan,
        devFlapping: node.devFlapping,
        devAlertDown: node.devAlertDown,
        devIsSleeping: node.devIsSleeping || 0,
        devIsArchived: node.devIsArchived || 0,
        devIsNew:      node.devIsNew      || 0,
        hasChildren: children.length > 0 || hiddenMacs.includes(node.devMac),
        devParentRelType: node.devParentRelType,
        devVlan: node.devVlan,
        devSSID: node.devSSID,
        hiddenChildren: hiddenMacs.includes(node.devMac),
        qty: children.length,
        children: children
    };
}

/**
 * Build complete hierarchy starting from the Internet node
 * @returns {Object} Root hierarchy object
 */
function getHierarchy()
{
  // reset counters before rebuilding the hierarchy
  leafNodesCount = 0;
  visibleNodesCount = 0;
  parentNodesCount = 0;

  let internetNode = null;

  for(i in deviceListGlobal)
  {
    if(deviceListGlobal[i].devMac.toLowerCase() == 'internet')
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

/**
 * Toggle collapse/expand state of a subtree
 * @param {string} parentMac - MAC address of parent node to toggle
 * @param {string} treePath - Path in tree (colon-separated)
 */
function toggleSubTree(parentMac, treePath)
{
  treePath = treePath.split('|')

  parentMac = parentMac.toLowerCase()

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

/**
 * Attach click events to tree collapse/expand controls
 */
function attachTreeEvents()
{
  //  toggle subtree functionality
  $("div[data-mytreemac]").each(function(){
      $(this).attr('onclick', 'toggleSubTree("'+$(this).attr('data-mytreemac')+'","'+ $(this).attr('data-mytreepath')+'")')
  });
}

/**
 * Convert pixels to em units
 * @param {number} px - Pixel value
 * @param {HTMLElement} element - Reference element for font-size
 * @returns {number} Value in em units
 */
function pxToEm(px, element) {
    var baseFontSize = parseFloat($(element || "body").css("font-size"));
    return px / baseFontSize;
}

/**
 * Convert em units to pixels
 * @param {number} em - Value in em units
 * @param {HTMLElement} element - Reference element for font-size
 * @returns {number} Value in pixels (rounded)
 */
function emToPx(em, element) {
    var baseFontSize = parseFloat($(element || "body").css("font-size"));
    return Math.round(em * baseFontSize);
}

/**
 * Initialize tree visualization
 * @param {Object} myHierarchy - Hierarchy object to render
 */
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

        (!emptyArr.includes(nodeData.data.devParentPort)) ? port = nodeData.data.devParentPort : port = "";

        (port == "" || port == 0 || port == 'None' ) ? portBckgIcon = `<i class="fa fa-wifi"></i>` : portBckgIcon = `<i class="fa fa-ethernet"></i>`;

        portHtml = (port == "" || port == 0 || port == 'None' ) ? " &nbsp " : port;

        // Build HTML for individual nodes in the network diagram
        deviceIcon = (!emptyArr.includes(nodeData.data.devIcon)) ?
                  `<div class="netIcon">
                        ${atob(nodeData.data.devIcon)}
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
                            data-mytreemac="${nodeData.data.devMac}">
                        <i class="fa fa-${collapseExpandIcon} pointer"></i>
                      </div>` : "";

        selectedNodeMac = $(".nav-tabs-custom .active a").attr('data-mytabmac')

        highlightedCss = nodeData.data.devMac == selectedNodeMac ?
                      " highlightedNode " : "";
        cssNodeType = nodeData.data.devIsNetworkNodeDynamic  ?
                      " node-network-device " : " node-standard-device ";

        networkHardwareIcon = nodeData.data.devIsNetworkNodeDynamic ? `<span class="network-hw-icon">
                                  <i class="fa-solid fa-hard-drive"></i>
                              </span>` : "";

        const badgeConf = badgeFromDevice(nodeData.data);

        return result = `<div
                              class="node-inner hover-node-info box pointer ${highlightedCss} ${cssNodeType}"
                              style="height:${nodeHeightPx}px;font-size:${nodeHeightPx-5}px;"
                              onclick="handleNodeClick(this)"
                              data-mac="${nodeData.data.devMac}"
                              data-parentMac="${nodeData.data.devParentMAC}"
                              data-name="${nodeData.data.devName}"
                              data-ip="${nodeData.data.devLastIP}"
                              data-mac="${nodeData.data.devMac}"
                              data-vendor="${nodeData.data.devVendor}"
                              data-type="${nodeData.data.devType}"
                              data-devIsNetworkNodeDynamic="${nodeData.data.devIsNetworkNodeDynamic}"
                              data-lastseen="${nodeData.data.devLastConnection}"
                              data-firstseen="${nodeData.data.devFirstConnection}"
                              data-relationship="${nodeData.data.devParentRelType}"
                              data-flapping="${nodeData.data.devFlapping}"
                              data-sleeping="${nodeData.data.devIsSleeping || 0}"
                              data-archived="${nodeData.data.devIsArchived || 0}"
                              data-isnew="${nodeData.data.devIsNew || 0}"
                              data-status="${nodeData.data.devStatus}"
                              data-present="${nodeData.data.devPresentLastScan}"
                              data-alertdown="${nodeData.data.devAlertDown}"
                              data-icon="${nodeData.data.devIcon}"
                          >
                            <div class="netNodeText">
                              <strong><span>${devicePort}  <span class="${badgeConf.cssText}">${deviceIcon}</span></span>
                                <span class="spanNetworkTree anonymizeDev" style="width:${nodeWidthPx-50}px">${nodeData.data.devName}</span>
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
      idKey: "devMac",
      hasFlatData: false,
      relationnalField: "children",
      linkLabel: {
      render: (parent, child) => {
        // Return text or HTML to display on the connection line
        connectionLabel = (child?.data.devVlan ?? "") + "/" + (child?.data.devSSID ?? "");
        if(connectionLabel == "/")
        {
          connectionLabel = "";
        }

        return connectionLabel;
        // or with HTML:
        // return "<tspan><strong>reports to</strong></tspan>";
      },
      color: "#336c87ff",      // Label text color (optional)
      fontSize: nodeHeightPx - 5           // Label font size in px (optional)
    },
      linkWidth: (nodeData) => 2,
      linkColor: (nodeData) => {
        relConf = getRelationshipConf(nodeData.data.devParentRelType)
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
