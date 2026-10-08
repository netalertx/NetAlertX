/* -----------------------------------------------------------------------------
*  NetAlertX
*  Open Source Network Guard / WIFI & LAN intrusion detector
*
*  plugin_column_render.js - Shared, plugin-agnostic column-value renderer.
*  Extracted verbatim from pluginsCore.php so Plugin View and the Sources
*  tab's Field View render database_column_definitions-typed values
*  identically instead of duplicating this switch statement.
*-------------------------------------------------------------------------------
#  jokob             support@netalertx.com                GNU GPLv3
----------------------------------------------------------------------------- */

/**
 * The DataTables init options shared by every plugin-data table in the app
 * (Plugin View's Objects/Events/History tables, Field View's per-field
 * tables) - paging/searching/ordering/lengthMenu are identical everywhere a
 * plugin's rows get rendered into a table, so this is the one place that set
 * is defined. Callers spread this into their own config and add whatever
 * else they need (ajax/serverSide for a server-paginated table, plain
 * data/columns for a small client-side one, createdRow, etc).
 * @param {string|null} skelSelector - jQuery selector for this table's own loading skeleton, faded out after the first draw. Pass null if the table has no per-table skeleton (e.g. a shared tab-level one is used instead).
 * @returns {object} A partial DataTables options object.
 */
function getStandardDataTableOptions(skelSelector) {
  return {
    autoWidth: false,
    paging: true,
    searching: true,
    ordering: true,
    pageLength: 25,
    lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
    language: { emptyTable: getString('Gen_No_Data') },
    // Fade out the skeleton only after the first draw so there is no gap
    // between the skeleton disappearing and the table rows appearing.
    initComplete: function() {
      if (skelSelector) {
        $(skelSelector).fadeOut(0, function() { $(this).hide(); });
      }
    },
  };
}

// -----------------------------------------------------------------------------
// Get form control according to the column definition from config.json > database_column_definitions
function getFormControl(dbColumnDef, value, index) {

  result = ''

  // Check if mapped_to_column_data exists and has a value to override the supplied value which is most likely `undefined`
  if (dbColumnDef.mapped_to_column_data && dbColumnDef.mapped_to_column_data.value) {
    value = dbColumnDef.mapped_to_column_data.value;
  }


  result = processColumnValue(dbColumnDef, value, index, dbColumnDef.type)

  return result;
}

// -----------------------------------------------------------------------------
// Process column value
function processColumnValue(dbColumnDef, value, index, type) {
  if (type.includes('.')) {
  const typeParts = type.split('.');

  // recursion
  for (const typePart of typeParts) {
    value = processColumnValue(dbColumnDef, value, index, typePart)
  }

  } else{
  // pick form control based on the supplied type
  switch(type)
  {
    case 'label':
      value = `<span>${value}<span>`;
      break;
    case 'none':
      value = `${value}`;
      break;
    case 'textarea_readonly':
      value = `<textarea cols="70" rows="3" wrap="off" readonly style="white-space: pre-wrap;">
          ${value.replace(/^b'(.*)'$/gm, '$1').replace(/\\n/g, '\n').replace(/\\r/g, '\r')}
          </textarea>`;
      break;
    case 'textbox_save':

      value = value == 'null' ? '' : value; // hide 'null' values

      id = `${dbColumnDef.column}_${index}`

      value =  `<span class="form-group">
              <div class="input-group">
                <input class="form-control" type="text" value="${value}" id="${id}" data-my-column="${dbColumnDef.column}"  data-my-index="${index}" name="${dbColumnDef.column}">
                <span class="input-group-addon"><i class="fa fa-save pointer" onclick="genericSaveData('${id}');"></i></span>
              </div>
            <span>`;
      break;
    case 'url':
      value = `<span><a href="${value}" target="_blank">${value}</a><span>`;
      break;
    case 'url_http_https':
      value = `<span>
                <a href="http://${value}" target="_blank">
                  <i class="fa fa-lock-open "></i>
                </a>
                /
                <a href="https://${value}" target="_blank">
                  <i class="fa fa-lock "></i>
                </a>
            </span>`;
      break;
    case 'device_name_mac':
      value = `<div class="text-center"> ${value}
                <br/>
                ${createDeviceLink(value)}
              </div>`;
      break;
    case 'device_mac':
      value = `<span class="anonymizeMac"><a href="/deviceDetails.php?mac=${value}" target="_blank">${value}</a><span>`;
      break;
    case 'device_ip':
      value = `<span class="anonymizeIp"><a href="#" onclick="navigateToDeviceWithIp('${value}')" >${value}</a><span>`;
      break;
    case 'threshold':

      valueTmp = ''

      $.each(dbColumnDef.options, function(index, obj) {
        if(Number(value) < Number(obj.maximum) && valueTmp == '')
        {
          valueTmp = `<div class="thresholdFormControl" style="background-color:${obj.hexColor}">${value}</div>`
          // return;
        }
      });

      value = valueTmp;

      break;
    case 'replace':
      $.each(dbColumnDef.options, function(index, obj) {
        if(value == obj.equals)
        {
          value = `<span title="${value}">${obj.replacement}</span>`
        }
      });
      break;
    case 'regex':

      for (const option of dbColumnDef.options) {
        if (option.type === type) {

          const regexPattern = new RegExp(option.param);
          const match = value.match(regexPattern);
          if (match) {
            // Return the first match
            value =  match[0];

          }
        }
      }
      break;
    case 'eval':

      for (const option of dbColumnDef.options) {
        if (option.type === type) {
          // console.log(option.param)
          value =  eval(option.param);
        }
      }
      break;

    default:
      value = value + `<div style='text-align:center' title="${getString("Plugins_no_control")}"><i class='fa-solid fa-circle-question'></i></div>` ;
  }
  }

  // Default behavior if no match is found
  return value;
}
