<!--
#---------------------------------------------------------------------------------#
#  NetAlertX                                                                       #
#  Open Source Network Guard / WIFI & LAN intrusion detector                      #
#                                                                                 #
#  presence.php - Front module. Device Presence calendar page                     #
#---------------------------------------------------------------------------------#
#    Puche      2021        pi.alert.application@gmail.com   GNU GPLv3            #
#    jokob-sk   2022        jokob.sk@gmail.com               GNU GPLv3            #
#    leiweibau  2022        https://github.com/leiweibau     GNU GPLv3            #
#    cvc90      2023        https://github.com/cvc90         GNU GPLv3            #
#---------------------------------------------------------------------------------#
-->

<?php
  require 'php/templates/header.php';
?>

<script>
  showSpinner();
</script>

<!-- Page ------------------------------------------------------------------ -->
  <div class="content-wrapper">

<!-- Main content ---------------------------------------------------------- -->
    <section class="content">

<!-- top small box 1 ------------------------------------------------------- -->
      <div class="row">

        <div class="col-lg-2 col-sm-4 col-xs-6">
          <a href="#" onclick="javascript: getDevicesPresence('all');">
          <div class="small-box bg-aqua">
            <div class="inner"><h3 id="devicesAll"> -- </h3>
                <p class="infobox_label"><?= lang('Presence_Shortcut_AllDevices');?></p>
            </div>
            <div class="icon"><i class="fa fa-laptop text-aqua-40"></i></div>
          </div>
          </a>
        </div>

<!-- top small box 2 ------------------------------------------------------- -->
        <div class="col-lg-2 col-sm-4 col-xs-6">
          <a href="#" onclick="javascript: getDevicesPresence('connected');">
            <div class="small-box bg-green">
              <div class="inner"> <h3 id="devicesConnected"> -- </h3>
                  <p class="infobox_label"><?= lang('Presence_Shortcut_Connected');?></p>
              </div>
              <div class="icon"> <i class="fa fa-plug text-green-40"></i> </div>
            </div>
          </a>
        </div>

<!-- top small box 3 ------------------------------------------------------- -->
        <div class="col-lg-2 col-sm-4 col-xs-6">
          <a href="#" onclick="javascript: getDevicesPresence('favorites');">
            <div  class="small-box bg-yellow">
              <div class="inner"> <h3 id="devicesFavorites"> -- </h3>
                <p class="infobox_label"><?= lang('Presence_Shortcut_Favorites');?></p>
              </div>
              <div class="icon"> <i class="fa fa-star text-yellow-40"></i> </div>
            </div>
          </a>
        </div>

<!-- top small box 4 ------------------------------------------------------- -->
        <div class="col-lg-2 col-sm-4 col-xs-6">
          <a href="#" onclick="javascript: getDevicesPresence('new');">
            <div  class="small-box bg-yellow">
              <div class="inner"> <h3 id="devicesNew"> -- </h3>
                <p class="infobox_label"><?= lang('Presence_Shortcut_NewDevices');?></p>
              </div>
              <div class="icon"> <i class="fa-solid fa-circle-plus text-yellow-40"></i> </div>
            </div>
          </a>
        </div>

<!-- top small box 5 ------------------------------------------------------- -->
        <div class="col-lg-2 col-sm-4 col-xs-6">
          <a href="#" onclick="javascript: getDevicesPresence('down');">
            <div  class="small-box bg-red">
              <div class="inner"> <h3 id="devicesDown"> -- </h3>
                <p class="infobox_label"><?= lang('Presence_Shortcut_DownAlerts');?></p>
              </div>
              <div class="icon"> <i class="fa fa-warning text-red-40"></i> </div>
            </div>
          </a>
        </div>

<!-- top small box 6 ------------------------------------------------------- -->
        <div class="col-lg-2 col-sm-4 col-xs-6">
          <a href="#" onclick="javascript: getDevicesPresence('archived');">
            <div  class="small-box bg-gray top_small_box_gray_text">
              <div class="inner"> <h3 id="devicesHidden"> -- </h3>
                <p class="infobox_label"><?= lang('Presence_Shortcut_Archived');?></p>
              </div>
              <div class="icon"> <i class="fa fa-eye-slash text-gray-40"></i> </div>
            </div>
          </a>
        </div>

      </div>

