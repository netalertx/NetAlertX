// =============================================================================
// devices-totals.js — Devices list page: tile-card totals.
//
// Fetches per-status device counts and renders them as the tile cards at the
// top of devices.php (#TileCards).
// =============================================================================

//------------------------------------------------------------------------------
//  Query total numbers of Devices by status
//------------------------------------------------------------------------------
function getDevicesTotals() {
    maxDelay = 180; //cap at 180 seconds

    let maxRetries = Math.ceil(Math.log2(maxDelay)); // Calculate maximum retries to cap at maxDelay seconds
    let attempt = 0;
    let calledUpdateAPI = false;

    function fetchDataWithBackoff() {
        // Calculate the delay (2^attempt seconds, capped at maxDelay seconds)
        const delay = Math.min(2 ** attempt, maxDelay) * 1000;

        // Attempt to fetch data
        $.ajax({
            url: 'php/server/query_json.php',
            type: "GET",
            dataType: "json",
            data: {
                file: 'table_devices_tiles.json', // Pass the file parameter
                nocache: Date.now() // Prevent caching with a timestamp
            },
            success: function(response) {
                if (response && response.data) {
                    const resultJSON = response.data[0]; // Assuming the structure {"data": [ ... ]}

                    // Save the result to cache
                    setCache("getDevicesTotals", JSON.stringify(resultJSON));

                    // Process the fetched data
                    processDeviceTotals(resultJSON);
                } else {
                    console.error("Invalid response format from API");
                }
            },
            error: function(xhr, status, error) {
                console.error("Failed to fetch devices data (Attempt " + (attempt + 1) + "):", error);

                //  try updating the API once
                if(calledUpdateAPI == false)
                {
                  calledUpdateAPI = true;
                  updateApi("devices_tiles");
                }

                // Retry logic
                if (attempt < maxRetries) {
                    attempt++;
                    setTimeout(fetchDataWithBackoff, delay);
                } else {
                    console.error("Maximum retries reached. Unable to fetch devices data.");
                }
            }
        });
    }

    // Start the first fetch attempt
    fetchDataWithBackoff();
}

function processDeviceTotals(devicesData) {
  // Define filter conditions and corresponding objects
  const filters = [
    { status: 'my_devices',         color: 'bg-aqua',   label: getString('Device_Shortcut_AllDevices'), icon: 'fa-laptop' },
    { status: 'all',                color: 'bg-aqua',   label: getString('Gen_All_Devices'),            icon: 'fa-laptop' },
    { status: 'connected',          color: 'bg-green',  label: getString('Device_Shortcut_Connected'),  icon: 'fa-plug' },
    { status: 'favorites',          color: 'bg-yellow', label: getString('Device_Shortcut_Favorites'),  icon: 'fa-star' },
    { status: 'new',                color: 'bg-yellow', label: getString('Device_Shortcut_NewDevices'), icon: 'fa-plus' },
    { status: 'down',               color: 'bg-red',    label: getString('Device_Shortcut_DownOnly'),   icon: 'fa-warning' },
    { status: 'archived',           color: 'bg-gray',   label: getString('Device_Shortcut_Archived'),   icon: 'fa-eye-slash' },
    { status: 'offline',            color: 'bg-gray',   label: getString('Gen_Offline'),                icon: 'fa-xmark' },
    { status: 'all_devices',        color: 'bg-gray',   label: getString('Gen_All_Devices'),            icon: 'fa-laptop' },
    { status: 'network_devices',    color: 'bg-aqua',   label: getString('Network_Devices'),            icon: 'fa-sitemap fa-rotate-270' }
  ];

  // Initialize an empty array to store the final objects
  let dataArray = [];

  // Loop through each filter condition
  filters.forEach(filter => {
    // Get count directly from API response data
    let count = devicesData[filter.status] || 0;

    // Check any condition to skip adding the object to dataArray
    if (
      (['', 'False'].includes(getSetting('UI_hide_empty')) || (getSetting('UI_hide_empty') == "True" && count > 0)) &&
      (getSetting('UI_shown_cards') == "" || getSetting('UI_shown_cards').includes(filter.status))
    ) {
      dataArray.push({
        onclickEvent: `forceLoadUrl('devices.php#${filter.status}')`,
        color: filter.color,
        title: count,
        label: filter.label,
        icon: filter.icon
      });
    }
  });

  // Render info boxes/tile cards
  renderInfoboxes(dataArray);
}

//------------------------------------------------------------------------------
//  Render the info boxes/tiles on top
function renderInfoboxes(customData) {
  if(customData.length > 0)
  {
    $.ajax({
      url: 'php/components/tile_cards.php', // PHP script URL
      type: 'POST', // Use POST method to send data
      dataType: 'html', // Expect HTML response
      data: { items: JSON.stringify(customData) }, // Send customData as JSON
      success: function(response) {
        $('#TileCards').html(response); // Replace container content with fetched HTML
      },
      error: function(xhr, status, error) {
        console.error('Error fetching infoboxes:', error);
      }
    });
  }
}
