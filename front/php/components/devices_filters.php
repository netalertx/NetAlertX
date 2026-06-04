<?php

//------------------------------------------------------------------------------
// Check if authenticated
require_once $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
require_once $_SERVER['DOCUMENT_ROOT'] . '/php/server/db.php';
require_once $_SERVER['DOCUMENT_ROOT'] . '/php/templates/language/lang.php';

// Function to render a filter dropdown
function renderFilterDropdown($headerKey, $columnName, $values) {
    // Generate dropdown options
    $optionsHtml = '<option value="" selected>All</option>'; // Default "All" option
    foreach ($values as $item) {
        // Support both {value, label} objects and plain strings (backward compat)
        if (is_array($item)) {
            $val   = $item['value'] ?? '';
            $label = $item['label'] ?? $val;
        } else {
            $val   = $item;
            $label = $item;
        }
        $escapedValue = htmlspecialchars($val);
        $escapedLabel = htmlspecialchars($label);
        $optionsHtml .= '<option value="' . $escapedValue . '">' . $escapedLabel . '</option>';
    }

    // Generate the dropdown HTML
    return '
    <div class="filter-group input-group">
        <label for="filter_' . htmlspecialchars($columnName) . '">' . lang($headerKey) . ': </label>
        <select id="filter_' . htmlspecialchars($columnName) . '" class="filter-dropdown" data-column="' . htmlspecialchars($columnName) . '">
            ' . $optionsHtml . '
        </select>
    </div>';
}

// Get filterObject from POST data
$filterObject = isset($_POST['filterObject']) ? json_decode($_POST['filterObject'], true) : [];

// Validate filterObject structure
if (!isset($filterObject['filters']) || !is_array($filterObject['filters'])) {
    echo '<p class="error">Invalid filter data provided.</p>';
    exit();
}

// Generate HTML for each filter in the filterObject
$html = '';
foreach ($filterObject['filters'] as $filter) {
    if (isset($filter['column'], $filter['headerKey'], $filter['options'])) {
        $html .= renderFilterDropdown($filter['headerKey'], $filter['column'], $filter['options']);
    } else {
        // Skip invalid entries
        continue;
    }
}

// Output the generated HTML
echo $html;
exit();

?>