<!-- Activity Chart ------------------------------------------------------- -->
      <div class="row">
          <div class="col-md-12">
          <div class="box" id="clients">
              <div class="box-header with-border">
                <h3 class="box-title"><?= lang('Device_Shortcut_OnlineChart');?></h3>
              </div>
              <div class="box-body">
                <div class="chart">
                  <script src="lib/chart.js/Chart.js"></script>
                  <!-- presence chart -->
                  <?php
                      require 'php/components/graph_online_history.php';
                  ?>
                </div>
              </div>
              <!-- /.box-body -->
            </div>
          </div>
      </div>

      <!-- /.row -->

<!-- Calendar -------------------------------------------------------------- -->
      <div class="row">
        <div class="col-lg-12 col-sm-12 col-xs-12">
          <div id="tableDevicesBox" class="box" style="min-height: 500px">

            <!-- box-header -->
            <div class="box-header">
              <h3 id="tableDevicesTitle" class="box-title text-gray">Devices</h3>
              <div class="presencenceKey">
                <span class="question" title="<?= lang('Presence_Key_OnlineNow_desc');?>">
                  <div class="presenceOnlineNow presenceKeyBoxes"></div> <?= lang('Presence_Key_OnlineNow');?>
                </span>
                <span class="question" title="<?= lang('Presence_Key_OnlinePast_desc');?>">
                  <div class="presenceOnlinePast presenceKeyBoxes"></div> <?= lang('Presence_Key_OnlinePast');?>
                </span>
                <span class="question" title="<?= lang('Presence_Key_OnlinePastMiss_desc');?>">
                  <div class="presenceOnlinePastMiss presenceKeyBoxes"></div> <?= lang('Presence_Key_OnlinePastMiss');?>
                </span>
              </div>
            </div>

            <!-- box-body -->
            <div class="box-body table-responsive">

              <!-- Calendar -->
              <div id="calendar"></div>
            </div>

          </div>
          <!-- /.box -->
        </div>
        <!-- /.col -->
      </div>
      <!-- /.row -->

<!-- ----------------------------------------------------------------------- -->
    </section>
    <!-- /.content -->
  </div>
  <!-- /.content-wrapper -->


<!-- ----------------------------------------------------------------------- -->
<?php
  require 'php/templates/footer.php';
?>


<!-- ----------------------------------------------------------------------- -->
<!-- fullCalendar -->
  <link rel="stylesheet" href="lib/fullcalendar/fullcalendar.min.css">
  <link rel="stylesheet" href="lib/fullcalendar/fullcalendar.print.min.css" media="print">
  <script src="lib/moment/moment.js"></script>
  <script src="lib/fullcalendar/fullcalendar.min.js"></script>
  <script src="lib/fullcalendar/locale-all.js"></script>

<!-- fullCalendar Scheduler -->
  <link href="lib/fullcalendar-scheduler/scheduler.min.css" rel="stylesheet">
  <script src="lib/fullcalendar-scheduler/scheduler.min.js"></script>

<!-- Dark-Mode Patch -->
<?php
switch ($UI_THEME) {
  case "Dark":
    echo '<link rel="stylesheet" href="css/dark-patch-cal.css">';
    break;
  case "System":
    echo '<link rel="stylesheet" href="css/system-dark-patch-cal.css">';
    break;
}
?>

<!-- page script ----------------------------------------------------------- -->
<script>

  var deviceStatus = 'all';

  // Read parameters & Initialize components
  main();


// -----------------------------------------------------------------------------
function main () {
  // Initialize components
  $(function () {
    initializeCalendar();
    getDevicesTotals();
    getDevicesPresence(deviceStatus);
  });

  // Force re-render calendar on tab change (bugfix for render error at left panel)
  $(document).on('shown.bs.tab', 'a[data-toggle="tab"]', function (nav) {
    if ($(nav.target).attr('href') == '#panPresence') {
      $('#calendar').fullCalendar('rerenderEvents');
    }
  });
}


