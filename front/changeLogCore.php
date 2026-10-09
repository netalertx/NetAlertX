<script>
  showSpinner();
</script>

<?php require 'php/templates/skel_change_log.php'; ?>

<section class="content change-log">
  <!-- Help link -->
  <span class="helpIcon">
    <a target="_blank" href="https://docs.netalertx.com/DEVICE_CHANGE_LOG">
      <i class="fa fa-circle-question"></i>
    </a>
  </span>

  <div class="row">
    <div class="col-xs-12">
      <div >
      
        <!-- Filter Bar -->      
        <div class="changeLogFilter" >
          <select id="filterChangedBy" class="form-control" style="width:200px;">
            <option value=""><?= lang('device_history_col_source'); ?> - All</option>
          </select>

          <select id="filterChangedColumn" class="form-control" style="width:200px;">
            <option value=""><?= lang('device_history_col_dropdown'); ?> - All</option>
          </select>

          <?= lang('device_history_col_changes'); ?>
        </div>

        <!-- Data Table -->
        <div class="box-body">
          <table id="changeHistoryTable" class="table table-bordered table-striped">
            <thead>
              <tr>
                <th><?= lang('device_history_col_time'); ?></th>
                <th><?= lang('device_history_col_source'); ?></th>
                <th><?= lang('gen_device'); ?></th>
                <th><?= lang('device_history_table_title_changes'); ?></th>
              </tr>
            </thead>

            <tbody id="changeHistoryBody">
              <tr>
                <td colspan="4" class="text-center">
                  <i class="fa fa-spinner fa-spin"></i>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>
    </div>
  </div>
</section>

