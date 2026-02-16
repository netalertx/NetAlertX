<?php
//------------------------------------------------------------------------------
// check if authenticated
require_once $_SERVER["DOCUMENT_ROOT"] . "/php/templates/security.php"; ?>


<div class="row" id="deviceDetailsEdit">
  <div class="box-body form-horizontal">
  <form id="edit-form">
  <!-- Form fields will be appended here -->
  </form>
  </div>
  <!-- Buttons -->
  <div class="col-xs-12">
  <div class="pull-right">
    <button type="button"
        class="btn btn-default pa-btn pa-btn-delete"
        style="margin-left:0px;"
        id="btnDelete"
        onclick="askDeleteDeviceByMac()">
          <i class="fas fa-trash-alt"></i>
          <?= lang("DevDetail_button_Delete") ?>
    </button>
    <button type="button"
        class="btn btn-primary pa-btn"
        style="margin-left:6px; "
        id="btnSave"
        onclick="setDeviceData()" >
          <i class="fas fa-save"></i>
          <?= lang("DevDetail_button_Save") ?>
    </button>
  </div>
  </div>
</div>


<script defer>

// Global variable to store device data for access by toggleFieldLock and other functions
let deviceData = {};

// -------------------------------------------------------------------
// Get plugin and settings data from API endpoints
function getDeviceData() {

  mac = getMac()

  console.log(mac);
  const apiToken = getSetting("API_TOKEN");
  let period = $("#period").val()

  const apiBaseUrl = getApiBase();
  const url = `${apiBaseUrl}/device/${mac}?period=${encodeURIComponent(period)}`;

  // get data from server
  $.ajax({
    url: url,
    method: "GET",
    headers: {
      "Authorization": `Bearer ${apiToken}`
    },
    dataType: "json",
    success: function(data) {
      // Assign to global variable for access by toggleFieldLock and other functions
      deviceData = data;

      // some race condition, need to implement delay
      setTimeout(() => {

        const query = `
        query($filters: [FilterOptionsInput]) {
          settings(filters: $filters) {
          settings {
            setKey
            setName
            setDescription
            setType
            setOptions
            setGroup
            setValue
            setEvents
            setOverriddenByEnv
          }
          count
          }
        }
        `;

        // I need to get a subset of settings only (performance improvement), but include both NEWDEV and CUSTPROP settings
        const variables = {
          filters: [
            { filterColumn: "setGroup", filterValue: "NEWDEV" },
            { filterColumn: "setGroup", filterValue: "CUSTPROP" }
          ]
        };

        const graphQlUrl = `${apiBaseUrl}/graphql`;

        $.ajax({
          url: graphQlUrl,
          method: "POST",
          contentType: "application/json",
          headers: { "Authorization": `Bearer ${apiToken}` },
          data: JSON.stringify({ query, variables }),
          success: function(response) {

            const settingsData = response.data.settings.settings;

            // columns to hide
            hiddenFields = ["NEWDEV_devScan", "NEWDEV_devPresentLastScan"]
            // columns to disable/readonly - conditional depending if a new dummy device is created
            disabledFields = mac == "new" ? ["NEWDEV_devLastNotification", "NEWDEV_devFirstConnection", "NEWDEV_devLastConnection"] : ["NEWDEV_devLastNotification", "NEWDEV_devFirstConnection", "NEWDEV_devLastConnection", "NEWDEV_devMac", "NEWDEV_devLastIP", "NEWDEV_devPrimaryIPv6", "NEWDEV_devPrimaryIPv4", "NEWDEV_devSyncHubNode", "NEWDEV_devFQDN"];

            // Fields that are tracked by authoritative handler and can be locked/unlocked
            const trackedFields = {
              "devMac": true,
              "devName": true,
              "devLastIP": true,
              "devVendor": true,
              "devFQDN": true,
              "devSSID": true,
              "devParentMAC": true,
              "devParentPort": true,
              "devParentRelType": true,
              "devVlan": true
            };

            // Grouping of fields into categories with associated documentation links
            const fieldGroups = {
              // Group for device main information
              DevDetail_MainInfo_Title: {
                data: ["devMac", "devLastIP", "devName", "devOwner", "devType", "devVendor", "devGroup", "devIcon", "devLocation", "devComments"],
                docs: "https://docs.netalertx.com/DEVICE_MANAGEMENT",
                iconClass: "fa fa-pencil",
                inputGroupClasses: "field-group main-group col-lg-4 col-sm-6 col-xs-12",
                labelClasses: "col-sm-4 col-xs-12 control-label",
                inputClasses: "col-sm-8 col-xs-12 input-group"
              },
              // Group for event and alert settings
              DevDetail_EveandAl_Title: {
                data: ["devAlertEvents", "devAlertDown", "devSkipRepeated", "devReqNicsOnline", "devChildrenNicsDynamic", "devForceStatus"],
                docs: "https://docs.netalertx.com/NOTIFICATIONS",
                iconClass: "fa fa-bell",
                inputGroupClasses: "field-group alert-group col-lg-4 col-sm-6 col-xs-12",
                labelClasses: "col-sm-4 col-xs-12 control-label",
                inputClasses: "col-sm-8 col-xs-12 input-group"
              },
              // Group for network details
              DevDetail_MainInfo_Network_Title: {
                data: ["devParentMAC", "devParentRelType", "devParentPort", "devSSID", "devSite", "devVlan", "devSyncHubNode"],
                docs: "https://docs.netalertx.com/NETWORK_TREE",
                iconClass: "fa fa-sitemap fa-rotate-270",
                inputGroupClasses: "field-group network-group col-lg-4 col-sm-6 col-xs-12",
                labelClasses: "col-sm-4 col-xs-12 control-label",
                inputClasses: "col-sm-8 col-xs-12 input-group"
              },
              // Group for other fields like static IP, archived status, etc.
              DevDetail_DisplayFields_Title: {
                data: ["devStaticIP", "devIsNew", "devFavorite", "devIsArchived"],
                docs: "https://docs.netalertx.com/DEVICE_DISPLAY_SETTINGS",
                iconClass: "fa fa-list-check",
                inputGroupClasses: "field-group display-group col-lg-4 col-sm-6 col-xs-12",
                labelClasses: "col-sm-4 col-xs-12 control-label",
                inputClasses: "col-sm-8 col-xs-12 input-group"
              },
              // Group for session information
              DevDetail_SessionInfo_Title: {
                data: ["devPrimaryIPv4", "devPrimaryIPv6", "devStatus", "devLastConnection", "devFirstConnection", "devFQDN"],
                docs: "https://docs.netalertx.com/SESSION_INFO",
                iconClass: "fa fa-calendar",
                inputGroupClasses: "field-group session-group col-lg-4 col-sm-6 col-xs-12",
                labelClasses: "col-sm-4 col-xs-12 control-label",
                inputClasses: "col-sm-8 col-xs-12 input-group"
              },
              // Group for Custom properties.
              DevDetail_CustomProperties_Title: {
                data: ["devCustomProps"],
                docs: "https://docs.netalertx.com/CUSTOM_PROPERTIES",
                iconClass: "fa fa-list",
                inputGroupClasses: "field-group cutprop-group col-lg-6 col-sm-12 col-xs-12",
                labelClasses: "col-sm-12 col-xs-12 control-label",
                inputClasses: "col-sm-12 col-xs-12 input-group"
              },
              // Group for Children.
              DevDetail_Children_Title: {
                data: ["devChildrenDynamic"],
                docs: "https://docs.netalertx.com/NETWORK_TREE",
                iconClass: "fa fa-list",
                inputGroupClasses: "field-group cutprop-group col-lg-6 col-sm-12 col-xs-12",
                labelClasses: "col-sm-12 col-xs-12 control-label",
                inputClasses: "col-sm-12 col-xs-12 input-group"
              },
            };

            // Filter settings data to get relevant settings
            const relevantSettings = settingsData.filter(set =>
              set.setGroup === "NEWDEV" && // Filter for settings in the "NEWDEV" group
              set.setKey.includes("_dev") && // Include settings with '_dev' in the key
              !hiddenFields.includes(set.setKey) && // Exclude settings listed in hiddenFields
              !set.setKey.includes("__metadata") // Exclude metadata fields
            );

            // Function to generate the form
            const generateSimpleForm = settings => {
              const form = $('#edit-form'); // Get the form element to append generated fields

              // Loop over each field group to generate sections for each category
              Object.entries(fieldGroups).forEach(([groupName, obj]) => {
                const groupDiv = $('<div>').addClass(obj.inputGroupClasses); // Create a div for each group with responsive Bootstrap classes

                // Add group title and documentation link
                groupDiv.append(`<h5><i class="${obj.iconClass}"></i>  ${getString(groupName)}
                    <span class="helpIconSmallTopRight">
                      <a target="_blank" href="${obj.docs}">
                        <i class="fa fa-circle-question"></i>
                      </a>
                    </span>
                  </h5>
                  <hr>
                  `);

                // Filter relevant settings for the current group
                const groupSettings = settings.filter(set => obj.data.includes(set.setKey.replace('NEWDEV_', '')));

                // Loop over each setting in the group to generate form fields
                groupSettings.forEach(setting => {
                  const column = $('<div>'); // Create a column for each setting (Bootstrap column)

                  // console.log(setting);

                  // Get the field data (replace 'NEWDEV_' prefix from the key)
                  fieldData = deviceData[setting.setKey.replace('NEWDEV_', '')]
                  fieldData = fieldData == null ? "" : fieldData;
                  fieldOptionsOverride = null;

                  // console.log(setting.setKey);
                  // console.log(fieldData);

                  // Additional form elements like the random MAC address button for devMac
                  let inlineControl = "";
                  // handle random mac
                  if (setting.setKey == "NEWDEV_devMac" && deviceData["devIsRandomMAC"] == true) {
                    inlineControl += `<span class="input-group-addon pointer"
                        title="${getString("RandomMAC_hover")}">
                        <a href="https://docs.netalertx.com/RANDOM_MAC" target="_blank">
                          <i class="fa-solid fa-shuffle"></i>
                        </a>
                      </span>`;
                  }
                  // handle FAKE mac
                  if (setting.setKey == "NEWDEV_devMac" && isFakeMac(deviceData["devMac"])) {
                    inlineControl += `<span class="input-group-addon"
                        title="${getString("FakeMAC_hover")}">
                          <i class="fa-solid fa-dice"></i>
                      </span>`;
                  }
                  // handle generate MAC for new device
                  if (setting.setKey == "NEWDEV_devMac" && deviceData["devMac"] == "") {
                    inlineControl += `<span class="input-group-addon pointer"
                        onclick="generate_NEWDEV_devMac()"
                        title="${getString("Gen_Generate")}">
                        <i class="fa-solid fa-dice" ></i>
                      </span>`;
                  }
                  // handle generate IP for new device
                  if (setting.setKey == "NEWDEV_devLastIP" && deviceData["devLastIP"] == "") {
                    inlineControl += `<span class="input-group-addon pointer"
                        onclick="generate_NEWDEV_devLastIP()"
                        title="${getString("Gen_Generate")}">
                        <i class="fa-solid fa-dice" ></i>
                      </span>`;
                  }

                  // timestamps
                  if (setting.setKey == "NEWDEV_devFirstConnection" || setting.setKey == "NEWDEV_devLastConnection") {
                    fieldData = localizeTimestamp(fieldData)
                  }

                  // Add lock/unlock icon button for tracked fields (not for new devices)
                  const fieldName = setting.setKey.replace('NEWDEV_', '');
                  if (trackedFields[fieldName] &&  !["devFQDN", "devMac", "devLastIP"].includes(fieldName) &&  mac != "new") {
                    const sourceField = fieldName + "Source";

                    const currentSource = deviceData[sourceField] || "N/A";
                    const isLocked = currentSource === "LOCKED";
                    const lockIcon = isLocked ? "fa-lock" : "fa-lock-open";
                    const lockTitle = isLocked ? getString("FieldLock_Unlock_Tooltip") : getString("FieldLock_Lock_Tooltip");
                    inlineControl += `<span class="input-group-addon pointer field-lock-btn"
                        onclick="toggleFieldLock('${mac}', '${fieldName}')"
                        title="${lockTitle}"
                        data-field="${fieldName}"
                        data-locked="${isLocked ? 1 : 0}">
                        <i class="fa-solid ${lockIcon}"></i>
                      </span>`;
                    if (isLocked) {
                      if (!disabledFields.includes(setting.setKey)) {
                        disabledFields.push(setting.setKey);
                      }
                    }
                  }

                  // Add source indicator for tracked fields
                  const fieldName2 = setting.setKey.replace('NEWDEV_', '');
                  if (trackedFields[fieldName2] && mac != "new") {
                    const sourceField = fieldName2 + "Source";
                    //  only show if data available
                    if (deviceData[sourceField] != "")
                    {
                      const currentSource = deviceData[sourceField] || "N/A";
                      const sourceTitle = getString("FieldLock_Source_Label") + currentSource;
                      const sourceColor = currentSource === "USER" ? "text-warning" : (currentSource === "LOCKED" ? "text-danger" : "text-muted");
                      inlineControl += `<span class="input-group-addon pointer ${sourceColor}" title="${sourceTitle}">
                        ${currentSource}
                        </span>`;
                    }
                  }

                  // handle devChildrenDynamic or NEWDEV_devChildrenNicsDynamic - selected values and options are the same
                  if (
                    Array.isArray(fieldData) &&
                    (setting.setKey == "NEWDEV_devChildrenDynamic" ||
                      setting.setKey == "NEWDEV_devChildrenNicsDynamic")
                  ) {
                    fieldDataNew = []
                    fieldData.forEach(child => {
                      fieldDataNew.push(child.devMac)
                    })
                    fieldData = fieldDataNew;
                    fieldOptionsOverride = fieldDataNew;
                  }

                  // Generate the input field HTML
                  const inputFormHtml = `<div class="form-group col-xs-12">
                        <label id="${setting.setKey}_label" class="${obj.labelClasses}" > ${setting.setName}
                          <i my-set-key="${setting.setKey}"
                            title="${getString("Settings_Show_Description")}"
                            class="fa fa-circle-info pointer helpIconSmallTopRight"
                            onclick="showDescriptionPopup(this)">
                          </i>
                        </label>
                        <div class="${obj.inputClasses}">
                          ${generateFormHtml(settingsData, setting, fieldData.toString(), fieldOptionsOverride, null, mac == "new")}
                          ${inlineControl}
                        </div>
                      </div>`;

                  column.append(inputFormHtml); // Append the input field to the column
                  groupDiv.append(column); // Append the column to the group div
                });

                form.append(groupDiv); // Append the group div (containing columns) to the form
              });


              // wait until everything is initialized to update icons
              updateAllIconPreviews();

              // update readonly fields
              handleReadOnly(settingsData, disabledFields);
            };

            // console.log(relevantSettings)

            generateSimpleForm(relevantSettings);

            toggleNetworkConfiguration(mac == 'Internet')

            initSelect2();
            initHoverNodeInfo();

            hideSpinner();

          }}); // $.get callback
      }, 100); // setTimeout
    } // ajax success
  }); // $.ajax
} // getDeviceData


