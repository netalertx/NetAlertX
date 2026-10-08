<?php
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
?>

<!-- Main content ---------------------------------------------------------- -->
<div class="nav-tabs-custom content plugin-content field-view-content">

  <?php require $_SERVER['DOCUMENT_ROOT'] . '/php/templates/skel_device_details_tab_field_view.php'; ?>

  <ul id="field-tabs-location" class="nav nav-tabs col-sm-2 ">
    <!-- PLACEHOLDER -->
  </ul>
  <div id="field-tabs-content-location-wrap" class="tab-content col-sm-10">
    <div id="field-tabs-content-location" class="tab-content col-sm-12">
      <!-- PLACEHOLDER -->
    </div>
  </div>
</div>

<script>

// -----------------------------------------------------------------------------
// Status values from Plugins_Objects are plugin-observation state, not network
// liveness - render them accordingly rather than implying reachability.
// Localized via getString(), not hardcoded English, matching the rest of the UI.
const FIELD_VIEW_STATUS_LABELS = {
  'new':                  'Plugins_FieldStatus_New',
  'watched-changed':      'Plugins_FieldStatus_Changed',
  'watched-not-changed':  'Plugins_FieldStatus_Unchanged',
  'missing-in-last-scan': 'Plugins_FieldStatus_NotReported',
};

let fieldViewLastMac = null;
let fieldViewInitialized = false;

// -----------------------------------------------------------------------------
function hideFieldViewSkeleton() {
  $('#skel-tab-field-view').fadeOut(0, function() { $(this).hide(); });
}
function showFieldViewSkeleton() {
  var $skel = $('#skel-tab-field-view');
  $skel.stop(true, true).fadeIn(10);
}

// -----------------------------------------------------------------------------
// Builds the side-nav of fields and an empty shell pane per field. Each pane's
// rows are built lazily, the first time its tab is actually focused (see the
// shown.bs.tab binding below) - fieldViews/entries are already fully fetched
// by this point (one shared getSourcesFieldData() call, not a per-field
// query), so deferring is purely about not building table markup the user
// may never look at, not an extra round-trip.
// getFieldViewDefinitions() is the shared lookup declared in deviceDetails.php -
// Session Info's Known IPs chip list reads the exact same data, not a duplicate.
async function renderFieldView(mac) {
  const fieldViews = await getFieldViewDefinitions();
  const entries = await getSourcesFieldData(mac);

  const fieldKeys = Object.keys(fieldViews);
  if (fieldKeys.length === 0) {
    $('#field-tabs-content-location').html(`<p class="text-muted plugin-no-data">${getString('Gen_No_Data')}</p>`);
    return;
  }

  const urlParams = new URLSearchParams(window.location.search);
  const requestedField = urlParams.get('field');
  const activeField = fieldKeys.includes(requestedField) ? requestedField : fieldKeys[0];

  // Tear down any DataTable instances from a previous mac before wiping the
  // markup they're attached to - .empty() alone would orphan them instead of
  // cleanly releasing their state.
  $('#field-tabs-content-location table').each(function() {
    if ($.fn.DataTable.isDataTable(this)) {
      $(this).DataTable().destroy();
    }
  });
  $('#field-tabs-location').empty();
  $('#field-tabs-content-location').empty();

  fieldKeys.forEach(fieldKey => {
    const isActive = fieldKey === activeField;
    const { label_key } = fieldViews[fieldKey];

    $('#field-tabs-location').append(`
      <li class="left-nav ${isActive ? 'active' : ''}">
        <a class="col-sm-12 textOverflow" href="#fieldPane_${fieldKey}" data-toggle="tab">
          ${getString(label_key)}
        </a>
      </li>
    `);

    const navItems = buildTabNavItems([
      { href: `#objectsTarget_field_${fieldKey}`, icon: 'fa-cube', label: getString('Plugins_Objects'), active: true },
    ]);

    $('#field-tabs-content-location').append(`
      <div id="fieldPane_${fieldKey}" class="tab-pane ${isActive ? 'active' : ''}">
        <div class="nav-tabs-custom plugin-tab-nav">
          <ul class="nav nav-tabs">${navItems}</ul>
          <div class="tab-content">
            <div id="objectsTarget_field_${fieldKey}" class="tab-pane active">
              <table id="fieldTable_${fieldKey}" class="display table table-striped table-stretched field-pane-table"></table>
            </div>
          </div>
        </div>
      </div>
    `);
  });

  const builtFields = new Set();
  function buildFieldPaneTableOnce(fieldKey) {
    if (builtFields.has(fieldKey)) return;
    builtFields.add(fieldKey);
    buildFieldPaneTable(fieldKey, fieldViews[fieldKey], entries);
  }

  // The field active from the start builds immediately; every other field's
  // table waits for its tab to actually be clicked.
  buildFieldPaneTableOnce(activeField);
  $('#field-tabs-location a[data-toggle="tab"]').off('shown.bs.tab.fieldView').on('shown.bs.tab.fieldView', function() {
    buildFieldPaneTableOnce($(this).attr('href').replace('#fieldPane_', ''));
  });
}

