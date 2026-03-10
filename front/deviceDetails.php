<!--
#---------------------------------------------------------------------------------#
#  NetAlertX                                                                       #
#  Open Source Network Guard / WIFI & LAN intrusion detector                      #
#                                                                                 #
#  deviceDetails.php - Front module. Device management page                       #
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

<!-- Content header--------------------------------------------------------- -->
    <section class="content-header">
      <?php require 'php/templates/modals.php'; ?>

      <h1 id="pageTitle">
        &nbsp<small>Quering device info...</small>
      </h1>

      <div id="devicePageInfoPlc" class="card-body bg-light">
          <div class="small-box panel  rounded">
              <div class="inner text-center">

              </div>
          </div>
      </div>

      <!-- period selector -->
      <span class="breadcrumb" style="top: 0px;">
        <select class="form-control" id="period" onchange="javascript: periodChanged();">
          <option value="1 day"><?= lang('DevDetail_Periodselect_today');?></option>
          <option value="7 days"><?= lang('DevDetail_Periodselect_LastWeek');?></option>
          <option value="1 month" selected><?= lang('DevDetail_Periodselect_LastMonth');?></option>
          <option value="1 year"><?= lang('DevDetail_Periodselect_LastYear');?></option>
          <option value="100 years"><?= lang('DevDetail_Periodselect_All');?></option>
        </select>
      </span>
    </section>

<!-- Main content ---------------------------------------------------------- -->
    <section class="content">

      <div id="TopSmallBoxes"></div>

<!-- tab control------------------------------------------------------------ -->
      <div class="row">
        <div class="col-lg-12 col-sm-12 col-xs-12">
        <!-- <div class="box-transparent"> -->
          <div id="navDevice" class="nav-tabs-custom">
            <ul class="nav nav-tabs" style="font-size:16px;">
              <li>
                <a id="tabDetails"  href="#panDetails"  data-toggle="tab">
                  <i class="fa fa-info-circle"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('DevDetail_Tab_Details');?>
                    </span>
                </a>
                </li>
                <li>
                <a id="tabTools"    href="#panTools"    data-toggle="tab">
                  <i class="fa fa-screwdriver-wrench"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('DevDetail_Tab_Tools');?>
                    </span>
                </a>
                </li>
              <li>
                <a id="tabSessions" href="#panSessions" data-toggle="tab">
                  <i class="fa fa-list-ol"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('DevDetail_Tab_Sessions');?>
                    </span>
                </a>
                </li>
              <li>
                <a id="tabPresence" href="#panPresence" data-toggle="tab">
                  <i class="fa fa-calendar"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('DevDetail_Tab_Presence');?>
                    </span>
                </a>
                </li>
              <li>
                <a id="tabEvents"   href="#panEvents"   data-toggle="tab">
                  <i class="fa fa-bolt"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('DevDetail_Tab_Events');?>
                    </span>
                </a>
                </li>
              <li>
                <a id="tabPlugins"  href="#panPlugins"  data-toggle="tab">
                  <i class="fa fa-plug"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('DevDetail_Tab_Plugins');?>
                    </span>
                </a>
                </li>

              <div class="btn-group pull-right">
                <button type="button" class="btn btn-default"  style="padding: 10px; min-width: 30px;"
                  id="btnPrevious" onclick="recordSwitch('prev')"> <i class="fa fa-chevron-left"></i> </button>

                <div class="btn pa-btn-records"  style="padding: 10px; min-width: 30px; margin-left: 1px;"
                  id="txtRecord"     > 0 / 0 </div>

                <button type="button" class="btn btn-default"  style="padding: 10px; min-width: 30px; margin-left: 1px;"
                  id="btnNext"     onclick="recordSwitch('next')"> <i class="fa fa-chevron-right"></i> </button>
              </div>
            </ul>

            <div class="tab-content spinnerTarget" style="min-height: 430px;">

<!-- tab page 1 ------------------------------------------------------------ -->

              <div class="tab-pane fade" id="panDetails">
                <?php
                  require 'deviceDetailsEdit.php';
                ?>
              </div>

<!-- tab page 2 ------------------------------------------------------------ -->
              <div class="tab-pane fade table-responsive" id="panSessions">
              <?php
                  require 'deviceDetailsSessions.php';
                ?>
              </div>

<!-- tab page "Tools" ------------------------------------------------------------ -->

              <div class="tab-pane fade" id="panTools">
                <?php
                  require 'deviceDetailsTools.php';
                ?>
              </div>

<!-- tab page 3 ------------------------------------------------------------ -->
              <div class="tab-pane fade table-responsive" id="panPresence">
                <?php
                  // Include the other page
                  include 'deviceDetailsPresence.php';
                ?>
              </div>

<!-- tab page 4 ------------------------------------------------------------ -->
              <div class="tab-pane fade table-responsive" id="panEvents">
              <?php
                  // Include the other page
                  include 'deviceDetailsEvents.php';
                ?>
              </div>

