<?php

  require 'php/templates/header.php';
  require 'php/templates/modals.php';

?>

<script>
  showSpinner();
</script>

<!-- Page ------------------------------------------------------------------ -->
<div class="content-wrapper">

<!-- Content header--------------------------------------------------------- -->
    <!-- Main content ---------------------------------------------------------- -->
    <section class="content tab-content">

      <div class="box box-gray col-xs-12" >
        <div class="box-header">
              <h3 class="box-title text-aqua"><?= lang('Reports_Sent_Log');?></h3>
        </div>
        <div class="box-body  table-responsive ">
          <!-- Top level <> buttons, Format selection etc.  -->
          <div class="col-sm-2">
            <!-- Display data and navigation buttons -->
            <div id="notificationContainer">
              <div id="navigationButtons">
                    <button class="btn btn-default text-gray50" id="prevButton">
                      <i class="fa fa-chevron-left"></i>
                    </button>
                    <span id="notificationOutOff"></span>
                    <button class="btn btn-default text-gray50" id="nextButton">
                      <i class="fa fa-chevron-right"></i>
                    </button>
              </div>
            </div>
          </div>

          <!-- Select format -->
          <div class="col-sm-2 ">
            <label for="formatSelect">
              <?= lang('report_select_format') ;?>
            </label>
            <select id="formatSelect" class="pointer">
                <option value="HTML">HTML</option>
                <option value="JSON">JSON</option>
                <option value="Text">Text</option>
            </select>
          </div>


          <div class="col-sm-4">
            <label><?= lang('report_time') ;?></label>
            <span id="timestamp"></span>
          </div>

          <div class="col-sm-4">
            <label><?= lang('report_guid') ;?></label>
            <span id="guid"></span>
          </div>


          <div class="col-sm-12" id="notificationData">
              <!-- Data will be displayed here -->
          </div>

        </div>
      </div>
    </div>
  </section>

  <!-- JavaScript to fetch and display data based on selected format -->
  <script>
  // JavaScript to fetch and display data based on selected format
  document.addEventListener('DOMContentLoaded', function() {
    const notificationData = document.getElementById('notificationData');
    const timestamp = document.getElementById('timestamp');
    const notiGuid = document.getElementById('guid');
    const prevButton = document.getElementById('prevButton');
    const nextButton = document.getElementById('nextButton');
    const formatSelect = document.getElementById('formatSelect');

    let currentIndex = -1; // Current report index

    // Function to update the displayed data and timestamp based on the selected format and index
    function updateData(format, index) {
        // Fetch data from the API endpoint
        fetch(`php/server/query_json.php?file=table_notifications.json&nocache=${Date.now()}`)
            .then(response => response.json())
            .then(data => {
                if (index < 0) {
                    index = data.data.length - 1;
                } else if (index >= data.data.length) {
                    index = 0;
                }

                const notification = data.data[index];
                const formatData = notification[format];

                // Display the selected format data and update timestamp
                switch (format) {
                    case 'HTML':
                        notificationData.innerHTML = formatData;
                        break;
                    case 'JSON':
                        notificationData.innerHTML = `<pre class="logs" cols="70" rows="10" wrap="off" readonly="">
                                                      ${jsonSyntaxHighlight(JSON.stringify(JSON.parse(formatData), undefined, 4))}
                                                    </pre>`;
                        break;
                    case 'Text':
                        notificationData.innerHTML = `<pre class="logs" cols="70" rows="10" wrap="off" readonly">${formatData}</pre>`;
                        break;
                }

                // console.log(notification)

                timestamp.textContent = localizeTimestamp(notification.DateTimeCreated);
                notiGuid.textContent = notification.GUID;
                currentIndex = index;

                $("#notificationOutOff").html(`${currentIndex + 1}/${data.data.length}`);
            })
            .catch(error => {
                console.error('Error:', error);
            })
            .finally(() => {
                hideSpinner(); // always called, even if error occurred
            });
    }

    // Function to find the index of a notification by GUID
    function findIndexByGUID(data, guid) {
        return data.findIndex(notification => notification.GUID == guid);
    }

    // Listen for format selection changes
    formatSelect.addEventListener('change', () => {
        updateData(formatSelect.value, currentIndex);
    });

    // Listen for previous button click
    prevButton.addEventListener('click', () => {
        updateData(formatSelect.value, currentIndex - 1);
    });

    // Listen for next button click
    nextButton.addEventListener('click', () => {
        updateData(formatSelect.value, currentIndex + 1);
    });

    // Check if there is a GUID query parameter
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('guid')) {
        const guid = urlParams.get('guid');
        fetch('php/server/query_json.php?file=table_notifications.json')
            .then(response => response.json())
            .then(data => {
                const index = findIndexByGUID(data.data, guid);

                console.log(index)

                if (index == -1) {
                  showModalOk('WARNING', `${getString("report_guid_missing")} <br/> <br/> <code>${guid}</code>`)
                }

                // Load the notification with the specified GUID
                updateData(formatSelect.value, index);

            })
            .catch(error => {
                console.error('Error:', error);
            });
    } else {

        // Initial data load
        updateData('HTML', -1); // Default format to HTML and load the latest report
    }
});



  </script>

    <!-- /.content -->
    <?php
      require 'php/templates/footer.php';
    ?>
  </div>
  <!-- /.content-wrapper -->

<!-- ----------------------------------------------------------------------- -->
