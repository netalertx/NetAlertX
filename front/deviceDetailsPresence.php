<?php
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once  $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
?>

<!-- fullCalendar -->
 <?php require $_SERVER['DOCUMENT_ROOT'] . '/php/templates/skel_tab_presence.php'; ?>

<link rel="stylesheet" href="lib/fullcalendar/fullcalendar.min.css">

<!-- fullCalendar -->
  <link rel="stylesheet" href="lib/fullcalendar/fullcalendar.print.min.css" media="print">
  <script src="lib/moment/moment.js"></script>
  <script src="lib/fullcalendar/fullcalendar.min.js"></script>
  <script src="lib/fullcalendar/locale-all.js"></script>

<!-- fullCalendar Scheduler -->
  <link href="lib/fullcalendar-scheduler/scheduler.min.css" rel="stylesheet">
  <script src="lib/fullcalendar-scheduler/scheduler.min.js"></script>


<!-- Calendar -->
<div id="calendar">
</div>


<script>

  // Force re-render calendar on tab change
  // (bugfix for render error at left panel)
  $(document).on('shown.bs.tab', 'a[data-toggle="tab"]', function (nav) {
    if ($(nav.target).attr('href') == '#panPresence') {
      $('#calendar').fullCalendar('rerenderEvents');
    }
  });


  // ---------------------------------------
  // query data
  function loadPresenceData() {
    const apiToken = getSetting("API_TOKEN");

    const apiBaseUrl = getApiBase();
    const url = `${apiBaseUrl}/sessions/calendar`;

    $('#calendar').fullCalendar('removeEventSources');

    $('#calendar').fullCalendar('addEventSource', function(start, end, timezone, callback) {
      $.ajax({
        url: url,
        method: "GET",
        dataType: "json",
        headers: {
          "Authorization": `Bearer ${apiToken}`
        },
        data: {
          start: start.format('YYYY-MM-DD'),
          end: end.format('YYYY-MM-DD'),
          mac: mac
        },
        success: function(response) {
          if (response && response.success) {
            callback(response.sessions || []);
          } else {
            console.warn("Presence calendar API error:", response);
            callback([]);
          }
          hidePresenceTabSkeleton();
        },
        error: function(xhr) {
          console.error(
            "Presence calendar request failed:",
            xhr.status,
            xhr.responseText
          );
          callback([]);
          hidePresenceTabSkeleton();
        }
      });
    });
  }

// -----------------------------------------------------------------------------
function initializeCalendar() {
  $('#calendar').fullCalendar({
    editable          : false,
    droppable         : false,
    defaultView       : 'agendaMonth',
    schedulerLicenseKey: 'GPL-My-Project-Is-Open-Source',
    height            : 'auto',
    firstDay          : 1,
    allDaySlot        : false,
    slotDuration      : '02:00:00',
    slotLabelInterval : '04:00:00',
    slotLabelFormat   : 'H:mm',
    timeFormat        : 'H:mm',
    locale            : '<?= lang('Presence_CalHead_lang');?>',
    header: {
      left            : 'prev,next today',
      center          : 'title',
      right           : 'agendaYear,agendaMonth,agendaWeek'
    },

   views: {
      agendaYear: {
        type               : 'agenda',
        duration           : { year: 1 },
        buttonText         : '<?= lang('Presence_CalHead_year');?>',
        columnHeaderFormat : ''
      },

      agendaMonth: {
        type               : 'agenda',
        duration           : { month: 1 },
        buttonText         : '<?= lang('Presence_CalHead_month');?>',
        columnHeaderFormat : 'D'
      },
      agendaWeek: {
        buttonText         : '<?= lang('Presence_CalHead_week');?>',
      }
    },

    viewRender: function(view) {
      if (view.name === 'agendaYear') {
        var listHeader  = $('.fc-day-header')[0];
        var listContent = $('.fc-widget-content')[0];

        for (i=0; i < listHeader.length-2 ; i++) {
          listHeader[i].style.borderColor = 'transparent';
          listContent[i+2].style.borderColor = 'transparent';

          if (listHeader[i].innerHTML != '<span></span>') {
            if (i==0) {
              listHeader[i].style.borderLeftColor = '#808080';
            } else {
              listHeader[i-1].style.borderRightColor = '#808080';
              listContent[i+1].style.borderRightColor = '#808080';
            }
            listHeader[i].style.paddingLeft = '10px';
          }
        };
      }
    },

    columnHeaderText: function(mom) {
      switch ($('#calendar').fullCalendar('getView').name) {
        case 'agendaYear':
          if (mom.date() == 1) {
            return mom.format('MMM');
          } else {
            return '';
          }
          break;
        case 'agendaMonth':
          return mom.date();
          break;
        case 'agendaWeek':
          return mom.format ('ddd D');
          break;
        default:
          return mom.date();
        }
    },

    eventRender: function (event, element) {
      // $(element).tooltip({container: 'body', placement: 'bottom',  title: event.tooltip});
      element.attr ('title', event.tooltip);  // Alternative tooltip
    },

    loading: function( isLoading, view ) {
        if (isLoading) {
          showSpinner()
        } else {
          hideSpinner()
        }
    }

  })
}

// -----------------------------------------------
// INIT with polling for panel element visibility
// -----------------------------------------------

var presencePageInitialized = false;

function initDevicePresencePage() {
  // Only proceed if the Presence tab is visible
  if (!$('#panPresence:visible').length) {
    return; // Exit early if nothing is visible
  }

  // Ensure initialization only happens once
  if (presencePageInitialized) return;
  presencePageInitialized = true;

  showPresenceTabSkeleton();
  showSpinner();

  initializeCalendar();
  loadPresenceData();
}

// Recurring check to initialize when visible
function devicePresencePageUpdater() {
  initDevicePresencePage();

  setTimeout(devicePresencePageUpdater, 200);
}

devicePresencePageUpdater();

// -----------------------------------------------------------------------------
function hidePresenceTabSkeleton() {
  $('#skel-tab-presence').fadeOut(50, function() { $(this).hide(); });
}

function showPresenceTabSkeleton() {
  var $skel = $('#skel-tab-presence');
  $skel.stop(true, true).fadeIn(10);
}


</script>