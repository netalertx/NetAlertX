<?php
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once  $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
?>
<!-- ----------------------------------------------------------------------- -->


<!-- Hide Connections -->
<div class="col-sm-12 col-xs-12">
    <label class="col-sm-3 col-xs-10">
      <?= lang('DevDetail_Events_CheckBox');?>
    </label>
    <input class="checkbox blue col-sm-1 col-xs-2" id="chkHideConnectionEvents" type="checkbox" onChange="loadEventsData()">
</div>

<!-- Datatable Events -->
<table id="tableEvents" class="table table-bordered table-hover table-striped ">
    <thead>
    <tr>
    <th><?= lang("DevDetail_Tab_EventsTableDate");?></th>
    <th><?= lang("DevDetail_Tab_EventsTableDate");?></th>
    <th><?= lang("DevDetail_Tab_EventsTableEvent");?></th>
    <th><?= lang("DevDetail_Tab_EventsTableIP");?></th>
    <th><?= lang("DevDetail_Tab_EventsTableInfo");?></th>
    </tr>
    </thead>
</table>


<script>

function loadEventsData() {
  const mac = getMac();
  if (!mac) {
    console.warn("loadEventsData: mac not set, skipping");
    return;
  }

  const hideConnections = $('#chkHideConnectionEvents')[0].checked;

  let period = $("#period").val();
  let { start, end } = getPeriodStartEnd(period);

  const apiToken  = getSetting("API_TOKEN");
  const apiBase   = getApiBase();
  const graphqlUrl = `${apiBase}/graphql`;

  const query = `
    query Events($options: EventQueryOptionsInput) {
      events(options: $options) {
        count
        entries {
          eveDateTime
          eveEventType
          eveIp
          eveAdditionalInfo
        }
      }
    }
  `;

  $.ajax({
    url: graphqlUrl,
    method: "POST",
    contentType: "application/json",
    headers: {
      "Authorization": `Bearer ${apiToken}`
    },
    data: JSON.stringify({
      query,
      variables: {
        options: {
          eveMac:   mac,  // local const from getMac() above
          dateFrom: start,
          dateTo:   end,
          limit:    500,
          sort:     [{ field: "eveDateTime", order: "desc" }]
        }
      }
    }),
    success: function (data) {
      const CONNECTION_TYPES = ["Connected", "Disconnected", "VOIDED - Connected", "VOIDED - Disconnected"];

      const rows = data.data.events.entries
        .filter(row => !hideConnections || !CONNECTION_TYPES.includes(row.eveEventType))
        .map(row => {
          const rawDate = row.eveDateTime;
          const formattedDate = rawDate ? localizeTimestamp(rawDate) : '-';

          return [
            formattedDate,
            row.eveDateTime,
            row.eveEventType,
            row.eveIp,
            row.eveAdditionalInfo
          ];
        });

      const table = $('#tableEvents').DataTable();
      table.clear();
      table.rows.add(rows);
      table.draw();

      hideSpinner();
    },
    error: function (xhr) {
      console.error("Failed to load events", xhr.responseText);
      hideSpinner();
    }
  });
}


function initializeEventsDatatable (eventsRows) {

  if ($.fn.dataTable.isDataTable('#tableEvents')) {
      $('#tableEvents').DataTable().clear().destroy();
  }

  $('#tableEvents').DataTable({
      'paging'      : true,
      'lengthChange': true,
      'lengthMenu'  : [[10, 25, 50, 100, 500, -1], [10, 25, 50, 100, 500, 'All']],
      'searching'   : true,
      'ordering'    : true,
      'info'        : true,
      'autoWidth'   : false,
      'order'       : [[0,'desc']],
      'pageLength'  : eventsRows,

      'columnDefs'  : [
          {   orderData: [1], targets:  [0]   },
          {   visible:   false, targets: [1]  },
          {
              targets: [0],
              'createdCell': function (td, cellData, rowData, row, col) {
                  $(td).html(translateHTMLcodes((cellData)));
              }
          }
      ],

      'processing'  : true,
      'language'    : {
          processing: '<table><td width="130px" align="middle"><?= lang("DevDetail_Loading");?></td>'+
                      '<td><i class="fa-solid fa-spinner fa-spin-pulse"></i></td></table>',
          emptyTable: 'No data',
          "lengthMenu": "<?= lang('Events_Tablelenght');?>",
          "search":     "<?= lang('Events_Searchbox');?>: ",
          "paginate": {
              "next":     "<?= lang('Events_Table_nav_next');?>",
              "previous": "<?= lang('Events_Table_nav_prev');?>"
          },
          "info": "<?= lang('Events_Table_info');?>",
      }
  });
}

// -----------------------------------------------
// INIT with polling for panel element visibility
// -----------------------------------------------

var eventsPageInitialized = false;

function initDeviceEventsPage()
{
  // Only proceed if .plugin-content is visible
  if (!$('#panEvents:visible').length) {
    return; // exit early if nothing is visible
  }

  // Only proceed if mac is available
  if (!getMac()) {
    return; // exit early if mac is not yet set
  }

  // init page once
  if (eventsPageInitialized) return; //  ENSURE ONCE
  eventsPageInitialized = true;

  showSpinner();

  var eventsRows          = 10;
  var eventsHide          = true;

  initializeEventsDatatable(eventsRows);
  loadEventsData();
}

// -----------------------------------------------------------------------------
// Recurring function to monitor the URL and reinitialize if needed
function deviceEventsPageUpdater() {
  initDeviceEventsPage();

  // Run updater again after delay
  setTimeout(deviceEventsPageUpdater, 200);
}

deviceEventsPageUpdater();


</script>