// ----------------------------------------
// Handle the read-only fields
function handleReadOnly(settingsData, disabledFields) {
  settingsData.forEach(setting => {
    const element = $(`#${setting.setKey}`);
    if (disabledFields.includes(setting.setKey)) {
      element.prop('readonly', true);
    } else {
      element.prop('readonly', false);
    }
  });
}

// -----------------------------------------------------------------------------
// Save device data to DB
function setDeviceData(direction = '', refreshCallback = '') {
  // Check MAC
  mac = getMac()

  if (isEmpty(mac)) {

    console.error("Mac not defined");
    return;
  }

  // Determine if a new device should be created
  const createNew = mac === 'new' ? 1 : 0;

  const devLastIP = $('#NEWDEV_devLastIP').val();
  const newMac = $('#NEWDEV_devMac').val()

  // Validate MAC and Last IP
  if (mac === '' || !isValidMac(newMac) || !(isValidIPv4(devLastIP) || isValidIPv6(devLastIP))) {
    showMessage(getString("DeviceEdit_ValidMacIp"), 5000, "modal_red");
    return;
  }

  showSpinner();

  const apiToken = getSetting("API_TOKEN"); // dynamic token
  const apiBaseUrl = getApiBase();

  mac = $('#NEWDEV_devMac').val();

  // Build payload
  const payload = {
    devName: $('#NEWDEV_devName').val(),
    devOwner: $('#NEWDEV_devOwner').val().replace(/'/g, "’"),
    devType: $('#NEWDEV_devType').val().replace(/'/g, ""),
    devVendor: $('#NEWDEV_devVendor').val().replace(/'/g, "’"),
    devIcon: $('#NEWDEV_devIcon').val(),

    devFavorite: ($('#NEWDEV_devFavorite')[0].checked * 1),
    devGroup: $('#NEWDEV_devGroup').val().replace(/'/g, "’"),
    devLocation: $('#NEWDEV_devLocation').val().replace(/'/g, "’"),
    devComments: ($('#NEWDEV_devComments').val()),

    devParentMAC: $('#NEWDEV_devParentMAC').val(),
    devParentPort: $('#NEWDEV_devParentPort').val(),
    devParentRelType: $('#NEWDEV_devParentRelType').val().replace(/'/g, ""),

    devSSID: $('#NEWDEV_devSSID').val(),
    devSite: $('#NEWDEV_devSite').val(),
    devVlan: $('#NEWDEV_devVlan').val(),

    devStaticIP: ($('#NEWDEV_devStaticIP')[0].checked * 1),
    devScan: 1,

    devAlertEvents: ($('#NEWDEV_devAlertEvents')[0].checked * 1),
    devAlertDown: ($('#NEWDEV_devAlertDown')[0].checked * 1),
    devSkipRepeated: $('#NEWDEV_devSkipRepeated').val().split(' ')[0],
    devForceStatus: $('#NEWDEV_devForceStatus').val().replace(/'/g, ""),

    devReqNicsOnline: ($('#NEWDEV_devReqNicsOnline')[0].checked * 1),
    devIsNew: ($('#NEWDEV_devIsNew')[0].checked * 1),
    devIsArchived: ($('#NEWDEV_devIsArchived')[0].checked * 1),

    devFirstConnection: $('#NEWDEV_devFirstConnection').val(),
    devLastConnection: $('#NEWDEV_devLastConnection').val(),
    devLastIP: $('#NEWDEV_devLastIP').val(),

    devCustomProps: btoa(
      JSON.stringify(collectTableData("#NEWDEV_devCustomProps_table"))
    ),

    createNew: createNew
  };


  $.ajax({
    url: `${apiBaseUrl}/device/${encodeURIComponent(mac)}`,
    type: "POST",
    headers: {
      "Authorization": "Bearer " + apiToken,
      "Content-Type": "application/json"
    },
    data: JSON.stringify(payload),
    success: function(resp) {

      if (resp && resp.success) {
        showMessage(getString("Device_Saved_Success"));
      } else {

        console.log(resp);

        errorMessage = resp?.error;

        showMessage(`${getString("Device_Saved_Unexpected")}: ${errorMessage}`, 5000, "modal_red");
      }

      // Remove navigation prompt
      window.onbeforeunload = null;
      somethingChanged = false;

      // Refresh API
      updateApi("devices,appevents");

      // Callback
      if (typeof refreshCallback === "function") {
        refreshCallback(direction);
      }

      hideSpinner();
    },
    error: function(xhr) {
      if (xhr.status === 403) {
        showMessage(getString("Device_Save_Unauthorized"));
      } else {
        showMessage(getString("Device_Save_Failed") + " (" + xhr.status + ")");
      }
      hideSpinner();
    }
  });
}

//-----------------------------------------------------------------------------------
// Disables or enables network configuration for the root node
function toggleNetworkConfiguration(disable) {
  if (disable) {
    // Completely disable the NEWDEV_devParentMAC <select> and NEWDEV_devParentPort
    $('#NEWDEV_devParentMAC').prop('disabled', true).val("").prop('selectedIndex', 0);
    $('#NEWDEV_devParentMAC').empty() // Remove all options
      .append('<option value="">Root Node</option>')
    $('#NEWDEV_devParentPort').prop('disabled', true);
    $('#NEWDEV_devParentPort').prop('readonly', true);
    $('#NEWDEV_devParentMAC').prop('readonly', true);
  } else {
    // Enable the NEWDEV_devParentMAC <select> and NEWDEV_devParentPort
    $('#NEWDEV_devParentMAC').prop('disabled', false);
    $('#NEWDEV_devParentPort').prop('disabled', false);
    $('#NEWDEV_devParentPort').prop('readonly', false);
    $('#NEWDEV_devParentMAC').prop('readonly', false);
  }
}

// -----------------------------------------------
// INIT with polling for panel element visibility
// -----------------------------------------------

var deviceDetailsPageInitialized = false;

function initdeviceDetailsPage() {
  // Only proceed if .plugin-content is visible
  if (!$('#panDetails:visible').length) {
    return; // exit early if nothing is visible
  }

  // init page once
  if (deviceDetailsPageInitialized) return; //  ENSURE ONCE
  deviceDetailsPageInitialized = true;

  showSpinner();

  getDeviceData();

}

// -----------------------------------------------------------------------------
// Recurring function to monitor the URL and reinitialize if needed
function deviceDetailsPageUpdater() {
  initdeviceDetailsPage();

  // Run updater again after delay
  setTimeout(deviceDetailsPageUpdater, 200);
}

// if visible, load immediately, if not start updater
if (!$('#panDetails:visible').length) {
  deviceDetailsPageUpdater();
} else {
  getDeviceData();
}

// -------------------------------------------------------------------
// Lock/Unlock field to prevent plugin overwrites
function toggleFieldLock(mac, fieldName) {
  if (!mac || !fieldName) {
    console.error("Invalid parameters for toggleFieldLock");
    return;
  }

  const apiToken = getSetting("API_TOKEN");
  const apiBaseUrl = getApiBase();

  // Get current source value
  const sourceField = fieldName + "Source";
  const currentSource = deviceData[sourceField] || "N/A";
  const shouldLock = currentSource !== "LOCKED";

  if(shouldLock && somethingChanged)
  {
    showMessage(getString("FieldLock_SaveBeforeLocking"), 5000, "modal_red");
    return;
  }

  const payload = {
    fieldName: fieldName,
    lock: shouldLock ? 1 : 0
  };

  const url = `${apiBaseUrl}/device/${mac}/field/lock`;

  // Show visual feedback
  const lockBtn = $(`.field-lock-btn[data-field="${fieldName}"]`);
  lockBtn.css("opacity", 0.6);

  $.ajax({
    url: url,
    type: "POST",
    headers: {
      "Authorization": `Bearer ${apiToken}`
    },
    contentType: "application/json",
    data: JSON.stringify(payload),
    success: function(response) {
      if (response.success) {
        // Update the button state
        const newLocked = shouldLock ? 1 : 0;
        lockBtn.attr("data-locked", newLocked);

        const lockIcon = shouldLock ? "fa-lock" : "fa-lock-open";
        const lockTitle = shouldLock ? getString("FieldLock_Unlock_Tooltip") : getString("FieldLock_Lock_Tooltip");
        lockBtn.find("i").attr("class", `fa-solid ${lockIcon}`);
        lockBtn.attr("title", lockTitle);

        // Update local source state
        deviceData[sourceField] = shouldLock ? "LOCKED" : "";

        const fieldKey = `NEWDEV_${fieldName}`;
        const fieldInput = $(`#${fieldKey}`);
        fieldInput.prop("readonly", shouldLock);

        // Update source indicator
        const sourceIndicator = lockBtn.next();
        if (sourceIndicator.hasClass("input-group-addon")) {
          if (shouldLock) {
            const sourceValue = "LOCKED";
            const sourceClass = "input-group-addon pointer text-danger";
            sourceIndicator.text(sourceValue);
            sourceIndicator.attr("class", sourceClass);
            sourceIndicator.attr("title", getString("FieldLock_Source_Label") + sourceValue);
          } else {
            sourceIndicator.remove();
          }
        }

        showMessage(shouldLock ? getString("FieldLock_Locked") : getString("FieldLock_Unlocked"), 3000, "modal_green");
      } else {
        showMessage(response.error || getString("FieldLock_Error"), 5000, "modal_red");
      }
    },
    error: function(jqXHR, textStatus, errorThrown) {
      console.error("Lock/Unlock error:", jqXHR, textStatus, errorThrown);
      showMessage(getString("FieldLock_Error"), 5000, "modal_red");
    },
    complete: function() {
      lockBtn.css("opacity", 1.0);
    }
  });
}

</script>
