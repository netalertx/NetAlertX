<?php

    //------------------------------------------------------------------------------
    // check if authenticated
    require_once  $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';

?>

<script src="js/graph_online_history.js"></script>
<script >


  if (isAppInitialized()) {
    initOnlineHistoryGraph();
  } else {
    callAfterAppInitialized(() => initOnlineHistoryGraph());
  }


function initOnlineHistoryGraph() {
    $.get('php/server/query_json.php', { file: 'table_online_history.json', nocache: Date.now() }, function(res) {
        // Extracting data from the JSON response
        var timeStamps = [];
        var onlineCounts = [];
        var downCounts = [];
        var offlineCounts = [];
        var archivedCounts = [];

        res.data.forEach(function(entry) {

            var formattedTime = localizeTimestamp(entry.Scan_Date).slice(11, 17);

            timeStamps.push(formattedTime);
            onlineCounts.push(entry.Online_Devices);
            downCounts.push(entry.Down_Devices);
            offlineCounts.push(entry.Offline_Devices);
            archivedCounts.push(entry.Archived_Devices);
        });

        // Call your presenceOverTime function after data is ready
        presenceOverTime(
            timeStamps,
            onlineCounts,
            offlineCounts,
            archivedCounts,
            downCounts
        );
    }).fail(function() {
        // Handle any errors in fetching the data
        console.error('Error fetching online history data.');
    });
}

</script>
<!-- <canvas id="clientsChart" width="800" height="140" class="extratooltipcanvas no-user-select"></canvas> -->
<canvas id="OnlineChart" style="width:100%; height: 150px;  margin-bottom: 15px;"></canvas>