<!-- tab page 7 ------------------------------------------------------------ -->
              <div class="tab-pane fade table-responsive" id="panPlugins">
                <?php
                  // Include the other page
                  include 'pluginsCore.php';
                ?>
              </div>

            </div>
            <!-- /.tab-content -->
          </div>
          <!-- /.nav-tabs-custom -->

          <!-- </div> -->
        </div>
        <!-- /.col -->
      </div>
      <!-- /.row -->

    </section>
    <!-- /.content -->
  </div>
  <!-- /.content-wrapper -->


<!-- ----------------------------------------------------------------------- -->
<?php
  require 'php/templates/footer.php';
?>


  <!-- ----------------------------------------------------------------------- -->

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
<script >

  // ------------------------------------------------------------

  mac                     = getMac()  // can also be rowID!! not only mac
  var devicesList         = [];   // this will contain a list the database row IDs of the devices ordered by the position displayed in the UI

  var pos                 = -1;
  var parPeriod           = 'Front_Details_Period';

  var tab                 = 'tabDetails'
  var selectedTab         = 'tabDetails';
  var emptyArr            = ['undefined', "", undefined, null];

// -----------------------------------------------------------------------------
function main () {

  // Initialize MAC
  var urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has ('mac') == true) {
    mac = urlParams.get ('mac');
    setCache("naxDeviceDetailsMac", mac); // set cookie
  } else {
    $('#pageTitle').html ('Device not found');
  }

  key ="activeDevicesTab"

  // Activate panel
  if(!emptyArr.includes(getCache(key)))
  {
    selectedTab = getCache(key);
  }

  tab = selectedTab;

  period = '1 day';
  sessionsRows = 50;
  eventsRows = 50;
  // $('#chkHideConnectionEvents')[0].checked = eval(eventsHide == 'true');

  // Initialize components with parameters


  // Init tabs once DOM ready
  $( document ).ready(function() {
    initializeTabs();
  });

}


// -----------------------------------------------------------------------------
function periodChanged () {
  loadSessionsData();
  loadPresenceData();
  loadEventsData();
}


// -----------------------------------------------------------------------------
// Left (prev) < > (next) Right toggles at the top right of device details to
// cycle between devices
function recordSwitch(direction) {

  if(somethingChanged)
  {
    showModalDefaultStrParam ('Unsaved changes', 'Do you want to discard your changes?',
      '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Okay');?>', performSwitch, direction);
  } else
  {
    performSwitch(direction)
  }
}


// ----------------------------------------
// Handle previous/next arrows/chevrons
function updateChevrons(currentMac) {
  const devicesList = getDevicesList();

  pos = devicesList.findIndex(item => item.devMac === currentMac);

  if (pos === -1) {
    console.warn('Device not found in cache. Re-caching devices...', currentMac);

    showSpinner();

    cacheDevices().then(() => {
      hideSpinner();

      // Retry after re-caching
      const refreshedList = getDevicesList();
      pos = refreshedList.findIndex(item => item.devMac === currentMac);

      if (pos === -1) {
        console.error('Still not found after re-cache:', currentMac);
        return;
      }

      console.log('Device found after re-cache:', refreshedList[pos]);
      // Proceed with using `refreshedList[pos]`
    }).catch((err) => {
      hideSpinner();
      console.error('Failed to cache devices:', err);
    });

    return;
  }

  // Update the record number display
  $('#txtRecord').html((pos + 1) + ' / ' + devicesList.length);

  // Enable/disable previous button
  if (pos <= 0) {
    $('#btnPrevious').attr('disabled', '');
    $('#btnPrevious').addClass('text-gray50');
  } else {
    $('#btnPrevious').removeAttr('disabled');
    $('#btnPrevious').removeClass('text-gray50');
  }

  // Enable/disable next button
  if (pos >= devicesList.length - 1) {
    $('#btnNext').attr('disabled', '');
    $('#btnNext').addClass('text-gray50');
  } else {
    $('#btnNext').removeAttr('disabled');
    $('#btnNext').removeClass('text-gray50');
  }
}

// -----------------------------------------------------------------------------

function performSwitch(direction)
{
  somethingChanged = false;

  devicesList = getDevicesList()

  // Update the global position in the devices list variable 'pos'
  if (direction === "next") {
    console.log("direction:" + direction);

    if (pos < devicesList.length) {
      pos++;
    }
  } else if (direction === "prev") {
    if (pos > 0) {
      pos--;
    }
  }

  // Get the new MAC address from devicesList
  mac = devicesList[pos].devMac.toString();

  setCache("naxDeviceDetailsMac", mac);

  // Update the query string with the new MAC and refresh the page
  const baseUrl = window.location.href.split('?')[0];
  window.location.href = `${baseUrl}?mac=${encodeURIComponent(mac)}`;

}

// -----------------------------------------------------------------------------
// Activate save & restore on any value change
$(document).on('input', 'input:text', function() {
  settingsChanged();
});

// -----------------------------------------------------------------------------

function initializeTabs () {
  initializeTabsShared({
    cacheKey:    'activeDevicesTab',
    defaultTab:  'tabDetails'
  });
}


