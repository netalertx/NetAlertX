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
  const hideConnections = $('#chkHideConnectionEvents')[0].checked;
  const hideConnectionsStr = hideConnections ? 'true' : 'false';

  let period = $("#period").val();
  let { start, end } = getPeriodStartEnd(period);

  const rawSql = `
    SELECT eve_DateTime, eve_EventType, eve_IP, eve_AdditionalInfo
    FROM Events
    WHERE eve_MAC = "${mac}"
      AND eve_DateTime BETWEEN "${start}" AND "${end}"
      AND (
        (eve_EventType NOT IN ("Connected", "Disconnected", "VOIDED - Connected", "VOIDED - Disconnected"))
        OR "${hideConnectionsStr}" = "false"
      )
  `;

  const apiToken = getSetting("API_TOKEN");

  const apiBaseUrl = getApiBase();
  const url = `${apiBaseUrl}/dbquery/read`;

  $.ajax({
    url: url,
    method: "POST",
    contentType: "application/json",
    headers: {
      "Authorization": `Bearer ${apiToken}`
    },
    data: JSON.stringify({
      rawSql: btoa(rawSql)
    }),
    success: function (data) {
      // assuming read_query returns rows directly
      const rows = data["results"].map(row => {
        const rawDate = row.eve_DateTime;
        const formattedDate = rawDate ? localizeTimestamp(rawDate) : '-';

        return [
          formattedDate,
          row.eve_DateTime,
          row.eve_EventType,
          row.eve_IP,
          row.eve_AdditionalInfo
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