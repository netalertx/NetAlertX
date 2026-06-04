<?php
require 'php/templates/header.php';
?>

<script>
  showSpinner(); // Show initial page loading spinner
</script>

<div class="content-wrapper eventsPage">
  <section class="content">

    <!-- ---------------- Top small boxes (Event shortcuts) ---------------- -->
    <div class="row">
      <?php
        // Define the top shortcut boxes for different event types
        $eventBoxes = [
          ['id' => 'eventsAll', 'type' => 'all', 'label' => 'Events_Shortcut_AllEvents', 'color' => 'aqua', 'icon' => 'fa-bolt'],
          ['id' => 'eventsSessions', 'type' => 'sessions', 'label' => 'Events_Shortcut_Sessions', 'color' => 'green', 'icon' => 'fa-plug'],
          ['id' => 'eventsMissing', 'type' => 'missing', 'label' => 'Events_Shortcut_MissSessions', 'color' => 'yellow', 'icon' => 'fa-exchange'],
          ['id' => 'eventsVoided', 'type' => 'voided', 'label' => 'Events_Shortcut_VoidSessions', 'color' => 'yellow', 'icon' => 'fa-exclamation-circle'],
          ['id' => 'eventsNewDevices', 'type' => 'new', 'label' => 'Events_Shortcut_NewDevices', 'color' => 'yellow', 'icon' => 'fa-circle-plus'],
          ['id' => 'eventsDown', 'type' => 'down', 'label' => 'Events_Shortcut_DownAlerts', 'color' => 'red', 'icon' => 'fa-warning']
        ];

        foreach ($eventBoxes as $box) :
      ?>
        <div class="col-lg-2 col-sm-4 col-xs-6">
          <a href="#" onclick="getEvents('<?= $box['type'] ?>')">
            <div class="small-box bg-<?= $box['color'] ?>">
              <div class="inner">
                <h3 id="<?= $box['id'] ?>">--</h3>
                <p class="infobox_label"><?= lang($box['label']); ?></p>
              </div>
              <div class="icon">
                <i class="fa <?= $box['icon'] ?> text-<?= $box['color'] ?>-40"></i>
              </div>
            </div>
          </a>
        </div>
      <?php endforeach; ?>
    </div>

    <!-- ---------------- Events DataTable ---------------- -->
    <div class="row">
      <div class="col-xs-12">
        <div id="tableEventsBox" class="box">
          <div class="box-header col-xs-12">
            <h3 id="tableEventsTitle" class="box-title text-gray col-xs-10">Events</h3>
            <div class="eventsPeriodSelectWrap col-xs-2">
              <select class="form-control" id="period" onchange="periodChanged()">
                <option value="1 day"><?= lang('Events_Periodselect_today'); ?></option>
                <option value="7 days"><?= lang('Events_Periodselect_LastWeek'); ?></option>
                <option value="1 month" selected><?= lang('Events_Periodselect_LastMonth'); ?></option>
                <option value="1 year"><?= lang('Events_Periodselect_LastYear'); ?></option>
                <option value="100 years"><?= lang('Events_Periodselect_All'); ?></option>
              </select>
            </div>
          </div>

          <div class="box-body table-responsive">
            <table id="tableEvents" class="spinnerTarget table table-bordered table-hover table-striped">
              <thead>
                <tr>
                  <th><?= lang('Events_TableHead_Order'); ?></th>
                  <th><?= lang('Events_TableHead_Device'); ?></th>
                  <th><?= lang('Events_TableHead_Owner'); ?></th>
                  <th><?= lang('Events_TableHead_Date'); ?></th>
                  <th><?= lang('Events_TableHead_EventType'); ?></th>
                  <th><?= lang('Events_TableHead_Connection'); ?></th>
                  <th><?= lang('Events_TableHead_Disconnection'); ?></th>
                  <th><?= lang('Events_TableHead_Duration'); ?></th>
                  <th><?= lang('Events_TableHead_DurationOrder'); ?></th>
                  <th><?= lang('Events_TableHead_IP'); ?></th>
                  <th><?= lang('Events_TableHead_IPOrder'); ?></th>
                  <th><?= lang('Events_TableHead_AdditionalInfo'); ?></th>
                  <th>N/A</th>
                  <th>MAC</th>
                  <th><?= lang('Events_TableHead_PendingAlert'); ?></th>
                </tr>
              </thead>
            </table>
          </div>
        </div>
      </div>
    </div>

  </section>
</div>

<?php require 'php/templates/footer.php'; ?>

<script>
/* ---------------- Global Variables ---------------- */
const parPeriod = 'nax_parPeriod';
const parTableRows = 'nax_parTableRows';

let eventsType = 'all'; // Default type
let period = getCookie(parPeriod) || '1 day';
let tableRows = parseInt(getCookie(parTableRows) || getSetting("UI_DEFAULT_PAGE_SIZE"), 10);

main(); // Initialize page

/* ---------------- Main initialization ---------------- */
function main() {
  $('#period').val(period);
  initializeDatatable();
  getEventsTotals();
  getEvents(eventsType); // triggers first serverSide draw
}

