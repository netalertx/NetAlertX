// =============================================================================
// devices-init.js — Page bootstrap for devices.php.
//
// Declares the shared page-level state (deviceStatus, tableColumnOrder, etc.)
// used across the other devices-*.js files, wires up the mobile-collapse
// behavior, and defines main() — the entry point run once the app has
// finished initializing (see callAfterAppInitialized below).
//
// Loaded last (after devices-totals.js, devices-filters.js, devices-table.js,
// devices-custom-props.js) since it's the orchestrator that calls into them —
// though since these are plain global var/function declarations sharing one
// scope, load order among the devices-*.js files doesn't affect correctness.
// =============================================================================

var deviceStatus    = 'all';

var tableOrder      = getCache ("nax_parTableOrder") == "" ? [[3,'desc'], [0,'asc']] : JSON.parse(getCache ("nax_parTableOrder")) ;

var tableColumnHide = [];
var tableColumnOrder = [];
var tableColumnVisible = [];
headersDefaultOrder = [];
missingNumbers = [];

// DEVICE_COLUMN_FIELDS, COL, NUMERIC_DEFAULTS, GRAPHQL_EXTRA_FIELDS, COLUMN_NAME_MAP
// are all defined in js/device-columns.js — edit that file to add new columns.

// Collapse DevicePresence and Filters sections by default on small/mobile screens
(function collapseOnMobile() {
  if (window.innerWidth < 768) {
    ['#clients', '#columnFiltersWrap'].forEach(function(sel) {
      var $box = $(sel);
      if ($box.length) {
        $box.addClass('collapsed-box');
        $box.find('.box-body, .box-footer').hide();
        $box.find('[data-widget="collapse"] i').removeClass('fa-minus').addClass('fa-plus');
      }
    });
  }
})();

// Read parameters & Initialize components
callAfterAppInitialized(main)
showSpinner();

// -----------------------------------------------------------------------------
function hideDevicesSkeleton() {
   $('#devices-skeleton').fadeOut(0, function() { $(this).remove(); });
}

// Fallback: ensure skeleton is removed even if DataTable fails to initialize
setTimeout(hideDevicesSkeleton, 15000);

// -----------------------------------------------------------------------------
function main () {

  showSpinner();

  initFilters();

  // render tiles
  getDevicesTotals();

  //initialize the table headers in the correct order
  var availableColumns = getSettingOptions("UI_device_columns").split(",");
  headersDefaultOrder = availableColumns.map(val => getString(val));

  var selectedColumns = JSON.parse(getSetting("UI_device_columns").replace(/'/g, '"'));

  // generate default order lists of given length
  var columnsStr = JSON.stringify(Array.from({ length: headersDefaultOrder.length }, (_, i) => i));
  tableColumnOrder = Array.from({ length: headersDefaultOrder.length }, (_, i) => i);
  tableColumnVisible = [];

  // Initialize tableColumnVisible by including all columns from selectedColumns, preserving their order.
  tableColumnVisible = selectedColumns.map(column => availableColumns.indexOf(column)).filter(index => index !== -1);

  // Add any columns from availableColumns that are not in selectedColumns to the end.
  const remainingColumns = availableColumns.map((column, index) => index).filter(index => !tableColumnVisible.includes(index));

  // Combine both arrays.
  tableColumnOrder = tableColumnVisible.concat(remainingColumns);

  // Generate the full array of numbers from 0 to totalLength - 1 of tableColumnOrder
  const fullArray = Array.from({ length: tableColumnOrder.length }, (_, i) => i);

  // Filter out the elements already present in inputArray
  missingNumbers = fullArray.filter(num => !tableColumnVisible.includes(num));

  // Concatenate the inputArray with the missingNumbers
  tableColumnOrder = [...tableColumnVisible, ...missingNumbers];

  // Initialize components with parameters
  initializeDatatable(getUrlAnchor('my_devices'));

  // check if data outdated and show spinner if so
  handleLoadingDialog()

}

// -----------------------------------------------------------------------------
// Update cache with shown devices before navigating away
window.addEventListener('beforeunload', function(event) {
    // Call your function here
    macs = getMacsOfShownDevices();

    setCache("ntx_visible_macs", macs)

});