//------------------------------------------------------------------------------
//  Render the small boxes on top
async function renderSmallBoxes() {

    try {
        // Show loading dialog
        showSpinner();

        // Get data from the server
        const apiToken = getSetting("API_TOKEN");

        const apiBaseUrl = getApiBase();
        // Ensure period is a string, not an element
        let periodValue = period;
        if (typeof period === 'object' && period !== null && 'value' in period) {
          periodValue = period.value;
        }
        const url = `${apiBaseUrl}/device/${getMac()}?period=${encodeURIComponent(periodValue)}`;

        const response = await fetch(url, {
          method: "GET",
          headers: {
            "Authorization": `Bearer ${apiToken}`,
            "Content-Type": "application/json"
          }
        });

        if (!response.ok) {
          const text = await response.text();
          throw new Error(`Error fetching device data: ${response.status} ${text}`);
        }

        const deviceData = await response.json();

        // Derive status card appearance from shared getStatusBadgeParts —
        // ensures icon, color, label and lang key are always in sync with the rest of the UI.
        const statusBadge = badgeFromDevice(deviceData);
        const statusText = statusBadge.label;

        // Prepare custom data
        const customData = [
            {
                "onclickEvent": "$('#tabDetails').trigger('click')",
                "color": statusBadge.cssClass,
                "headerId": "deviceStatus",
                "headerStyle": "margin-left: 0em",
                "labelLang": "DevDetail_Shortcut_CurrentStatus",
                "iconId": "deviceStatusIcon",
                "iconHtml": statusBadge.iconHtml,
                "dataValue": statusText
            },
            {
                "onclickEvent": "$('#tabSessions').trigger('click');",
                "color": "bg-green",
                "headerId": "deviceSessions",
                "headerStyle": "",
                "labelLang": "DevDetail_Shortcut_Sessions",
                "iconId": "",
                "iconClass": "fa fa-plug",
                "dataValue": deviceData.devSessions
            },
            {
                "onclickEvent": "$('#tabPresence').trigger('click')",
                "color": "bg-yellow",
                "headerId": "deviceEvents",
                "headerStyle": "margin-left: 0em",
                "labelLang": "DevDetail_Shortcut_Presence",
                "iconId": "deviceEventsIcon",
                "iconClass": "fa fa-calendar",
                "dataValue": `${deviceData.devPresenceHours ?? 0}h`
            },
            {
                "onclickEvent": "$('#tabEvents').trigger('click');",
                "color": "bg-red",
                "headerId": "deviceDownAlerts",
                "headerStyle": "",
                "labelLang": "DevDetail_Shortcut_DownAlerts",
                "iconId": "",
                "iconClass": "fa fa-warning",
                "dataValue": deviceData.devDownAlerts
            }
        ];

        // Send data to render small boxes
        const cardResponse = await fetch('php/components/device_cards.php', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ items: customData })
        });

        if (!cardResponse.ok) {
            throw new Error(`Error rendering small boxes: ${cardResponse.statusText}`);
        }

        const html = await cardResponse.text();

        $('#TopSmallBoxes').html(html);

    } catch (error) {
        console.error('Error in renderSmallBoxes:', error);
    } finally {
        // Hide loading dialog
        // hideSpinner();
    }
}

function updateDevicePageName(mac) {
  let name = getDevDataByMac(mac, "devName");
  let owner = getDevDataByMac(mac, "devOwner");

  // If data is missing, re-cache and retry once
  if (mac != 'new' && (name === null|| owner === null)) {
    console.warn("Device not found in cache, retrying after re-cache:", mac);
    showSpinner();
    cacheDevices().then(() => {
      hideSpinner();
      // Retry after successful cache
      updateDevicePageName(mac);
    }).catch((err) => {
      hideSpinner();
      console.error("Failed to refresh devices:", err);
    });
    return; // Exit early to avoid showing bad data
  }

  // Page title - Name
  let pageTitleText;

  if (mac === "new") {
      pageTitleText = getString("Gen_create_new_device");
      $('#pageTitle').html(
          `<i title="${pageTitleText}" class="fa fa-square-plus"></i> ` + pageTitleText
      );
      $('#devicePageInfoPlc .inner').html(
          `<i class="fa fa-circle-info"></i> ` + getString("Gen_create_new_device_info")
      );
      $('#devicePageInfoPlc').show();
  } else if (!owner || name.toString().includes(owner)) {
      pageTitleText = name;
      $('#pageTitle').html(pageTitleText);
      $('#devicePageInfoPlc').hide();
  } else {
      pageTitleText = `${name} (${owner})`;
      $('#pageTitle').html(pageTitleText);
      $('#devicePageInfoPlc').hide();
  }

  // Prepend to the <title> tag
  $('title').html(pageTitleText + ' - ' + $('title').html());
}


//-----------------------------------------------------------------------------------




window.onload = function() {
  // Always trigger app-init bootstrap
  if (typeof executeOnce === 'function') {
    executeOnce();
  }

  mac = getMac();

  // Wait for app initialization (cache populated) before using cached data
  callAfterAppInitialized(async () => {
    updateDevicePageName(mac);
    updateChevrons(mac);
    await renderSmallBoxes();
    main();
  });
}

</script>