/* ---------------- Initialize DataTable ---------------- */
function initializeDatatable() {
  const apiBase  = getApiBase();
  const apiToken = getSetting("API_TOKEN");

  $('#tableEvents').DataTable({
    processing:   true,
    serverSide:   true,
    paging:       true,
    lengthChange: true,
    lengthMenu:   getLengthMenu(getSetting("UI_DEFAULT_PAGE_SIZE")),
    searching:    true,
    ordering:     true,
    info:         true,
    autoWidth:    false,
    order:        [[0, "desc"]],
    pageLength:   tableRows,

    ajax: function (dtRequest, callback) {
      const page   = Math.floor(dtRequest.start / dtRequest.length) + 1;
      const limit  = dtRequest.length;
      const search = dtRequest.search?.value || '';
      const sortCol = dtRequest.order?.length ? dtRequest.order[0].column : 0;
      const sortDir = dtRequest.order?.length ? dtRequest.order[0].dir    : 'desc';

      const url = `${apiBase}/sessions/session-events`
        + `?type=${encodeURIComponent(eventsType)}`
        + `&period=${encodeURIComponent(period)}`
        + `&page=${page}`
        + `&limit=${limit}`
        + `&sortCol=${sortCol}`
        + `&sortDir=${sortDir}`
        + (search ? `&search=${encodeURIComponent(search)}` : '');

      $.ajax({
        url,
        method: "GET",
        dataType: "json",
        headers: { "Authorization": `Bearer ${apiToken}` },
        success: function (response) {
          callback({
            data:            response.data            || [],
            recordsTotal:    response.total           || 0,
            recordsFiltered: response.recordsFiltered || 0
          });
          hideSpinner();
        },
        error: function (xhr, status, error) {
          console.error("Error fetching session events:", status, error, xhr.responseText);
          callback({ data: [], recordsTotal: 0, recordsFiltered: 0 });
          hideSpinner();
        }
      });
    },

    columnDefs: [
      { targets: [0,5,6,7,8,10,11,12,13], visible: false },
      { targets: [7], orderData: [8] },
      { targets: [9], orderData: [10] },
      // Use `render` (not `createdCell`) so encodeSpecialChars runs before
      // DataTables sets td.innerHTML, preventing devName XSS execution.
      { targets: [1], render: function (data, type, row) {
          if (type !== 'display') { return data; }
          return `<b><a href="deviceDetails.php?mac=${row[13]}">${encodeSpecialChars(data)}</a></b>`;
      }},
      { targets: [3], createdCell: (td, cellData) => $(td).html(localizeTimestamp(cellData)) },
      { targets: [4,5,6,7], createdCell: (td, cellData) => $(td).html(translateHTMLcodes(cellData)) }
    ],

    language: {
      processing: '<table><td width="130px" align="middle"><?= lang("Events_Loading"); ?></td><td><i class="fa-solid fa-spinner fa-spin-pulse"></i></td></table>',
      emptyTable: 'No data',
      lengthMenu: "<?= lang('Events_Tablelenght'); ?>",
      search:     "<?= lang('Events_Searchbox'); ?>: ",
      paginate:   { next: "<?= lang('Events_Table_nav_next'); ?>", previous: "<?= lang('Events_Table_nav_prev'); ?>" },
      info:       "<?= lang('Events_Table_info'); ?>"
    }
  });

  // Save page length when changed
  $('#tableEvents').on('length.dt', function(e, settings, len) {
    setCookie(parTableRows, len);
  });
}

/* ---------------- Period filter changed ---------------- */
function periodChanged() {
  period = $('#period').val();
  setCookie(parPeriod, period);
  getEventsTotals();
  getEvents(eventsType);
}

/* ---------------- Fetch event totals ---------------- */
function getEventsTotals() {
  stopTimerRefreshData();

  // Build API URL
  const apiBase = getApiBase();
  const apiToken = getSetting("API_TOKEN");
  const url = `${apiBase}/sessions/totals?period=${encodeURIComponent(period)}`;

  $.ajax({
    url,
    method: "GET",
    dataType: "json",
    headers: { "Authorization": `Bearer ${apiToken}` },
    success: totalsEvents => {
      const ids = ['eventsAll','eventsSessions','eventsMissing','eventsVoided','eventsNewDevices','eventsDown'];
      ids.forEach((id, i) => $(`#${id}`).html(totalsEvents[i].toLocaleString()));
      newTimerRefreshData(getEventsTotals);
    },
    error: (xhr, status, error) => console.error("Error fetching totals:", status, error)
  });
}

/* ---------------- Switch event type and reload DataTable ---------------- */
function getEvents(type) {
  eventsType = type;
  const table = $('#tableEvents').DataTable();

  // Event type config: title, color, session columns visibility
  const config = {
    all:      {title: 'Events_Shortcut_AllEvents',    color: 'aqua',   sesionCols: false},
    sessions: {title: 'Events_Shortcut_Sessions',     color: 'green',  sesionCols: true},
    missing:  {title: 'Events_Shortcut_MissSessions', color: 'yellow', sesionCols: true},
    voided:   {title: 'Events_Shortcut_VoidSessions', color: 'yellow', sesionCols: false},
    new:      {title: 'Events_Shortcut_NewDevices',   color: 'yellow', sesionCols: false},
    down:     {title: 'Events_Shortcut_DownAlerts',   color: 'red',    sesionCols: false}
  }[type] || {title: 'Events_Shortcut_Events', color: '', sesionCols: false};

  // Update title and color
  $('#tableEventsTitle').attr('class', 'box-title text-' + config.color).html(getString(config.title));
  $('#tableEventsBox').attr('class', 'box box-' + config.color);

  // Toggle column visibility
  table.column(3).visible(!config.sesionCols);
  table.column(4).visible(!config.sesionCols);
  table.column(5).visible(config.sesionCols);
  table.column(6).visible(config.sesionCols);
  table.column(7).visible(config.sesionCols);

  showSpinner();
  table.ajax.reload(null, true); // reset to page 1
}
</script>
