<?php
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once  $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
  require_once $_SERVER['DOCUMENT_ROOT'] . '/php/templates/language/lang.php';
?>

<div class="col-md-12">
    <div class="callout callout-warning">
      <h4><?= lang('Gen_Warning');?></h4>

      <p><?= lang('Device_MultiEdit_Backup');?></p>
    </div>
    <div class="box box-default">

      <div class="box-header">

        <h3 class="box-title"><?= lang('Gen_Selected_Devices');?></h3>

      </div>
    <div class="deviceSelector col-md-11 col-sm-11" style="z-index:5">
      <div class="db_info_table_row  col-sm-12" >
        <div class="form-group" >
          <div class="input-group col-sm-12 " >
            <select class="form-control select2 select2-hidden-accessible" multiple=""  style="width: 100%;"  tabindex="-1" aria-hidden="true">

            </select>
          </div>
        </div>
      </div>
    </div>
    <div class="col-md-1 hoverHighlight">
        <i class="fa-solid fa-circle-check hoverHighlight pointer" onclick="markAllSelected()" title="<?= lang('Gen_Add_All');?>"></i>
        <i class="fa-solid fa-circle-xmark hoverHighlight pointer" onclick="markAllNotSelected()" title="<?= lang('Gen_Remove_All');?>"></i>
    </div>
  </div>


<div class="col-md-12">
    <div class="box box-default">

      <div class="box-header">
        <h3 class="box-title"><?= lang('Device_MultiEdit_Fields');?></h3>
      </div>
      <div class="box-body">
        <form id="multi-edit-form">
          <!-- Form fields will be appended here -->
        </form>
      </div>
    </div>
  </div>
</div>


  <div class="col-md-12">
    <div class="box box-default">
      <div class="box-header ">
        <h3 class="box-title"><?= lang('Device_MultiEdit_MassActions');?></h3>
      </div>
      <div class="box-body">
        <div class="col-md-12">
          <div class="col-md-4" style="">
              <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red col-md-12 col-sm-12 col-xs-12" id="btnDeleteMAC" onclick="askDeleteSelectedDevices()"><?= lang('Maintenance_Tool_del_selecteddev');?></button>
          </div>
          <div class="col-md-8"><?= lang('Maintenance_Tool_del_selecteddev_text');?></div>
        </div>
        <div class="col-md-12">
          <div class="col-md-4" style="">
              <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red col-md-12 col-sm-12 col-xs-12" id="btnUnlockFieldsSelected" onclick="askUnlockFieldsSelected()"><?= lang('Maintenance_Tool_unlockFields_selecteddev');?></button>
          </div>
          <div class="col-md-8"><?= lang('Maintenance_Tool_del_unlockFields_selecteddev_text');?></div>
        </div>
        <div class="col-md-12">
          <div class="col-md-4" style="">
              <button type="button" class="btn btn-default pa-btn pa-btn-delete bg-red col-md-12 col-sm-12 col-xs-12" id="btnClearSourceFields" onclick="askClearSourceFields()"><?= lang('Maintenance_Tool_clearSourceFields_selected');?></button>
          </div>
          <div class="col-md-8"><?= lang('Maintenance_Tool_clearSourceFields_selected_text');?></div>
        </div>
      </div>
    </div>
  </div>


