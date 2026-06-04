// -------------------------------------------------------------------
// Get all plugin prefixes of a given type
function getPluginsByType(pluginsData, pluginType, onlyEnabled) {
  var result = [];

  pluginsData.forEach((plug) => {
    if (plug.plugin_type == pluginType) {
      // collect all, or if only enabled, check if NOT disabled
      if (
        onlyEnabled == false ||
        (onlyEnabled && getSetting(plug.unique_prefix + "_RUN") != "disabled")
      ) {
        result.push(plug.unique_prefix);
      }
    }
  });

  return result;
}

// -------------------------------------------------------------------
// Get plugin code name base on prefix
function getPluginCodeName(pluginsData, prefix) {
  var result = "";

  pluginsData.forEach((plug) => {
    if (plug.unique_prefix == prefix) {
      id = plug.code_name;

      // console.log(id)
      result = plug.code_name;
    }
  });

  return result;
}

// -------------------------------------------------------------------
// Get plugin type base on prefix
function getPluginType(pluginsData, prefix) {
  var result = "core";

  pluginsData.forEach((plug) => {
    if (plug.unique_prefix == prefix) {
      id = plug.plugin_type;

      // console.log(id)
      result = plug.plugin_type;
    }
  });

  return result;
}

// -------------------------------------------------------------------
// Get plugin config based on prefix
function getPluginConfig(pluginsData, prefix) {
  result = "";

  pluginsData.forEach((plug) => {
    if (plug.unique_prefix == prefix) {
      // console.log(id)
      result = plug;
    }
  });

  return result;
}

// ----------------------------------------
// Show the description of a setting
function showDescriptionPopup(e) {

  console.log($(e).attr("my-set-key"));

  showModalOK("Info", getString($(e).attr("my-set-key") + '_description'))
}

// -------------------------------------------------------------------
// Generate plugin HTML card based on prefixes in an array
function pluginCards(prefixesOfEnabledPlugins, includeSettings) {
  html = "";

  prefixesOfEnabledPlugins.forEach((prefix) => {
    includeSettings_html = "";

    includeSettings.forEach((set) => {
      includeSettings_html += `
            <div class="col-sm-6 overview-setting-value-wrap">
              <a href="#${prefix + "_" + set}" onclick="toggleAllSettings()">
                <div class="overview-setting-value  pointer" title="${
                  prefix + "_" + set
                }">
                  <code>${getSetting(prefix + "_" + set)}</code>
                </div>
              </a>
            </div>
          `;
    });

    html += `
              <div class="col-xs-6 col-sm-4 col-md-3 col-lg-2  col-xxl-1  padding-5px">
                <div class="small-box bg-green col-sm-12 " >
                  <div class="inner col-sm-12">
                    <a href="#${prefix}_header" onclick="toggleAllSettings('open')">
                      <h5 class="card-title">
                        <b>${getString(prefix + "_display_name")}</b>
                      </h5>
                    </a>
                    ${includeSettings_html}
                  </div>
                  <a href="#${prefix}_header" onclick="toggleAllSettings('open')">
                    <div class="icon"> ${getString(prefix + "_icon")} </div>
                  </a>
                </div>

              </div>
            `;
  });

  return html;
}

// -----------------------------------------------------------------------------
// Open or close all settings
// -----------------------------------------------------------------------------
function toggleAllSettings(openOrClose = "") {
  inStr = " in";
  allOpen = true;
  openIcon = "fa-angle-double-down";
  closeIcon = "fa-angle-double-up";

  $(".panel-collapse").each(function () {
    if ($(this).attr("class").indexOf(inStr) == -1) {
      allOpen = false;
    }
  });

  if (allOpen == false || openOrClose == "open") {
    // open all
    openAllSettings();
    $("#toggleSettings").attr(
      "class",
      $("#toggleSettings").attr("class").replace(openIcon, closeIcon)
    );
  } else {
    // close all
    $('div[data-myid="collapsible"]').each(function () {
      $(this).attr("class", "panel-collapse collapse  ");
    });
    $("#toggleSettings").attr(
      "class",
      $("#toggleSettings").attr("class").replace(closeIcon, openIcon)
    );
  }
}

function openAllSettings() {
  $('div[data-myid="collapsible"]').each(function () {
    $(this).attr("class", "panel-collapse collapse in");
  });
  $('div[data-myid="collapsible"]').each(function () {
    $(this).attr("style", "height:inherit");
  });
}

// -------------------------------------------------------------------
// Checks if all schedules are the same
function schedulesAreSynchronized(prefixesOfEnabledPlugins, pluginsData) {
  plug_schedules = [];

  prefixesOfEnabledPlugins.forEach((prefix) => {
    pluginsData.forEach((plug) => {
      if (plug.unique_prefix == prefix) {
        plug_schedules.push(
          getSetting(prefix + "_RUN_SCHD").replace(/\s/g, "")
        ); // replace all white characters to compare them easier
      }
    });
  });

  // Check if all plug_schedules are the same
  if (plug_schedules.length > 0) {
    const firstSchedule = plug_schedules[0];
    return plug_schedules.every((schedule) => schedule === firstSchedule);
  }

  return true; // Return true if no schedules are found
}

