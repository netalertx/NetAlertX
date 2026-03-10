<?php

// ---- IMPORTS ----
// Check if authenticated - also populates $api_token and $configLines from app.conf
require_once $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
// getSettingValue() reads from Python-generated table_settings.json (reliable runtime source)
require_once dirname(__FILE__) . '/init.php';
// ---- IMPORTS ----

// Only respond to GET requests
if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    http_response_code(405);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// API_TOKEN: security.php extracts it from app.conf but the value is empty until Python
// initialise.py runs. Fall back to table_settings.json (runtime source of truth).
$resolved_token = !empty($api_token) ? $api_token : getSettingValue('API_TOKEN');

// GRAPHQL_PORT: format in app.conf is bare integer — GRAPHQL_PORT=20212 (no quotes)
$graphql_port_raw = getConfigLine('/^GRAPHQL_PORT\s*=/', $configLines);
$graphql_port = isset($graphql_port_raw[1]) ? (int) trim($graphql_port_raw[1]) : 20212;

// Validate we have something useful before returning
if (empty($resolved_token) || str_starts_with($resolved_token, 'Could not')) {
    http_response_code(500);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'Could not read API_TOKEN from configuration']);
    exit;
}

header('Content-Type: application/json');
echo json_encode([
    'api_token'    => $resolved_token,
    'graphql_port' => $graphql_port,
]);