<script defer>

  // -------------------------------------------------------------------
  // Get plugin and settings data from API endpoints
  function getData(){

    // some race condition, need to implement delay
    setTimeout(() => {
      $.get('php/server/query_json.php', { file: 'table_settings.json', nocache: Date.now() }, function(res) {

        settingsData = res["data"];

        excludedColumns = ["NEWDEV_devMac", "NEWDEV_devFirstConnection", "NEWDEV_devLastConnection", "NEWDEV_devLastNotification", "NEWDEV_devScan", "NEWDEV_devPresentLastScan", "NEWDEV_devCustomProps", "NEWDEV_devChildrenNicsDynamic", "NEWDEV_devChildrenDynamic" ]

        const relevantColumns = settingsData.filter(set =>
            set.setGroup === "NEWDEV" &&
            set.setKey.includes("_dev") &&
            !excludedColumns.includes(set.setKey) &&
            !set.setKey.includes("__metadata")
        );

        const generateSimpleForm = multiEditColumns => {
            const form = $('#multi-edit-form');
            const numColumns = 2; // Number of columns

            // Calculate number of elements per column
            const elementsPerColumn = Math.ceil(multiEditColumns.length / numColumns);

            // Divide columns equally
            for (let i = 0; i < numColumns; i++) {
                const column = $('<div>').addClass('col-md-6');

                // Append form groups to the column
                for (let j = i * elementsPerColumn; j < Math.min((i + 1) * elementsPerColumn, multiEditColumns.length); j++) {

                  const setTypeObject  = JSON.parse(multiEditColumns[j].setType.replace(/'/g, '"'));

                  // get the element with the input value(s)
                  let elements = setTypeObject.elements.filter(element => element.elementHasInputValue === 1);

                  //  if none found, take last
                  if(elements.length == 0)
                  {
                    elementWithInputValue = setTypeObject.elements[setTypeObject.elements.length - 1]
                  } else
                  {
                    elementWithInputValue = elements[0]
                  }

                  const { elementType, elementOptions = [], transformers = [] } = elementWithInputValue;
                  const {
                    inputType,
                    readOnly,
                    isMultiSelect,
                    isOrdeable,
                    cssClasses,
                    placeholder,
                    suffix,
                    sourceIds,
                    separator,
                    editable,
                    valRes,
                    getStringKey,
                    onClick,
                    onChange,
                    customParams,
                    customId,
                    columns,
                    base64Regex,
                    elementOptionsBase64,
                    focusout
                  } = handleElementOptions('none', elementOptions, transformers, val = "");

                  //  render based on element type
                  if (elementType === 'select') {

                    targetLocation = multiEditColumns[j].setKey + "_generateSetOptions"

                    generateOptionsOrSetOptions(multiEditColumns[j].setKey, [], targetLocation, generateOptions, null)

                    console.log(multiEditColumns[j].setKey)
                    //  Handle Icons as they need a preview
                    if(multiEditColumns[j].setKey == 'NEWDEV_devIcon')
                    {
                      input = `
                            <span class="input-group-addon iconPreview" my-customid="NEWDEV_devIcon_preview"></span>
                            <select  class="form-control"
                                      onChange="updateIconPreview(this)"
                                      my-customparams="NEWDEV_devIcon,NEWDEV_devIcon_preview"
                                      id="${multiEditColumns[j].setKey}"
                                      data-my-column="${multiEditColumns[j].setKey}"
                                      data-my-targetColumns="${multiEditColumns[j].setKey.replace('NEWDEV_','')}" >
                              <option id="${targetLocation}"></option>
                            </select>`

                    } else{

                      input = `<select  class="form-control"
                                      id="${multiEditColumns[j].setKey}"
                                      data-my-column="${multiEditColumns[j].setKey}"
                                      data-my-targetColumns="${multiEditColumns[j].setKey.replace('NEWDEV_','')}" >
                              <option id="${targetLocation}"></option>
                            </select>`
                    }


                  } else if (elementType === 'input' || elementType === 'textarea'){

                    // Add classes specifically for checkboxes
                    inputType === 'checkbox' ?  inputClass = 'checkbox' : inputClass = 'form-control';


                    input =  `<input  class="${inputClass}"
                                      id="${multiEditColumns[j].setKey}"
                                      my-customid="${multiEditColumns[j].setKey}"
                                      data-my-column="${multiEditColumns[j].setKey}"
                                      data-my-targetColumns="${multiEditColumns[j].setKey.replace('NEWDEV_','')}"
                                      type="${inputType}">`
                  }


                  const inputEntry  = `<div class="form-group col-sm-12" >
                                          <label class="col-sm-3 control-label">${multiEditColumns[j].setName}</label>
                                          <div class="col-sm-9">
                                            <div class="input-group red-hover-border">
                                              ${input}
                                              <span class="input-group-addon pointer red-hover-background" onclick="massUpdateField('${multiEditColumns[j].setKey}');" title="${getString('Device_MultiEdit_Tooltip')}">
                                                <i class="fa fa-save"></i>
                                              </span>
                                            </div>
                                          </div>
                                        </div>`


                  column.append(inputEntry);
                }

                form.append(column);
            }
        };

        console.log(relevantColumns)

        generateSimpleForm(relevantColumns);

        initSelect2();
        initDeviceSelectors();


    })

    }, 100);

  }

  // -----------------------------------------------------------------------------
  // Initialize device selectors / pickers fields
  function initDeviceSelectors() {

    // Parse device list using the shared helper
    devicesList = parseDeviceCache(getCache('devicesListAll_JSON'));

    // Check if the device list exists and is an array
    if (Array.isArray(devicesList)) {
        const $select = $(".deviceSelector select");

        $select.append(
            devicesList
                .filter(d => d.devMac && d.devName)
                .map(d => `<option value="${d.devMac}">${d.devName}</option>`)
                .join('')
        ).trigger('change');
    }



    // Initialize selected items after a delay so selected macs are available in the context
    setTimeout(function(){
          // Retrieve MAC addresses from query string or cache
          var macs = getQueryString('macs') || getCache('selectedDevices');

          if(macs)
          {
            // Split MAC addresses if they are comma-separated
            macs = macs.split(',');

            console.log(macs)

            // Loop through macs to be selected list
            macs.forEach(function(mac) {

              // Create the option and append to Select2
              var option = new Option($('.deviceSelector select option[value="' + mac + '"]').html(), mac, true, true);

              $('.deviceSelector select').append(option).trigger('change');
            });

          }

      }, 10);
  }



  // -----------------------------------------------------------------------------
  // Get selected devices Macs
  function selectorMacs () {
    return $('.deviceSelector select').val().join(',');
  }

  // -----------------------------------------------------------------------------
  // Select All
  function markAllSelected() {
    // Get the <select> element with the class 'deviceSelector'
    var selectElement = $('.deviceSelector select');

    // Iterate over each option within the select element
    selectElement.find('option').each(function() {
      // Mark each option as selected
      $(this).prop('selected', true);
    });

    // Trigger the 'change' event to notify Bootstrap Select of the changes
    selectElement.trigger('change');
  }

  // -----------------------------------------------------------------------------
  // UN-Select All
  function markAllNotSelected() {
    // Get the <select> element with the class 'deviceSelector'
    var selectElement = $('.deviceSelector select');

    // Iterate over each option within the select element
    selectElement.find('option').each(function() {
      // Unselect each option
      $(this).prop('selected', false);
    });

    // Trigger the 'change' event to notify Bootstrap Select of the changes
    selectElement.trigger('change');
  }



  // -----------------------------------------------------------------------------
  // Update specified field over the specified DB column and selected entry(ies)
  function massUpdateField(id) {

    // Get the input element
    var inputElement = $(`#${id}`);

    console.log(inputElement);
    console.log(id);

    // Initialize columnValue variable
    var columnValue;

    // Check the type of the input element
    if (inputElement.is(':checkbox')) {
        // For checkboxes, set the value to 1 if checked, otherwise set it to 0
        columnValue = inputElement.is(':checked') ? 1 : 0;
    } else {
        // For other input types (like textboxes), simply retrieve their values
        // Don't encode icons (already base64) or other pre-encoded values
        columnValue = inputElement.val();
    }

    var targetColumns = inputElement.attr('data-my-targetColumns');


    console.log(targetColumns);
    console.log(columnValue);

    // update selected
    if(selectorMacs() != "")
    {
      executeAction('update', 'devMac', selectorMacs(), targetColumns, columnValue )
    }
    else
    {
      showModalWarning(getString("Gen_Error"), getString('Device_MultiEdit_No_Devices'));
    }
}

// -----------------------------------------------------------------------------
// action: Represents the action to be performed, a CRUD operation like "update", "delete", etc.
// whereColumnName: Specifies the name of the column used in the WHERE or SELECT statement for filtering.
// key: Represents the unique identifier of the row or record to be acted upon.
// targetColumns: Indicates the columns to be updated or affected by the action.
// newTargetColumnValue: Specifies the new value to be assigned to the specified column(s).
function executeAction(action, whereColumnName, key, targetColumns, newTargetColumnValue )
{
  const apiBase = getApiBase();
  const apiToken = getSetting("API_TOKEN");
  const url = `${apiBase}/dbquery/${action}`;

  // Convert comma-separated string to array if needed
  let idArray = key;
  if (typeof key === 'string' && key.includes(',')) {
    idArray = key.split(',');
  } else if (!Array.isArray(key)) {
    idArray = [key];
  }

  // Build request data based on action type
  const requestData = {
    dbtable: "Devices",
    columnName: whereColumnName,
    id: idArray
  };

  // Only include columns and values for update action
  if (action === "update") {
    // Ensure columns and values are arrays
    requestData.columns = Array.isArray(targetColumns) ? targetColumns : [targetColumns];
    requestData.values = Array.isArray(newTargetColumnValue) ? newTargetColumnValue : [newTargetColumnValue];
  }

  $.ajax({
    url,
    method: "POST",
    headers: { "Authorization": `Bearer ${apiToken}` },
    data: JSON.stringify(requestData),
    contentType: "application/json",
    success: function(response) {
      if (response.success) {
        showMessage(getString('Gen_DataUpdatedUITakesTime'));
        // Remove navigation prompt "Are you sure you want to leave..."
        window.onbeforeunload = null;

        // update API endpoints to refresh the UI
        updateApi("devices,appevents")

        const columnsMsg = targetColumns ? ` on Columns "${targetColumns}"` : '';
        write_notification(`[Multi edit] Executed "${action}"${columnsMsg} matching "${key}"`, 'info')

      } else {
        console.error(response.error || "Unknown error");
        showMessage(response.error || getString('Gen_LockedDB'));
      }
    },
    error: function(xhr, status, error) {
      console.error("Error executing action:", status, error, xhr.responseJSON);
      showMessage("Error: " + (xhr.responseJSON?.error || error));
    }
  });
}


// -----------------------------------------------------------------------------
// Ask to unlock fields of selected devices
function askUnlockFieldsSelected () {
  // Ask
  showModalWarning(
    getString('Maintenance_Tool_unlockFields_selecteddev_noti'),
    getString('Gen_AreYouSure'),
    getString('Gen_Cancel'),
    getString('Gen_Okay'),
    'unlockFieldsSelected');
}

// -----------------------------------------------------------------------------
// Ask to unlock fields of selected devices
function askClearSourceFields () {
  // Ask
  showModalWarning(
    getString('Maintenance_Tool_clearSourceFields_selected_noti'),
    getString('Gen_AreYouSure'),
    getString('Gen_Cancel'),
    getString('Gen_Okay'),
    ()=>unlockFieldsSelected(null, true));
}

// -----------------------------------------------------------------------------
// Unlock fields for selected devices
function unlockFieldsSelected(fields = null, clearAll = false) {
    // Get selected MACs
    const macs_tmp = selectorMacs(); // returns array of MACs

    console.log(macs_tmp);
    console.log(clearAll);


    if (!macs_tmp || macs_tmp == "" || macs_tmp.length === 0) {
        showMessage(textMessage = "No devices selected", timeout = 3000, colorClass = "modal_red")
        return;
    }

    // API setup
    const apiBase = getApiBase();
    const apiToken = getSetting("API_TOKEN");
    const url = `${apiBase}/devices/fields/unlock`;

    // Convert string to array
    const macsArray = macs_tmp.split(",").map(m => m.trim()).filter(Boolean);

    const payload = {
        mac: macsArray,      // array of MACs for backend
        fields: fields,      // null for all tracked fields
        clearAll: clearAll  // true to clear all sources, false to clear only LOCKED/USER
    };

    $.ajax({
        url: url,
        method: "POST",
        headers: { "Authorization": `Bearer ${apiToken}` },
        contentType: "application/json",
        data: JSON.stringify(payload),
        success: function(response) {
            if (response.success) {
                showMessage(getString('Gen_DataUpdatedUITakesTime'));
                write_notification(
                    `[Multi edit] Successfully unlocked fields of devices with MACs: ${macs_tmp}`,
                    "info"
                );
            } else {
                write_notification(
                    `[Multi edit] Failed to unlock fields: ${response.error || "Unknown error"}`,
                    "interrupt"
                );
            }
        },
        error: function(xhr, status, error) {
            console.error("Error unlocking fields:", status, error);
            write_notification(
                `[Multi edit] Error unlocking fields: ${xhr.responseJSON?.error || error}`,
                "error"
            );
        }
    });
}


// -----------------------------------------------------------------------------
// Ask to delete selected devices
function askDeleteSelectedDevices () {
  // Ask
  showModalWarning(
    getString('Maintenance_Tool_del_alldev_noti'),
    getString('Gen_AreYouSure'),
    getString('Gen_Cancel'),
    getString('Gen_Delete'),
    'deleteSelectedDevices');
}

// -----------------------------------------------------------------------------
// Delete selected devices
function deleteSelectedDevices()
{
  macs_tmp = selectorMacs()
  executeAction('delete', 'devMac', macs_tmp )
  write_notification('[Multi edit] Manually deleted devices with MACs:' + macs_tmp, 'info')
}


getData();


</script>

<!-- ----------------------------------------------------------------------- -->

<!-- ----------------------------------------------------------------------- -->


