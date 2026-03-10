// network-events.js
// Event handlers and tree node click interactions

/**
 * Handle network node click - select correct tab and scroll to appropriate content
 * @param {HTMLElement} el - The clicked element
 */
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

/**
 * Handle window resize events to recheck tab overflow
 */
let resizeTimeout;
$(window).on('resize', function () {
  clearTimeout(resizeTimeout);
  resizeTimeout = setTimeout(() => {
    checkTabsOverflow();
  }, 100);
});

/**
 * Initialize page on document ready
 * Sets up toggle filters and event handlers
 */
$(document).ready(function () {
  // Restore cached values on load
  const cachedOffline = getCache(CACHE_KEYS.SHOW_OFFLINE);
  if (cachedOffline !== null) {
    $('input[name="showOffline"]').prop('checked', cachedOffline === 'true');
  }

  const cachedArchived = getCache(CACHE_KEYS.SHOW_ARCHIVED);
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
      setCache(CACHE_KEYS.SHOW_ARCHIVED, false);
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
    // setCache(name, value) works because CACHE_KEYS.SHOW_OFFLINE === 'showOffline'
    // and CACHE_KEYS.SHOW_ARCHIVED === 'showArchived' — matches the DOM input name attr.
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

  // init pop up hover  boxes for device details
  initHoverNodeInfo();
});