// -------------------------------------------------------------------
// Checks if value is already encoded
function isSHA256(value) {
  // Check if the value is a string and has a length of 64 characters
  if (typeof value === "string" && value.length === 64) {
    // Check if the value contains only hexadecimal characters
    return /^[0-9a-fA-F]+$/.test(value);
  } else {
    return false;
  }
}

// -------------------------------------------------------------------
// Validation
// -------------------------------------------------------------------
function settingsCollectedCorrectly(settingsArray, settingsJSON_DB) {
  // check if the required UI_LANG setting is in the array - if not something went wrong
  $.each(settingsArray, function (index, value) {
    if (value[1] == "UI_LANG") {
      if (isEmpty(value[3]) == true) {
        console.log(`⚠ Error: Required setting UI_LANG not found`);
        showModalOk("ERROR", getString("settings_missing_block"));

        return false;
      }
    }
  });

  const settingsCodeNames = settingsJSON_DB.map((setting) => setting.setKey);
  const detailedCodeNames = settingsArray.map((item) => item[1]);

  const missingCodeNamesOnPage = detailedCodeNames.filter(
    (setKey) => !settingsCodeNames.includes(setKey)
  );
  const missingCodeNamesInDB = settingsCodeNames.filter(
    (setKey) => !detailedCodeNames.includes(setKey)
  );

  // check if the number of settings on the page and in the DB are the same
  if (missingCodeNamesOnPage.length !== missingCodeNamesInDB.length) {
    console.log(
      `⚠ Error: The following settings are missing in the DB or on the page (Reload page to fix):`
    );
    console.log(missingCodeNamesOnPage);
    console.log(missingCodeNamesInDB);

    showModalOk("ERROR", getString("settings_missing_block"));

    return false;
  }

  //  all OK
  return true;
}
// -------------------------------------------------------------------
// Manipulating Editable List options
// -------------------------------------------------------------------

// ---------------------------------------------------------
// Clone datatable row
function cloneDataTableRow(el){

  console.log(el);

  const id = "NEWDEV_devCustomProps_table"; // Your table ID
  const table = $('#'+id).DataTable();


  // Get the 'my-index' attribute from the closest tr element
  const myIndex = parseInt($(el).closest("tr").attr("my-index"));

  // Find the row in the table with the matching 'my-index'
  const row = table.rows().nodes().to$().filter(`[my-index="${myIndex}"]`).first().get(0);

  // Clone the row (including its data and controls)
  let clonedRow = $(row).clone(true, true); // The true arguments copy the data and event handlers


  $(clonedRow).attr("my-index",table.rows().count())


  console.log(clonedRow);


  // Add the cloned row to the DataTable
  table.row.add(clonedRow[0]).draw();
}

// ---------------------------------------------------------
// Remove current datatable row
function removeDataTableRow(el) {
  console.log(el);

  const id = "NEWDEV_devCustomProps_table"; // Your table ID
  const table = $('#'+id).DataTable();

  if(table.rows().count() > 1)
  {
    // Get the 'my-index' attribute from the closest tr element
    const myIndex = parseInt($(el).closest("tr").attr("my-index"));

    // Find the row in the table with the matching 'my-index'
    const row = table.rows().nodes().to$().filter(`[my-index="${myIndex}"]`).first().get(0);

    // Remove the row from the DataTable
    table.row(row).remove().draw();
  }
  else
  {
    showMessage (getString("CustProps_cant_remove"), 3000, "modal_red");
  }
}

// ---------------------------------------------------------
// Add item via pop up form dialog
function addViaPopupForm(element) {
  console.log(element);

  const toId = $(element).attr("my-input-to");
  const curValue = $(`#${toId}`).val();
  const parsed = JSON.parse(atob($(`#${toId}`).data("elementoptionsbase64")));
  const popupFormJson = parsed.find(obj => "popupForm" in obj)?.popupForm ?? null;

  console.log(`toId  | curValue: ${toId}  | ${curValue}`);

  showModalPopupForm(
    `<i class="fa-solid fa-square-plus"></i> ${getString("Gen_Add")}`,  // title
    "",                                                                 // message
    getString("Gen_Cancel"),                                            // btnCancel
    getString("Gen_Add"),                                               // btnOK
    null,                                                               // curValue
    popupFormJson,                                                      // popupform
    toId,                                                               // parentSettingKey
    element,                                                            // triggeredBy
    true                                                                // initialize defaut values
  );

  // flag something changes to prevent navigating from page
  settingsChanged();
}

// ---------------------------------------------------------
// Add item to list
function addList(element, clearInput = true) {
  const fromId = $(element).attr("my-input-from");
  const toId = $(element).attr("my-input-to");

  const input = $(`#${fromId}`).val();

  console.log(`fromId | toId | input : ${fromId} | ${toId} | ${input}`);

  const newOption = $("<option class='interactable-option'></option>")
    .attr("value", input)
    .text(input);

  // add new option
  $(`#${toId}`).append(newOption);

  // clear input
  if (clearInput) {
    $(`#${fromId}`).val("");
  }

  // Initialize interaction options only for the newly added option
  initListInteractionOptions(newOption);

  // flag something changes to prevent navigating from page
  settingsChanged();
}

// ---------------------------------------------------------
function removeFromList(element) {
  settingsChanged();
  $(`#${$(element).attr("my-input-to")}`)
    .find("option:last")
    .remove();
}

// -------------------------------------------------------------------
// Function to remove an item from the select element
function removeOptionItem(option) {
  settingsChanged();
  option.remove();
}

