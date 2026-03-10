<?php

require '../server/init.php';

//------------------------------------------------------------------------------
// Check if authenticated
require_once $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';

function renderSmallBox($params) {
    $onclickEvent = isset($params['onclickEvent']) ? $params['onclickEvent'] : '';
    $color = isset($params['color']) ? $params['color'] : '';
    $headerId = isset($params['headerId']) ? $params['headerId'] : '';
    $headerStyle = isset($params['headerStyle']) ? $params['headerStyle'] : '';
    $labelLang = isset($params['labelLang']) ? $params['labelLang'] : '';
    $iconId = isset($params['iconId']) ? $params['iconId'] : '';
    $iconClass = isset($params['iconClass']) ? $params['iconClass'] : '';
    $iconHtml = isset($params['iconHtml']) ? $params['iconHtml'] : '';
    $dataValue = isset($params['dataValue']) ? $params['dataValue'] : '';

    return '
        <div class="col-lg-3 col-sm-6 col-xs-6">
            <div style="cursor:pointer" onclick="javascript: ' . htmlspecialchars($onclickEvent) . '">
                <div class="small-box ' . htmlspecialchars($color) . '" style="pointer-events:none">
                    <div class="inner">
                        <div class="col-lg-6 col-sm-6 col-xs-6">
                            <div class="small-box-text col-lg-12 col-sm-12 col-xs-12" id="' . htmlspecialchars($headerId) . '" style="' . htmlspecialchars($headerStyle) . '"> <b>' . htmlspecialchars($dataValue) . '</b> </div>
                        </div>
                        <div class="infobox_label col-lg-6 col-sm-6 col-xs-6">' . lang(htmlspecialchars($labelLang)) . '</div>
                    </div>
                    <div class="icon">
                        ' . ($iconHtml ? $iconHtml : '<i id="' . htmlspecialchars($iconId) . '" class="' . htmlspecialchars($iconClass) . '"></i>') . '
                    </div>
                </div>
            </div>
        </div>';
}

// Load default data from JSON file
$defaultDataFile = 'device_cards_defaults.json';
$defaultData = file_exists($defaultDataFile) ? json_decode(file_get_contents($defaultDataFile), true) : [];

// Decode raw JSON input from body
$requestBody = file_get_contents('php://input');
$data = json_decode($requestBody, true);

// Debugging logs
if (json_last_error() !== JSON_ERROR_NONE) {
    error_log('JSON Decode Error: ' . json_last_error_msg());
    error_log('Raw body: ' . $requestBody);
    $data = null;
}

// Extract 'items' or fall back to default data
$items = isset($data['items']) ? $data['items'] : $defaultData;

// Generate HTML
$html = '<div class="row">';
foreach ($items as $item) {
    $html .= renderSmallBox($item);
}
$html .= '</div>';

// Output generated HTML
echo $html;
exit();
?>
