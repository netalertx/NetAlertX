// =============================================================================
// devices-filters.js — Devices list page: column filter dropdowns.
//
// Fetches the available filter values, renders the filter dropdowns, and
// collects the currently-selected filter values for the DataTable's ajax
// query (see devices-table.js).
// =============================================================================

// -----------------------------------------------------------------------------
//Render filters if specified
// NOTE: this is the only top-level `let` among the devices-*.js files (everything
// else is `var`) — a second top-level `let`/`const columnFilters` anywhere else
// on this page would throw a page-breaking SyntaxError at parse time, unlike a
// duplicate `var` which is silently allowed. Keep this declaration unique.
let columnFilters = [];

function initFilters() {
    // Attempt to fetch data
    $.ajax({
        url: 'php/server/query_json.php',
        type: "GET",
        dataType: "json",
        data: {
            file: 'table_devices_filters.json', // Pass the file parameter
            nocache: Date.now() // Prevent caching with a timestamp
        },
        success: function(response) {
            if (response && response.data) {

                let resultJSON = response.data;

                // Save the result to cache
                setCache("devicesFilters", JSON.stringify(resultJSON));

                // Get the displayed filters from settings
                const displayedFilters = createArray(getSetting("UI_columns_filters"));

                // Clear any existing filters in the DOM
                $('#columnFilters').empty();

                // Ensure displayedFilters is an array and not empty
                if (Array.isArray(displayedFilters) && displayedFilters.length > 0) {
                    $('#columnFiltersWrap').removeClass("hidden");

                    displayedFilters.forEach(columnHeaderStringKey => {
                      // Get the column name using the mapping function
                      const columnName = getColumnNameFromLangString(columnHeaderStringKey);

                      // Ensure columnName is valid before proceeding
                      if (columnName) {
                          // Add the filter to the columnFilters array as [columnName, columnHeaderStringKey]
                          columnFilters.push([columnName, columnHeaderStringKey]);
                      } else {
                          console.warn(`Invalid column header string key: ${columnHeaderStringKey}`);
                      }
                    });

                    // Filter resultJSON to include only entries with columnName in columnFilters
                    resultJSON = resultJSON.filter(entry =>
                        columnFilters.some(filter => filter[0] === entry.columnName)
                    );

                    // Expand resultJSON to include the columnHeaderStringKey
                    resultJSON.forEach(entry => {
                        // Find the matching columnHeaderStringKey from columnFilters
                        const matchingFilter = columnFilters.find(filter => filter[0] === entry.columnName);

                        // Add the columnHeaderStringKey to the entry
                        if (matchingFilter) {
                            entry['columnHeaderStringKey'] = matchingFilter[1];
                        }
                    });

                    console.log(resultJSON);

                    // Transforming the data
                    const transformed = {
                      filters: []
                    };

                    // Build filters in the exact order of columnFilters
                    columnFilters.forEach(([columnName, headerKey]) => {
                      // Get matching entries for this column
                      const entries = resultJSON.filter(e => e.columnName === columnName);

                      if (entries.length === 0) return;

                      // Build options (unique)
                      const optionsMap = new Map();

                      entries.forEach(entry => {
                        const value = entry.columnValue;
                        const label = entry.columnLabel || value;

                        if (!optionsMap.has(value)) {
                          optionsMap.set(value, { value, label });
                        }
                      });

                      const options = Array.from(optionsMap.values());

                      // Sort options alphabetically
                      options.sort((a, b) => a.label.localeCompare(b.label));

                      transformed.filters.push({
                        column: columnName,
                        headerKey: headerKey,
                        options: options
                      });
                    });

                    // Sort options alphabetically by label for better readability
                    transformed.filters.forEach(filter => {
                      filter.options.sort((a, b) => a.label.localeCompare(b.label));
                    });

                    // Output the result
                    transformedJson =  transformed

                    // Process the fetched data
                    renderFilters(transformedJson);
                } else {
                    console.log("No filters to display.");
                }
            } else {
                console.error("Invalid response format from API");
            }
        },
        error: function(xhr, status, error) {
            console.error("Failed to fetch devices data 'table_devices_filters.json':", error);
        }
    });
}


// -------------------------------------------
// Server side component
function renderFilters(customData) {

  // console.log(JSON.stringify(customData));

  // Load filter data from the JSON file
  $.ajax({
    url: 'php/components/devices_filters.php', // PHP script URL
    data: { filterObject: JSON.stringify(customData) }, // Send customData as JSON
    type: 'POST',
    dataType: 'html',
    success: function(response) {
      // console.log(response);

      $('#columnFilters').html(response); // Replace container content with fetched HTML
      $('#columnFilters').removeClass('hidden'); // Show the filters container

      // Trigger the draw after select change
      $('.filter-dropdown').on('change', function() {
          // Collect filters
          const columnFilters = collectFilters();

          // Apply column filters then draw once (previously drew twice — bug fixed).
          const table = $('#tableDevices').DataTable();
          table.columnFilters = columnFilters;
          table.draw();
      });

    },
    error: function(xhr, status, error) {
      console.error('Error fetching filters:', error);
    }
  });
}

// -------------------------------------------
// Function to collect filters
function collectFilters() {
    const columnFilters = [];

    // Loop through each filter group
    document.querySelectorAll('.filter-group').forEach(filterGroup => {
        const dropdown = filterGroup.querySelector('.filter-dropdown');

        if (dropdown) {
            const filterColumn = dropdown.getAttribute('data-column');
            const filterValue = dropdown.value;

            if (filterValue && filterColumn) {
                columnFilters.push({
                    filterColumn: filterColumn,
                    filterValue: filterValue
                });
            }
        }
    });

    return columnFilters;
}