// -------------------------------------------------------------------
// Update value of an item from the select element
function updateOptionItem(option, value) {
  settingsChanged();
  option.html(value);
  option.val(value);
}

// -------------------------------------------------------------------
// Remove all options
function removeAllOptions(element) {
  settingsChanged();
  $(`#${$(element).attr("my-input-to")}`).empty();
}

// -------------------------------------------------------------------
// Add all options
function selectAll(element) {
  settingsChanged();

  var selectElement = $(`#${$(element).attr("my-input-to")}`);

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
function unselectAll(element) {
  settingsChanged();
  var selectElement = $(`#${$(element).attr("my-input-to")}`);

  // Iterate over each option within the select element
  selectElement.find('option').each(function() {
    // Unselect each option
    $(this).prop('selected', false);
  });

  // Trigger the 'change' event to notify Bootstrap Select of the changes
  selectElement.trigger('change');
}

// -----------------------------------------------------------------------------
// Trigger change to open up the dropdown filed
function selectChange(element) {
  settingsChanged();

  var selectElement = $(`#${$(element).attr("my-input-to")}`);

  selectElement.parent().find("input").focus().click();
}

// -------------------------------------------------------------------
// Function to initialize remove functionality on select options

// Counter to track number of clicks
let clickCounter = 0;

// Function to initialize list interaction options
function initListInteractionOptions(element) {
  if (element) {
    $options = $(element);
  } else {
    $options = $(`.interactable-option`);
  }

  // Attach click event listener to options
  $options.on("click", function () {
    const $option = $(this);

    // Increment click counter
    clickCounter++;

    // Delay to capture multiple clicks
    setTimeout(() => {
      // Perform action based on click count
      if (clickCounter === 1) {
        // Single-click action

        const $parent = $option.parent();
        const transformers = $parent.attr("my-transformers");

        if (transformers && transformers === "name|base64") {
          // Parent has my-transformers="name|base64"
          const toId =  $parent.attr("id");
          const curValue = $option.val();
          const parsed = JSON.parse(atob($parent.data("elementoptionsbase64")));
          const popupFormJson = parsed.find(obj => "popupForm" in obj)?.popupForm ?? null;

          showModalPopupForm(
            `<i class="fa fa-pen-to-square"></i> ${getString("Gen_Update_Value")}`, // title
            "",                                                                     // message
            getString("Gen_Cancel"),                                                // btnCancel
            getString("Gen_Update"),                                                // btnOK
            curValue,                                                               // curValue
            popupFormJson,                                                          // popupform
            toId,                                                                   // parentSettingKey
            this,                                                                    // triggeredBy
            true                                                                    // populate overrides
          );
        } else {
          // Fallback to normal field input
          showModalFieldInput(
            `<i class="fa fa-pen-to-square"></i> ${getString("Gen_Update_Value")}`,
            getString("settings_update_item_warning"),
            getString("Gen_Cancel"),
            getString("Gen_Update"),
            $option.html(),
            function () {
              updateOptionItem($option, $(`#modal-field-input-field`).val());
            }
          );
        }

      } else if (clickCounter === 2) {
        // Double-click action
        removeOptionItem($option);
      }

      // Reset click counter
      clickCounter = 0;
    }, 300); // Adjust delay as needed
  });
}

// -------------------------------------------------------------------
// Function to filter rows based on input text
function filterRows(inputText) {

  // open everything if input text is empty
  if (!inputText) {
    inputText = "";

    $(".panel").each(function () {
      var $panel = $(this);
      var $panelHeader = $panel.find('.panel-heading');
      var $panelBody = $panel.find('.panel-collapse');

      $panel.show()
      $panelHeader.show()
      $panelBody.collapse('show');

      $panelBody.find(".table_row:not(.docs)").each(function () {
        var $row = $(this)
        var rowId = $row.attr("id");
        var isMetadataRow = rowId && rowId.endsWith("__metadata");
        if (!isMetadataRow) {
          $row.show()
        }
      });

    });

  } else{
    // filter

    $(".panel").each(function () {
      var $panel = $(this);
      var $panelHeader = $panel.find('.panel-heading');
      var $panelBody = $panel.find('.panel-collapse');

      var anyVisible = false; // Flag to check if any row is visible

      $panelBody.find(".table_row:not(.docs)").each(function () {
        var $row = $(this);

        // Check if the row ID ends with "__metadata"
        var rowId = $row.attr("id");
        var isMetadataRow = rowId && rowId.endsWith("__metadata");

        // Always hide metadata rows
        if (isMetadataRow) {
          $row.hide();
          return; // Skip further processing for metadata rows
        }

        var description = $row.find(".setting_description").text().toLowerCase();
        var setKey = $row.find(".setting_name code").text().toLowerCase();

        if (
          description.includes(inputText.toLowerCase()) ||
          setKey.includes(inputText.toLowerCase())
        ) {
          $row.show();
          anyVisible = true; // Set the flag to true if at least one row is visible
        } else {
          $row.hide();
        }
      });

      // Determine whether to hide or show the panel based on visibility of rows
      if (anyVisible) {
        $panelBody.collapse('show'); // Ensure the panel body is shown if there are visible rows
        $panelHeader.show(); // Show the panel header
        $panel.show(); // Show the entire panel if there are visible rows
      } else {
        $panelBody.collapse('hide'); // Hide the panel body if no rows are visible
        $panelHeader.hide(); // Hide the panel header if no rows are visible
        $panel.hide(); // Hide the entire panel if no rows are visible
      }
    });


  }


}


setTimeout(() => {
  // Event listener for input change
  $("#settingsSearch").on("input", function () {
    var searchText = $(this).val();
    // hide the setting overview dashboard
    $("#settingsOverview").collapse("hide");

    filterRows(searchText);
  });

  // Event listener for input focus
  // var firstFocus = true;
  $("#settingsSearch").on("focus", function () {
    openAllSettings();
  });
}, 1000);


// -----------------------------------------------------------------------------
// Show/hide the metadata settings
// -----------------------------------------------------------------------------
function toggleMetadata(element) {
  const id = $(element).attr("my-to-toggle");

  $(`#${id}`).toggle();
}

// -----------------------------------------------------------------------------
// Show setting description in a modal on smaller screens
// -----------------------------------------------------------------------------
function showDescription(element) {
  const id = $(element).attr("my-to-show");

  description = $(`${id}`)[0].innerHTML
  console.log(description);
  showModalOK(getString("Gen_Description"), description);
}

// ---------------------------------------------------------
// Helper methods
// ---------------------------------------------------------
// Toggle readonly mode of the target element specified by the id in the "my-input-toggle-readonly" attribute
function overrideToggle(element) {
  settingsChanged();

  targetId = $(element).attr("my-input-toggle-readonly");

  inputElement = $(`#${targetId}`)[0];

  if (!inputElement) {
    console.error("Input element not found!");
    return;
  }

  if (inputElement.type === "text" || inputElement.type === "password") {
    inputElement.readOnly = !inputElement.readOnly;
  } else if (inputElement.type === "checkbox") {
    inputElement.disabled = !inputElement.disabled;
  } else {
    console.warn(
      "Unsupported input type. Only text, password, and checkbox inputs are supported."
    );
  }
}


// ---------------------------------------------------------
// Generate options or set options based on the provided parameters
function generateOptionsOrSetOptions(
  setKey,
  valuesArray, // Array of values to be pre-selected in the dropdown
  placeholder, // ID of the HTML element where dropdown should be rendered (will be replaced)
  processDataCallback, // Callback function to generate entries based on options
  targetField, // Target field or element where selected value should be applied or updated
  transformers = [], // Transformers to be applied to the values
  overrideOptions = null // override options if available
) {

  // console.log(setKey);

  // console.log(overrideOptions);
  // console.log( getSettingOptions(setKey));
  // console.log( setKey);

  // NOTE {value} options to replace with a setting or SQL value are handled in the cacheSettings() function
  // obj.push({ id: item, name: item })
  options = arrayToObject(createArray(overrideOptions ? overrideOptions : getSettingOptions(setKey)))

  // Call to render lists
  renderList(
    options,
    processDataCallback,
    valuesArray,
    placeholder,
    targetField,
    transformers
  );
}


// ------------------------------------------------------------
// Function to apply transformers to a value
function applyTransformers(val, transformers) {
  transformers.forEach((transformer) => {
    switch (transformer) {
      case "sha256":
        // Implement sha256 hashing logic
        if (!isSHA256(val)) {
          val = CryptoJS.SHA256(val).toString(CryptoJS.enc.Hex);
        }
        break;
      case "base64":
        // Implement base64 logic
        if (!isBase64(val)) {
          val = btoa(val);
        }
        break;
      case "prefix|base64":
        // Implement base64 logic w/ prefix
        if (val.startsWith("base64:") == false) {
          val = "base64:" + btoa(val);
        }
        break;
      case "name|base64":
        // // Implement base64  logic
        // if (!isBase64(val)) {
        //   val = btoa(val);
        // }
        val = val;   // probably TODO ⚠
        break;
      case "getString":
        // no change
        val = val;
        break;
      default:
        console.warn(`Unknown transformer: ${transformer}`);
    }
  });
  return val;
}

// ------------------------------------------------------------
// Function to reverse transformers applied to a value - returns the LABEL
function reverseTransformers(val, transformers) {
  transformers.reverse().forEach((transformer) => {
    switch (transformer) {
      case "sha256":
        // Reversing sha256 is not possible since it's a one-way hash function
        console.warn("Reversing sha256 is not possible");
        break;
      case "base64":
        // Implement base64 decoding logic
        if (isBase64(val)) {
          val = atob(val);
        }
        break;
      case "prefix|base64":
        // Implement base64 decoding logic
        if (val.startsWith("base64:")) {
          let encodedPart = val.slice(7); // remove "base64:"
          if (isBase64(encodedPart)) {
              val = atob(encodedPart);
          } else {
              console.log("Prefix exists but not valid Base64");
          }
        } else {
            console.error("Not Base64-prefixed");
        }
        break;
      case "name|base64":
        // Implement base64 decoding logic
        if (isBase64(val)) {
          val = JSON.parse(atob(val))[0][3];
        }
        val = val;   // probably TODO ⚠
        break;
      case "getString":
        // retrieve string
        val = getString(val);
        break;
      case "deviceChip":
        mac = val  // value is mac
        val =  encodeSpecialChars(getDevDataByMac(mac, "devName"))
        break;
      case "deviceRelType":
        val =  val; // nothing to do
        break;
      default:
        console.warn(`Unknown transformer: ${transformer}`);
    }
  });
  return val;
}


// ------------------------------------------------------------
// Function to initialize relevant variables based on HTML element
const handleElementOptions = (setKey, elementOptions, transformers, val) => {
  let inputType = "text";
  let readOnly = "";
  let isMultiSelect = false;
  let isOrderable = false;
  let cssClasses = "";
  let placeholder = "";
  let suffix = "";
  let separator = "";
  let editable = false;
  let valRes = val;
  let sourceIds = [];
  let getStringKey = "";
  let onClick = "console.log('onClick - Not implemented');";
  let onChange = "console.log('onChange - Not implemented');";
  let focusout = "console.log('focusout - Not implemented');";
  let customParams = "";
  let customId = "";
  let columns = [];
  let base64Regex = "";
  let elementOptionsBase64 = btoa(JSON.stringify(elementOptions));

  elementOptions.forEach((option) => {
    if (option.prefillValue) {
      valRes = option.prefillValue === "null" ? "" : option.prefillValue;
    }
    if (option.type) {
      inputType = option.type;
    }
    if (option.readonly === "true") {
      readOnly = `readonly`;
    }
    if (option.multiple === "true") {
      isMultiSelect = true;
    }
    if (option.orderable === "true") {
      isOrderable = true;
    }
    if (option.editable === "true") {
      editable = true;
    }
    if (option.cssClasses) {
      cssClasses = option.cssClasses;
    }
    if (option.placeholder) {
      placeholder = option.placeholder;
    }
    if (option.suffix) {
      suffix = option.suffix;
    }
    if (option.sourceSuffixes) {
      $.each(option.sourceSuffixes, function (index, suf) {
        sourceIds.push(setKey + suf);
      });
    }
    if (option.separator) {
      separator = option.separator;
    }
    if (option.getStringKey) {
      getStringKey = option.getStringKey;
    }
    if (option.onClick) {
      onClick = option.onClick;
    }
    if (option.onChange) {
      onChange = option.onChange;
    }
    if (option.focusout) {
      focusout = option.focusout;
    }
    if (option.customParams) {
      customParams = option.customParams;
    }
    if (option.customId) {
      customId = option.customId;
    }
    if (option.columns) {
      columns = option.columns;
    }
    if (option.base64Regex) {
      base64Regex = option.base64Regex;
    }
  });

  if (transformers.includes("sha256")) {
    inputType = "password";
  }

  return {
    inputType,
    readOnly,
    isMultiSelect,
    isOrderable,
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
  };
};


// -----------------------------------------------------------------------------
// Data processors
// -----------------------------------------------------------------------------

// --------------------------------------------------
// Creates an object from an array
function arrayToObject(array) {
  const obj = [];
  array.forEach((item, index) => {
    obj.push({ id: item, name: item })
  });
  return obj;
}

// -----------------------------------------------------------------------------
// Processor to generate options
//          options     - available options
//          valuesArray - values = selected options
function generateOptions(options, valuesArray, targetField, transformers, placeholder) {
  var optionsHtml = "";

  resultArray    = []
  selectedArray  = []
  cssClass       = ""

  // determine if options or values are used in the listing
  if (valuesArray.length > 0 && options.length > 0){

    // multiselect list ->  options only + selected the ones in valuesArray
    resultArray   = options;
    selectedArray = valuesArray

  } else if (valuesArray.length > 0 && options.length == 0){

    // editable list -> values only
    resultArray   = arrayToObject(valuesArray)
    cssClass = "interactable-option"  // generates [1x 📝 | 2x 🚮]
  } else if (options.length > 0){

    // dropdown -> options only (value == 1 STRING not ARRAY)
    resultArray   = options;
  }

  // Create a map to track the index of each item in valuesArray
  const orderMap = new Map(valuesArray.map((item, index) => [item, index]));

  // Sort resultArray based on the order in valuesArray
  resultArray.sort((a, b) => {
    const indexA = orderMap.has(a.id) ? orderMap.get(a.id) : valuesArray.length;
    const indexB = orderMap.has(b.id) ? orderMap.get(b.id) : valuesArray.length;
    return indexA - indexB;
  });

  resultArray.forEach(function(item) {
    let labelName = item.name;

    if (labelName !== '❌None') {
      labelName = reverseTransformers(labelName, transformers);
    }

    // Always include selected if options are used as a source
    let selected = options.length !== 0 && valuesArray.includes(item.id) ? 'selected' : '';

    optionsHtml += `<option class="${cssClass}" value="${encodeSpecialChars(item.id)}" ${selected}>${encodeSpecialChars(labelName)}</option>`;
  });


  // Place the resulting HTML into the specified placeholder div
  $("#" + placeholder).replaceWith(optionsHtml);
}


// -----------------------------------------------------------------------------
// Processor to generate a list
function generateList(options, valuesArray, targetField, transformers, placeholder) {
  var listHtml = "";
  options.forEach(function(item) {

    labelName = item.name

    if(labelName != '❌None')
    {
      labelName = reverseTransformers(labelName, transformers)
    }

    let selected = valuesArray.includes(item.id) ? 'selected' : '';

    listHtml += `<li ${selected}>${labelName}</li>`;
  });

  // Place the resulting HTML into the specified placeholder div
  $("#" + placeholder).replaceWith(listHtml);
}

// -----------------------------------------------------------------------------
// Processor to generate a list in the deviceDetails page
function genListWithInputSet(options, valuesArray, targetField, transformers, placeholder) {

  var listHtml = "";


  options.forEach(function(item) {

    let selected = valuesArray.includes(item.id) ? 'selected' : '';

    // console.log(item);

    labelName = item.name

    if(labelName != '❌None')
    {
      labelName = reverseTransformers(labelName, transformers)
      // console.log(transformers);
    }

    listHtml += `<li ${selected}>
                      <a href="javascript:void(0)" onclick="setTextValue('${targetField}','${item.id}')">${labelName}</a>
                </li>`;

  });

  // Place the resulting HTML into the specified placeholder div
  $("#" + placeholder).replaceWith(listHtml);
}

// -----------------------------------------------------------------
// Collects a setting based on code name
function collectSetting(prefix, setCodeName, setType, settingsArray) {
  // Parse setType if it's a JSON string
  const setTypeObject = (typeof setType === "string")
      ? JSON.parse(processQuotes(setType))
      : setType;

  const dataType = setTypeObject.dataType;

  // Pick element with input value
  let elements = setTypeObject.elements.filter(el => el.elementHasInputValue === 1);
  let elementWithInputValue = elements.length === 0
      ? setTypeObject.elements[setTypeObject.elements.length - 1]
      : elements[0];

  const { elementType, elementOptions = [], transformers = [] } = elementWithInputValue;

  // Check if validation failed
  if (
    $(`#${setCodeName}`)
    && $(`#${setCodeName}`).attr("data-is-valid")
    && $(`#${setCodeName}`).attr("data-is-valid") == 0
  )
  {
     return {
      "settingsArray": settingsArray,
      "dataIsValid": false,
      "failedSettingKey": setCodeName
    };
  }

  const opts = handleElementOptions('none', elementOptions, transformers, val = "");

  // Map of handlers
  const handlers = {
      datatableString: () => {
          const value = collectTableData(`#${setCodeName}_table`);
          return btoa(JSON.stringify(value));
      },
      simpleValue: () => {
          let value = $(`#${setCodeName}`).val();
          return applyTransformers(value, transformers);
      },
      checkbox: () => {
          let value = $(`#${setCodeName}`).is(':checked') ? 1 : 0;
          if (dataType === "boolean") {
              value = value === 1 ? "True" : "False";
          }
          return applyTransformers(value, transformers);
      },
      array: () => {
          let temps = [];
          if (opts.isOrderable) {
              temps = $(`#${setCodeName}`).val();
          } else {
              const sel = $(`#${setCodeName}`).attr("my-editable") === "true" ? "" : ":selected";
              $(`#${setCodeName} option${sel}`).each(function() {
                  const vl = $(this).val();
                  if (vl !== '') {
                      temps.push(applyTransformers(vl, transformers));
                  }
              });
          }
          return JSON.stringify(temps);
      },
      none: () => "",
      json: () => {
          let value = $(`#${setCodeName}`).val();
          value = applyTransformers(value, transformers);
          return JSON.stringify(value, null, 2);
      },
      fallback: () => {
          console.error(`[collectSetting] Couldn't determine how to handle (${setCodeName}|${dataType}|${opts.inputType})`);
          let value = $(`#${setCodeName}`).val();
          return applyTransformers(value, transformers);
      }
  };

  // Select handler key
  let handlerKey;
  if (dataType === "string" && elementType === "datatable") {
      handlerKey = "datatableString";
  } else if (dataType === "string" ||
            (dataType === "integer" && (opts.inputType === "number" || opts.inputType === "text"))) {
      handlerKey = "simpleValue";
  } else if (opts.inputType === "checkbox") {
      handlerKey = "checkbox";
  } else if (dataType === "array") {
      handlerKey = "array";
  } else if (dataType === "none") {
      handlerKey = "none";
  } else if (dataType === "json") {
      handlerKey = "json";
  } else {
      handlerKey = "fallback";
  }

  const value = handlers[handlerKey]();
  settingsArray.push([prefix, setCodeName, dataType, value]);

  return {
    "settingsArray": settingsArray,
    "dataIsValid": true,
    "failedSettingKey": ""
  };
}


// ------------------------------------------------------------------------------
// Generate the form control for setting
/**
 * Generates the HTML string for form controls based on setting configurations.
 * Supports various element types including select, input, button, textarea, span, and recursive datatables.
 * * @param {Object} settingsData - The global settings object containing configuration for all available settings.
 * @param {Object} set - The specific configuration object for the current setting.
 * @param {string} set.setKey - Unique identifier for the setting.
 * @param {string} set.setType - JSON string defining the UI components (dataType, elements, etc.).
 * @param {string} [set.setValue] - The default value for the setting.
 * @param {Array|string} [set.setEvents] - List of event triggers to be rendered as clickable icons.
 * @param {any} overrideValue - The current value to be displayed in the form control.
 * @param {any} overrideOptions - Custom options to override the default setting options (used primarily for dropdowns).
 * @param {string} originalSetKey - The base key name (used to maintain reference when keys are modified for uniqueness in tables).
 * @param {boolean} populateFromOverrides - Flag to determine if the value should be pulled from `set['setValue']` (true) or `overrideValue` (false).
 * * @returns {string} A string of HTML containing the form elements and any associated event action icons.
 * * @example
 * const html = generateFormHtml(allSettings, currentSet, "DefaultVal", null, "my_key", false);
 * $('#container').html(html);
 */
function generateFormHtml(settingsData, set, overrideValue, overrideOptions, originalSetKey, populateFromOverrides) {
  let inputHtml = '';


  // if override value is considered empty initialize from setting defaults
  populateFromOverrides ? inVal = set['setValue'] : inVal = overrideValue;

  const setKey = set['setKey'];
  const setType = set['setType'];

    // if (setKey == 'UNIFIAPI_site_name') {

    //   console.log("==== DEBUG OUTPUT BELOW 1 ====");
    //   console.log("populateFromOverrides: " + populateFromOverrides);
    //   console.log(setType);
    //   console.log(setKey);
    //   console.log("overrideValue:" + overrideValue);
    //   console.log("inVal:" + inVal);
    //   console.log("set['setValue']:" + set['setValue']);
    // }

  // Parse the setType JSON string
  // console.log(processQuotes(setType));

  const setTypeObject = JSON.parse(processQuotes(setType))
  const dataType = setTypeObject.dataType;
  const elements = setTypeObject.elements || [];

  // Generate HTML for elements
  elements.forEach(elementObj => {
    const { elementType, elementOptions = [], transformers = [] } = elementObj;

    // Handle element options
    const {
      inputType,
      readOnly,
      isMultiSelect,
      isOrderable,
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
    } = handleElementOptions(setKey, elementOptions, transformers, inVal);

    // Override value
    let val = valRes;

    // if (setKey == 'UNIFIAPI_site_name') {

    //   console.log("==== DEBUG OUTPUT BELOW 2 ====");
    //   console.log(setType);
    //   console.log(setKey);
    //   console.log("overrideValue:" + overrideValue);
    //   console.log("inVal:" + inVal);
    //   console.log("val:" + val);
    // }

    // Generate HTML based on elementType
    switch (elementType) {
      case 'select':
        const multi = isMultiSelect ? "multiple" : "";
        const addCss = isOrderable ? "select2 select2-hidden-accessible" : "";

        inputHtml += `<select onChange="settingsChanged();${onChange}"
                              onfocusout="${focusout}"
                              my-data-type="${dataType}"
                              my-editable="${editable}"
                              class="form-control ${addCss} ${cssClasses}"
                              name="${setKey}"
                              id="${setKey}"
                              my-transformers=${transformers}
                              my-customparams="${customParams}"
                              my-customid="${customId}"
                              my-originalSetKey="${originalSetKey}"
                              data-elementoptionsbase64="${elementOptionsBase64}"
                              ${multi}
                              ${readOnly ? "disabled" : ""}>
                          <option value="" id="${setKey + "_temp_"}"></option>
                        </select>`;

        generateOptionsOrSetOptions(setKey, createArray(val), `${setKey}_temp_`, generateOptions, null, transformers, overrideOptions);
        break;

      case 'input':
        const checked = val === 'True' || val === 'true' ||  val === '1' || val == true ? 'checked' : '';
        const inputClass = inputType === 'checkbox' ? 'checkbox' : 'form-control';

        inputHtml += `<input
                        class="${inputClass} ${cssClasses}"
                        onChange="settingsChanged();${onChange}"
                        onfocusout="${focusout}"
                        my-data-type="${dataType}"
                        my-customparams="${customParams}"
                        my-customid="${customId}"
                        my-originalSetKey="${originalSetKey}"
                        my-base64Regex="${base64Regex}"
                        id="${setKey}${suffix}"
                        type="${inputType}"
                        value="${val}"
                        ${readOnly}
                        ${checked}
                        placeholder="${placeholder}"
                      />`;
        break;

      case 'button':
        inputHtml += `<button
                        class="btn btn-primary ${cssClasses}"
                        my-customparams="${customParams}"
                        my-customid="${customId}"
                        my-originalSetKey="${originalSetKey}"
                        my-input-from="${sourceIds}"
                        my-input-to="${setKey}"
                        data-elementoptionsbase64="${elementOptionsBase64}"
                        onclick="${onClick}">
                        ${getString(getStringKey)}
                      </button>`;
        break;

      case 'textarea':
        inputHtml += `<textarea
                        class="form-control input"
                        onChange="settingsChanged();${onChange}"
                        onfocusout="${focusout}"
                        my-customparams="${customParams}"
                        my-customid="${customId}"
                        my-originalSetKey="${originalSetKey}"
                        my-data-type="${dataType}"
                        id="${setKey}"
                        ${readOnly}>${val}</textarea>`;
        break;

      case 'span':
        inputHtml += `<span
                        class="${cssClasses}"
                        my-data-type="${dataType}"
                        my-customparams="${customParams}"
                        my-customid="${customId}"
                        my-originalSetKey="${originalSetKey}"
                        onclick="${onClick}">
                        ${getString(getStringKey)}${placeholder}
                      </span>`;
        break;
      case 'datatable':

        const tableId = `${setKey}_table`;
        let datatableHtml = `<table id="${tableId}" class="table table-striped">`;

        // Dynamic array creation
        let emptyVal = [];

        let columnSettings = [];

        // Generate table headers
        datatableHtml += '<thead><tr>';

        columns.forEach(column => {
          let columnSetting = getSetObject(settingsData, column.settingKey) || {};

          datatableHtml += `<th>${columnSetting.setName}</th>`;

          if(column.typeOverride)
          {
            columnSetting["setType"] = JSON.stringify(column.typeOverride);
          }

          if(column.optionsOverride)
          {
            if (column.optionsOverride.startsWith("setting.")) {
              columnSetting["setOptions"] = getSetting(column.optionsOverride.replace("setting.",""));
            } else {
              columnSetting["setOptions"] = column.optionsOverride;
            }
          }

          columnSettings.push(columnSetting)

          // helper for if val is empty
          emptyVal.push('');
        });
        datatableHtml += '</tr></thead>';

        // Generate table body
        datatableHtml += '<tbody>';

        if(val.length > 0 && isBase64(val))
        {
          val = atob(val)
          // console.log(val);
          val = JSON.parse(val)
        }else{
          // init empty
          val = [emptyVal]
        }

        let index = 0;
        val.forEach(rowData => {
            datatableHtml += `<tr my-index="${index}">`;

            let j = 0;
            columnSettings.forEach(set => {
                // Extract the value for the current column
                let columnOverrideValue = rowData[j] && Object.values(rowData[j])[0];

                // Create unique key to prevent dropdown data duplication
                const oldKey = set["setKey"];
                set["setKey"] = oldKey + "_" + index;

                // console.log("settingsData");
                // console.log(settingsData);
                // console.log(set);


                // Generate the cell HTML using the extracted value
                const cellHtml = generateFormHtml(
                    settingsData,
                    set,
                    columnOverrideValue,
                    set["setOptions"],
                    oldKey,
                    false
                );
                datatableHtml += `<td> <div class="input-group"> ${cellHtml} </div></td>`;

                // Restore the original key
                set["setKey"] = oldKey;

                j++;
            });
            datatableHtml += '</tr>';
            index++;
        });


        datatableHtml += '</tbody></table>';

        inputHtml += datatableHtml;

        // Initialize DataTable with jQuery
        $(document).ready(() => {
          $(`#${tableId}`).DataTable({
            ordering: false, // Disables sorting on all columns
            searching: false, // Disables the search box
            dom: "<'top'rt><'bottom'ipl>", // Move length dropdown to the bottom
          });
        });

        break;

      default:
        console.warn(`🟥 Unknown element type: ${elementType}`);
    }
  });

  // Generate event HTML if applicable
  let eventsHtml = '';

  const eventsList = createArray(set['setEvents']);
  // inline buttons events
if (eventsList.length > 0) {
  eventsList.forEach(event => {
    let eventIcon = "fa-play";

    switch (event) {
      case "select_icon":
        eventIcon = "fa-chevron-down";
        break;
      case "add_icon":
      case "add_option":
        eventIcon = "fa-square-plus";
        break;
      case "copy_icons":
        eventIcon = "fa-copy";
        break;
      case "go_to_device":
        eventIcon = "fa-square-up-right";
        break;
      case "go_to_node":
        eventIcon = "fa-sitemap fa-rotate-270";
        break;
      case "run":
        eventIcon = "fa-play";
        break;
      case "test":
        eventIcon = "fa-vial-circle-check";
        break;
      default:
        eventIcon = "fa-play";
        break;
    }

    eventsHtml += `<span class="input-group-addon pointer"
                    id="${`${event}_${setKey}`}"
                    data-myparam-setkey="${setKey}"
                    data-myparam="${setKey}"
                    data-myparam-plugin="${setKey.split('_')[0] || ''}"
                    data-myevent="${event}"
                    onclick="execute_settingEvent(this)">
                    <i title="${getString(event + "_event_tooltip")}" class="fa ${eventIcon}"></i>
                  </span>`;
  });
}

  // Combine and return the final HTML
  return inputHtml + eventsHtml;
}

// -----------------------------------------------------
// Return the setting object by setKey
function getSetObject(settingsData, setKey) {

  found = false;
  result = ""

  settingsData.forEach(function(set) {

    if (set.setKey == setKey) {
      // console.log(set);

      result = set;
      return;

    }

  });

  if(result == "")
  {
    console.error(settingsData);
    console.error(`Setting not found: ${setKey}`);
  }

  return result;
}

// ---------------------------------------
// Collect DataTable data
function collectTableData(tableSelector) {
  const table = $(tableSelector).DataTable();

  let tableData = [];

  table.rows().every(function () {
      const rowData = [];
      const cells = $(this.node()).find('td');

      cells.each((index, cell) => {
          const input = $(cell).find('input, select, textarea');

          if (input.length) {
              if (input.attr('type') === 'checkbox') {
                  // For checkboxes, check if they are checked
                  rowData[index] = { [input.attr("my-originalsetkey")] : input.prop('checked') };
              } else {
                  // Generic sync for other inputs (text, select, textarea)
                  rowData[index] =  { [input.attr("my-originalsetkey")] : input.val().replace(/'/g, "").replace(/"/g, "") };
              }
          } else {
              // Handle plain text
              // rowData[index] = { [input.attr("my-originalsetkey")] : $(cell).text()};
              console.log(`Nothig to collect: ${$(cell).html()}`)
          }
      });

      tableData.push(rowData);
  });

  return tableData;
}