// -----------------------------------------------------------------------------
// Builds one field's DataTable - Plugin / Value / Status / Last Changed, one
// row per participating plugin's entry. Reuses the exact same shared options
// (getStandardDataTableOptions()) and cell-rendering approach
// (createdCell + getFormControl()) pluginsCore.php's own DataTables use,
// rather than a parallel hand-rolled table - only the data source differs
// (a small, already-fetched client-side array here vs. a server-paginated
// GraphQL query there). The column each plugin's value is read from is
// whatever get_plugin_columns_for_field() determined server-side, not a
// hardcoded column role; value_type comes from the field's own
// DEVICE_FIELD_VIEWS declaration (e.g. 'device_ip' for the IP field's
// clickable link, 'none' for a plain value) rather than being hardcoded to
// the IP field's rendering for every field.
function buildFieldPaneTable(fieldKey, fieldView, entries) {
  const { columns: pluginColumns, value_type } = fieldView;

  const rows = pluginColumns
    .map(({ plugin, column }) => {
      const entry = entries.find(e => e.plugin === plugin);
      return entry ? { plugin, value: entry[column], status: entry.status, dateTimeChanged: entry.dateTimeChanged || '' } : null;
    })
    .filter(row => row !== null);

  $(`#fieldTable_${fieldKey}`).DataTable({
    ...getStandardDataTableOptions(null), // no per-table skeleton - the whole tab shares #skel-tab-field-view
    data: rows,
    columns: [
      { data: 'plugin', title: getString('AppEvents_Plugin') },
      {
        data: 'value',
        title: getString('WF_Action_value'),
        createdCell: function(td, cellData, rowData) {
          $(td).html(getFormControl({ type: value_type }, cellData, rowData.plugin));
        }
      },
      {
        data: 'status',
        title: getString('Device_TableHead_Status'),
        render: function(data) {
          const statusLabelKey = FIELD_VIEW_STATUS_LABELS[data];
          return statusLabelKey ? getString(statusLabelKey) : data;
        }
      },
      { data: 'dateTimeChanged', title: getString('Plugins_Field_LastChanged') },
    ],
  });
}

// -----------------------------------------------------------------------------
// Poll for visibility the same way pluginsCore.php's own updater() does -
// #sourcesFieldView only reports :visible once both the Sources tab is the
// active top-level tab AND the Plugin/Field toggle has selected Field View.
function fieldViewUpdater() {
  if ($('#sourcesFieldView').is(':visible')) {
    const currentMac = getMac();
    if (!fieldViewInitialized || currentMac !== fieldViewLastMac) {
      fieldViewInitialized = true;
      fieldViewLastMac = currentMac;
      showFieldViewSkeleton();
      callAfterAppInitialized(() => renderFieldView(currentMac).finally(hideFieldViewSkeleton));
    }
  }
  setTimeout(fieldViewUpdater, 200);
}

fieldViewUpdater();

</script>