<script>
  /**
   * =========================
   * State
   * =========================
   */
  let historyTable = null;
  let changeLogPageInitialized = false;

  const urlMac = getMacFromUrl();

  /**
   * =========================
   * Table Initialization
   * =========================
   */
  function initializeHistoryTable() {

    historyTable = $('#changeHistoryTable').DataTable({

      processing: false,
      serverSide: true,
      paging: true,
      searching: true,
      ordering: true,
      info: true,
      autoWidth: false,

      pageLength: getSetting("UI_DEFAULT_PAGE_SIZE"),
      lengthMenu: getLengthMenu(getSetting("UI_DEFAULT_PAGE_SIZE")),

      /**
       * Server-side AJAX loader (GraphQL)
       */
      ajax: function (dtRequest, callback) {

        showSpinner();

        // DataTables paging
        const limit = parseInt(dtRequest.length, 10) || 50;
        const start = parseInt(dtRequest.start, 10) || 0;
        const page = Math.floor(start / limit) + 1;
        const search = dtRequest.search?.value || null;
        const order = dtRequest.order?.[0];

        const apiBaseUrl = getApiBase();
        const url = `${apiBaseUrl}/graphql`;

        // Resolve device filter from MAC if present
        let devGUID = null;
        if (urlMac) {
          devGUID = getDevDataByMac(urlMac, "devGUID");
        }

        // Column mapping for sorting
        const columns = [
          "timestamp",
          "changedBy",
          "devGUID",
          null
        ];

        const sort = [];

        if (order) {
          const field = columns[order.column];
          if (field) {
            sort.push({
              field: field,
              order: order.dir
            });
          }
        }

        /**
         * GraphQL query
         */
        const query = `
          query(
            $devGUID:String,
            $changedColumn:String,
            $changedBy:String,
            $options:PageQueryOptionsInput
          ){
            deviceHistoryGrouped(
              devGUID:$devGUID
              changedColumn:$changedColumn
              changedBy:$changedBy
              options:$options
            ){
              count
              history{
                devGUID
                timestamp
                changedBy
                changes{
                  changedColumn
                  oldValue
                  newValue
                }
              }
            }
          }
        `;

        $.ajax({
          url: url,
          method: "POST",
          contentType: "application/json",
          headers: {
            Authorization: "Bearer " + getSetting("API_TOKEN")
          },

          data: JSON.stringify({
            query,
            variables: {
              changedBy: $('#filterChangedBy').val() || null,
              changedColumn: $('#filterChangedColumn').val() || null,
              devGUID: devGUID,
              options: {
                page,
                limit,
                sort,
                search
              }
            }
          }),

          success: function (resp) {

            const result = resp?.data?.deviceHistoryGrouped;

            callback({
              data: result?.history || [],
              recordsTotal: result?.count || 0,
              recordsFiltered: result?.count || 0
            });

            hideSpinner();
            hideChangeLogSkeleton();
          },

          error: function (xhr, textStatus, errorThrown) {

            console.error("History GraphQL request failed", {
              status: xhr.status,
              statusText: xhr.statusText,
              textStatus,
              errorThrown,
              response: xhr.responseText,
              variables: {
                changedBy: $('#filterChangedBy').val() || null,
                changedColumn: $('#filterChangedColumn').val() || null,
                devGUID,
                options: {
                  page,
                  limit,
                  sort,
                  search
                }
              }
            });

            callback({
              data: [],
              recordsTotal: 0,
              recordsFiltered: 0
            });
          }
        });
      },

      /**
       * Column definitions
       */
      columns: [
        { data: "timestamp" },
        { data: "changedBy" },
        { data: "devGUID" },
        { data: "changes" }
      ],

      columnDefs: [
        {
          targets: 0,
          render: data => localizeTimestamp(data)
        },
        {
          targets: 1,
          render: data => escHtml(data)
        },
        {
          targets: 2,
          render: function (data) {

            const guid = escHtml(data);
            const mac = getDevDataByGuid(guid, "devMac");
            const name = getDevDataByGuid(guid, "devName");

            return `
              <a href="deviceDetails.php?mac=${mac}" data-guid="${guid}">
                ${name} (${guid})
              </a>`;
          }
        },
        {
          targets: 3,
          orderable: false,
          searchable: false,

          render: function (changes) {

            if (!Array.isArray(changes)) return "";

            return changes.map(c => `
              <div>
                <code>${escHtml(c.changedColumn)}</code>:
                <span class="text-danger">${escHtml(c.oldValue || "∅")}</span>
                →
                <span class="text-success">${escHtml(c.newValue || "∅")}</span>
              </div>
            `).join("");
          }
        }
      ],

      language: {
        processing: '<i class="fa fa-spinner fa-spin"></i>',
        emptyTable: "<?= lang('device_history_empty_state'); ?>"
      }
    });
  }

  /**
   * =========================
   * Filters
   * =========================
   */
  function bindHistoryFilters() {

    $('#filterChangedBy, #filterChangedColumn').on('change', function () {
      if (historyTable) {
        showSpinner();
        historyTable.ajax.reload(null, true);
      }
    });
  }

  function populateFilters() {

    const apiBaseUrl = getApiBase();
    const apiEndpoint = '/devices/history/filters';

    let queryString = "";

    if (urlMac) {
      queryString += `?devGUID=${getDevDataByMac(urlMac, "devGUID")}`;
    }

    const url = `${apiBaseUrl}/${apiEndpoint}${queryString}`;

    $.ajax({
      url,
      method: 'GET',
      headers: {
        Authorization: 'Bearer ' + getSetting('API_TOKEN')
      },

      success: function (resp) {

        if (!resp.data) return;

        const byEl = document.getElementById('filterChangedBy');
        const colEl = document.getElementById('filterChangedColumn');

        (resp.data.changedBy || []).forEach(v => byEl.add(new Option(v, v)));
        (resp.data.changedColumn || []).forEach(v => colEl.add(new Option(v, v)));

        if ($.fn.dataTable.isDataTable('#changeHistoryTable')) {
          $('#changeHistoryTable').DataTable().ajax.reload();
        }
      }
    });
  }

  /**
   * =========================
   * Helpers
   * =========================
   */

  function escHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function getMacFromUrl() {
    return new URLSearchParams(window.location.search).get('mac');
  }

  /**
   * =========================
   * Page Init
   * =========================
   */
  function initChangeLogPage() {

    if ($('#panHistory').length !== 0 && !$('#panHistory:visible').length) {
      return;
    }

    if (changeLogPageInitialized) return;
    changeLogPageInitialized = true;

    showChangeLogSkeleton();
    showSpinner();

    populateFilters();
    initializeHistoryTable();
    bindHistoryFilters();
  }

  initLazyTab('#panHistory', function () {
    waitForAppReady(function () {
      initChangeLogPage();
    });
  });

  /**
   * =========================
   * Skeleton UI
   * =========================
   */
  function hideChangeLogSkeleton() {
    $('#change-log-skeleton').fadeOut(0, function () {
      $(this).hide();
    });
  }

  function showChangeLogSkeleton() {
    $('#change-log-skeleton')
      .stop(true, true)
      .fadeIn(0);
  }
</script>