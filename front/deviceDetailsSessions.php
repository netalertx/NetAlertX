<?php
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once  $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
?>

<!-- ----------------------------------------------------------------------- -->


<!-- Datatable Session -->
<table id="tableSessions" class="table table-bordered table-hover table-striped ">
    <thead>
    <tr>
    <th><?= lang('DevDetail_SessionTable_Order');?></th>
    <th><?= lang('DevDetail_SessionTable_Connection');?></th>
    <th><?= lang('DevDetail_SessionTable_Disconnection');?></th>
    <th><?= lang('DevDetail_SessionTable_Duration');?></th>
    <th><?= lang('DevDetail_SessionTable_IP');?></th>
    <th><?= lang('DevDetail_SessionTable_Additionalinfo');?></th>
    </tr>
    </thead>
</table>


<script>



function initializeSessionsDatatable (sessionsRows) {
  // Sessions datatable
  $('#tableSessions').DataTable({
    'paging'      : true,
    'lengthChange': true,
    'lengthMenu'   : [[10, 25, 50, 100, 500, -1], [10, 25, 50, 100, 500, 'All']],
    'searching'   : true,
    'ordering'    : true,
    'info'        : true,
    'autoWidth'   : false,
    'order'       : [[0,'desc'], [1,'desc']],

    // Parameters
    'pageLength'  : sessionsRows,

    'columnDefs'  : [
        {visible:   false,  targets: [0]},

        // Replace HTML codes
        {targets: [3,5],
          'createdCell': function (td, cellData, rowData, row, col) {
            $(td).html (translateHTMLcodes (cellData));
        } },
          // Date
        {targets: [1,2],
          "createdCell": function (td, cellData, rowData, row, col) {
            // console.log(cellData);

            if (!cellData.includes("missing event") && !cellData.includes("..."))
            {
              // console.log(cellData);
              result = localizeTimestamp(cellData);
            } else
            {
              result = translateHTMLcodes(cellData)
            }

            $(td).html (result);
        } }
    ],

    // Processing
    'processing'  : true,
    'language'    : {
      processing: '<table><td width="130px" align="middle"><?= lang("DevDetail_Loading");?></td>'+
                  '<td><i class="fa-solid fa-spinner fa-spin-pulse"></i>'+
                  '</td></table>',
      emptyTable: 'No data',
      "lengthMenu": "<?= lang('Events_Tablelenght');?>",
      "search":     "<?= lang('Events_Searchbox');?>: ",
      "paginate": {
          "next":       "<?= lang('Events_Table_nav_next');?>",
          "previous":   "<?= lang('Events_Table_nav_prev');?>"
      },
      "info":           "<?= lang('Events_Table_info');?>",
    }
  });
}



// -----------------------------------------------
// INIT with polling for panel element visibility
// -----------------------------------------------

// -----------------------------------------------------------
// Init datatable
function loadSessionsData() {
  const table = $('#tableSessions').DataTable();
  let period = $("#period").val()

  showSpinner();

  // Build API base
  const apiToken = getSetting("API_TOKEN");

  const apiBaseUrl = getApiBase();
  const url = `${apiBaseUrl}/sessions/${getMac()}?period=${encodeURIComponent(period)}`;

  // Call API with Authorization header
  $.ajax({
    url: url,
    method: "GET",
    headers: {
      "Authorization": `Bearer ${apiToken}`
    },
    success: function (data) {
      table.clear();

      if (data.success && data.sessions.length) {
        data.sessions.forEach(session => {
          table.row.add([
            session.sesDateTimeOrder,
            session.sesConnection,
            session.sesDisconnection,
            session.sesDuration,
            session.sesIp,
            session.sesInfo
          ]);
        });
      }

      table.draw();
      hideSpinner();
    },
    error: function (xhr, status, err) {
      console.error("Failed to load sessions:", err, xhr.responseText);
      hideSpinner();
    }
  });
}


var sessionsPageInitialized = false;

// -----------------------------------------------------------
// Main init function
function initDeviceSessionsPage()
{
  // Only proceed if .plugin-content is visible
  if (!$('#panSessions:visible').length) {
    return; // exit early if nothing is visible
  }

  // init page once
  if (sessionsPageInitialized) return;
  sessionsPageInitialized = true;

  showSpinner();

  var sessionsRows        = 10;

  initializeSessionsDatatable(sessionsRows);
  loadSessionsData();
}

// -----------------------------------------------------------------------------
// Recurring function to monitor the URL and reinitialize if needed
function deviceSessionsPageUpdater() {
  initDeviceSessionsPage();

  // Run updater again after delay
  setTimeout(deviceSessionsPageUpdater, 200);
}

// start updater
deviceSessionsPageUpdater();

</script>