// -----------------------------------------------------------------------------
function initializeCalendar () {
  $('#calendar').fullCalendar({
    header: {
      left            : 'prev,next today',
      center          : 'title',
      right           : 'timelineYear,timelineMonth,timelineWeek,timelineDay'
    },
    defaultView       : 'timelineWeek',
    height            : 'auto',
    firstDay          : 1,
    allDaySlot        : false,
    timeFormat        : 'H:mm',

    resourceLabelText : '<?= lang('Presence_CallHead_Devices');?>',
    resourceAreaWidth : '160px',
    slotWidth         : '1px',

    resourceOrder     : '-favorite,title',
    locale            : '<?= lang('Presence_CalHead_lang');?>',

    //schedulerLicenseKey: 'CC-Attribution-NonCommercial-NoDerivatives',
    schedulerLicenseKey: 'GPL-My-Project-Is-Open-Source',

    views: {
      timelineYear: {
        type              : 'timeline',
        duration          : { year: 1 },
        buttonText        : '<?= lang('Presence_CalHead_year');?>',
        slotLabelFormat   : 'MMM',
        // Hack to show partial day events not as fullday events
        slotDuration      : {minutes: 44641}
      },

      timelineQuarter: {
        type              : 'timeline',
        duration          : { month: 3 },
        buttonText        : '<?= lang('Presence_CalHead_quarter');?>',
        slotLabelFormat   : 'MMM',
        // Hack to show partial day events not as fullday events
        slotDuration      : {minutes: 44641}
      },

      timelineMonth: {
        type              : 'timeline',
        duration          : { month: 1 },
        buttonText        : '<?= lang('Presence_CalHead_month');?>',
        slotLabelFormat   : 'D',
        // Hack to show partial day events not as fullday events
        slotDuration      : '24:00:01'
      },

      timelineWeek: {
        type              : 'timeline',
        duration          : { week: 1 },
        buttonText        : '<?= lang('Presence_CalHead_week');?>',
        slotLabelFormat   : 'D',
        slotDuration      : '24:00:01'
      },
      timelineDay: {
        type              : 'timeline',
        duration          : { day: 1 },
        buttonText        : '<?= lang('Presence_CalHead_day');?>',
        slotLabelFormat   : 'H',
        slotDuration      : '00:30:00'
      }
    },

    // Needed due hack partial day events 23:59:59
    dayRender: function (date, cell) {
      if ($('#calendar').fullCalendar('getView').name == 'timelineYear') {
        cell.removeClass('fc-sat');
        cell.removeClass('fc-sun');
        return;
      };

      if (date.day() == 0) {
        cell.addClass('fc-sun'); };

      if (date.day() == 6) {
        cell.addClass('fc-sat'); };

      if (date.format('YYYY-MM-DD') == moment().format('YYYY-MM-DD')) {
          cell.addClass ('fc-today'); };

      if ($('#calendar').fullCalendar('getView').name == 'timelineDay') {
        cell.removeClass('fc-sat');
        cell.removeClass('fc-sun');
        cell.removeClass('fc-today');
        if (date.format('YYYY-MM-DD HH') == moment().format('YYYY-MM-DD HH')) {
          cell.addClass('fc-today');
        }
      };
    },

    resourceRender: function (resourceObj, labelTds, bodyTds) {
      labelTds.find('span.fc-cell-text').html (
      '<b><a href="deviceDetails.php?mac='+ resourceObj.id+ '" class="">'+ encodeSpecialChars(resourceObj.title) +'</a></b>');

      // Resize heihgt
      // $(".fc-content table tbody tr .fc-widget-content div").addClass('fc-resized-row');
    },

    eventRender: function (event, element, view) {
      // $(element).tooltip({container: 'body', placement: 'bottom', title: event.tooltip});
      tltp = event.tooltip.replace('\n',' | ')

      element.attr ('title', tltp);  // Alternative tooltip

    },

    eventClick: function(info) {
      console.log(info);
    },

    loading: function( isLoading, view ) {
        if (isLoading) {
          showSpinner();
        } else {
          hideSpinner();
        }
    }

  })
}


// -----------------------------------------------------------------------------
/**
 * Fetch device totals from the API and update dashboard counters.
 *
 * This function:
 *  - Stops the automatic refresh timer
 *  - Calls the `/devices/totals` API endpoint using Bearer token authentication
 *  - Updates the device summary boxes (all, connected, favorites, new, down, archived)
 *  - Restarts the refresh timer after completion
 *
 * Expected API response format:
 *   [
 *     devices,     // Total devices
 *     connected,   // Currently connected devices
 *     favorites,   // Favorite devices
 *     new,         // Newly discovered devices
 *     down,        // Devices marked as down
 *     archived     // Archived / hidden devices
 *   ]
 */
