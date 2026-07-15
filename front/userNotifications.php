<?php
require 'php/templates/header.php';
?>


<!-- iCheck -->
<link rel="stylesheet" href="lib/iCheck/all.css">
<script src="lib/iCheck/icheck.min.js"></script>

<!-- ----------------------------------------------------------------------- -->

<script>
  showSpinner();
</script>

<div id="notifications" class="content-wrapper">
<?php require 'php/templates/skel_notifications.php'; ?>
  <section class="content table-responsive">
    <div class="notification-box box box-gray col-xs-12" >
      <div class="box-header">
       <h3 class="box-title text-aqua"><?= lang('Notifications_All');?></h3>
      </div>
      <div class=" ">
        <table id="notificationsTable" class="table table-bordered table-hover table-striped display">
          <thead>
            <tr>
              <th><?= lang('gen_timestamp');?></th>
              <th><?= lang('gen_level');?></th>
              <th><?= lang('gen_content');?></th>
              <th>GUID</th>
              <th><?= lang('gen_read');?></th>
              <th><?= lang('gen_actions');?></th>
            </tr>
          </thead>
          <tbody>
            <!-- Data will be inserted here by DataTables -->
          </tbody>
        </table>

        <div class="notification-buttons">
          <button id="clearNotificationsBtn" class="btn btn-danger"><?= lang("Gen_DeleteAll");?></button>
          <button id="notificationsMarkAllRead" class="btn btn-default"><?= lang("Notifications_Mark_All_Read");?></button>
        </div>
      </div>

    </div>

  </section>


</div>


<script>
  function fetchData(callback) {
    $.get('php/server/query_json.php', { file: 'user_notifications.json', nocache: Date.now() })
    .done(function(response) {
        if (response == "[]" || response == "") {
            callback([]);
        } else if (response.error) {
            alert("Error: " + response.error);
            callback([]);
        } else if (!Array.isArray(response)) {
            alert("Unexpected response format");
            callback([]);
        } else {
            callback(response);
        }
    })
    .fail(function(xhr, status, error) {
        console.error("An error occurred while fetching data:", error);
        callback([]);
    });
  }

  $(document).ready(function() {
    const table = $('#notificationsTable').DataTable({
      "autoWidth": false,
      "pageLength": parseInt(getSetting("UI_DEFAULT_PAGE_SIZE")),
      'lengthMenu'   : getLengthMenu(parseInt(getSetting("UI_DEFAULT_PAGE_SIZE"))),
      "columns": [
        { "data": "timestamp" ,
          "render": function(data, type, row) {

            var result = data.toString(); // Convert to string
            if (result.includes("+")) { // Check if timezone offset is present
                result = result.split('+')[0]; // Remove timezone offset
            }

            // Keep sortable value for DataTables
            if (type === "sort" || type === "type" || type !== "display") {
                return result;
            }

            // Display localized date only
            result = localizeTimestamp(result);

            return result;
          }
        },
        {
          "data": "level",
          "render": function(data, type, row) {


            switch (data) {
              case "info":
                color = 'green'
                break;

              case "alert":
                color = 'yellow'
                break;

              case "interrupt":
                color = 'red'
                break;

              default:
                color = 'red'
                break;
            }

            return `<span title="" class="badge bg-${color}" style="display: inline;"> ${data} </span>`
          }
        },
        { "data": "content",
          "render": function(data, type, row) {
              if (data.includes("Report:")) {
                  var guid = data.split(":")[1].trim();
                  return `<a href="report.php?guid=${guid}">Go to Report</a>`;
                } else {
                  // clear quotes (") if wrapped in them
                  return (data.startsWith('"') && data.endsWith('"')) ? data.slice(1, -1) : data;
                }
          }
         },

        { "data": "guid",
          "render": function(data, type, row) {
            return `<button class="copy-btn btn btn-info btn-flat" data-text="${data}" title="copy" onclick="copyToClipboard(this)">
                    <i class="fa-solid fa-copy"></i>
                  </button>`;
          }
        },
        { "data": "read",
         "render": function(data, type, row) {
            if (data == 0) {
              return `<button class="mark-read-btn btn btn-info btn-flat" onclick="markNotificationAsRead('${row.guid}', this)">
                        Mark as Read
                      </button>`;
            } else {
              return `<i class="fa-solid fa-check"></i>`;
            }
          }

        },
        {
            targets: -1, // Target the last column
            data: 'guid', // Assuming 'guid' is the key for the unique identifier
              render: function(data, type, row) {
                  return `<button class="mark-read-btn btn btn-danger btn-flat" onclick="removeNotification('${data}', this)">
                            <i class="fa-solid fa-trash"></i>
                          </button>`;
              }
        }
      ],
      "columnDefs": [
        { "width": "15%", "targets": [0] }, // Set width of the first four columns to 10%
        { "width": "5%", "targets": [1,3] }, // Set width of the first four columns to 10%
        { "width": "50%", "targets": [2] }, // Set width of the first four columns to 10%
        { "width": "5%", "targets": [4,5] }, // Set width of the "Content" column to 60%

      ],
      "order": [[0, "desc"]]
    ,
    initComplete: function(settings, json) {
        hideSpinner(); // Called after the DataTable is fully initialized
        hideNotificationsSkeleton();
    }});

    fetchData(function(data) {
      table.clear().rows.add(data).draw();
    });


    const apiBase = getApiBase();
    const apiToken = getSetting("API_TOKEN");

    // Function to clear all notifications
    $('#clearNotificationsBtn').click(function() {
      $.ajax({
        url: `${apiBase}/messaging/in-app/delete`,
        type: 'DELETE',
        headers: { "Authorization": `Bearer ${apiToken}` },
        success: function(response) {
          // Clear the table and reload data
          window.location.reload()
        },
        error: function(xhr, status, error) {
          console.log("An error occurred while clearing notifications: " + error);
          // You can display an error message here if needed
        }
      });
    });

    // Function to mark all notifications as read
    $('#notificationsMarkAllRead').click(function() {
      $.ajax({
        url: `${apiBase}/messaging/in-app/read/all`,
        type: 'POST',
        headers: { "Authorization": `Bearer ${apiToken}` },
        success: function(response) {
          // Clear the table and reload data
          window.location.reload()
        },
        error: function(xhr, status, error) {
          console.log("An error occurred while marking notifications as read: " + error);
          // You can display an error message here if needed
        }
      });
    });


  });

function hideNotificationsSkeleton() {
  $('#notifications-skeleton').fadeOut(0, function () { $(this).remove(); });
}

window.addEventListener('load', function () {
  setTimeout(hideNotificationsSkeleton, 15000);
});

</script>

<?php
require 'php/templates/footer.php';
?>