function getDevicesTotals () {
  // stop timer
  stopTimerRefreshData();

  const apiToken   = getSetting("API_TOKEN");
  const apiBaseUrl = getApiBase();
  const totalsUrl  = `${apiBaseUrl}/devices/totals`;

  $.ajax({
    url: totalsUrl,
    method: "GET",
    headers: {
      "Authorization": `Bearer ${apiToken}`
    },
    success: function (totalsDevices) {

      $('#devicesAll').html        (totalsDevices[0].toLocaleString());
      $('#devicesConnected').html  (totalsDevices[1].toLocaleString());
      $('#devicesFavorites').html  (totalsDevices[2].toLocaleString());
      $('#devicesNew').html        (totalsDevices[3].toLocaleString());
      $('#devicesDown').html       (totalsDevices[4].toLocaleString());
      $('#devicesHidden').html     (totalsDevices[5].toLocaleString());

      // Timer for refresh data
      newTimerRefreshData(getDevicesTotals);
    },
    error: function (xhr) {
      console.error("Failed to load device totals:", xhr.responseText);

      // Ensure refresh loop continues even on failure
      newTimerRefreshData(getDevicesTotals);
    }
  });
}



// -----------------------------------------------------------------------------
function getDevicesPresence (status) {
  // Save status selected
  deviceStatus = status;

  // Defini color & title for the status selected
  switch (deviceStatus) {
    case 'all':        tableTitle = '<?= lang('Presence_Shortcut_AllDevices');?>';    color = 'aqua';    break;
    case 'connected':  tableTitle = '<?= lang('Presence_Shortcut_Connected');?>';     color = 'green';   break;
    case 'favorites':  tableTitle = '<?= lang('Presence_Shortcut_Favorites');?>';     color = 'yellow';  break;
    case 'new':        tableTitle = '<?= lang('Presence_Shortcut_NewDevices');?>';    color = 'yellow';  break;
    case 'down':       tableTitle = '<?= lang('Presence_Shortcut_DownAlerts');?>';    color = 'red';     break;
    case 'archived':   tableTitle = '<?= lang('Presence_Shortcut_Archived');?>';      color = 'gray';    break;
    default:           tableTitle = '<?= lang('Presence_Shortcut_Devices');?>';       color = 'gray';    break;
  }

  period = "7 days"

  // Calculate startDate and endDate based on the period
  let startDate = "";
  let endDate = new Date().toISOString().slice(0, 10);  // Today's date in ISO format (YYYY-MM-DD)

  // Calculate startDate based on period
  switch (period) {
    case "7 days":
      startDate = new Date();
      startDate.setDate(startDate.getDate() - 7);  // Subtract 7 days
      startDate = startDate.toISOString().slice(0, 10);  // Convert to ISO format
      break;
    case "1 month":
      startDate = new Date();
      startDate.setMonth(startDate.getMonth() - 1);  // Subtract 1 month
      startDate = startDate.toISOString().slice(0, 10);  // Convert to ISO format
      break;
    case "1 year":
      startDate = new Date();
      startDate.setFullYear(startDate.getFullYear() - 1);  // Subtract 1 year
      startDate = startDate.toISOString().slice(0, 10);  // Convert to ISO format
      break;
    default:
      console.error("Invalid period selected");
  }

  // Set title and color
  $('#tableDevicesTitle')[0].className = 'box-title text-'+ color;
  $('#tableDevicesBox')[0].className = 'box box-'+ color;
  $('#tableDevicesTitle').html (tableTitle);

  const apiToken = getSetting("API_TOKEN");

  const apiBaseUrl = getApiBase();

  // -----------------------------
  // Load Devices as Resources
  // -----------------------------
  const devicesUrl = `${apiBaseUrl}/devices/by-status?status=${deviceStatus}`;

  $.ajax({
    url: devicesUrl,
    method: "GET",
    headers: {
      "Authorization": `Bearer ${apiToken}`
    },
    success: function(devices) {
      // FullCalendar expects resources array
      const resources = devices.map(dev => ({
        id: dev.devMac,
        title: dev.devName
      }));

      $('#calendar').fullCalendar('option', 'resources', resources);
      $('#calendar').fullCalendar('refetchResources');
    }
  });

  // -----------------------------
  // Load Events
  // -----------------------------
  const eventsUrl = `${apiBaseUrl}/sessions/calendar?start=${startDate}&end=${endDate}`;

  $('#calendar').fullCalendar('removeEventSources');
  $('#calendar').fullCalendar('addEventSource', {
    url: eventsUrl,
    method: "GET",
    headers: {
      "Authorization": `Bearer ${apiToken}`
    },
    success: function(response) {
      // Flask returns { "sessions": [...] } → FullCalendar needs array
      const events = response.sessions || [];
      $('#calendar').fullCalendar('removeEvents');
      $('#calendar').fullCalendar('renderEvents', events, true);
    },
    error: function(err) {
      console.error('Failed to load events:', err);
    }
  });
};



</script>
