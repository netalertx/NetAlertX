<?php
if (session_status() == PHP_SESSION_NONE) {
    session_start();
}

$isAuthenticated = false;

// Check if the user is logged in
if (isset($_SESSION["login"]) && $_SESSION["login"] == 1) {
    $isAuthenticated = true;
}

// $current_directory = __DIR__;
// echo "Current directory: " . $current_directory;

// Check if a valid cookie is present
$CookieSaveLoginName = "NetAlertX_SaveLogin";

// Use environment-aware config path
$configFolderPath = rtrim(getenv('NETALERTX_CONFIG') ?: '/data/config', '/');
$config_file = $configFolderPath . '/app.conf';

// Fallback to legacy path if new location doesn't exist
if (!file_exists($config_file)) {
    $legacyPath = "../../../config/app.conf";
    if (file_exists($legacyPath)) {
        $config_file = $legacyPath;
    }
}

$config_file_lines = file($config_file);
$config_file_lines_pw = array_values(preg_grep('/^SETPWD_password.*=/', $config_file_lines));
$password_line = explode("'", $config_file_lines_pw[0]);
$nax_Password = $password_line[1];

$config_file_lines_token = array_values(preg_grep('/^API_TOKEN.*=/', $config_file_lines));
$api_token = !empty($config_file_lines_token) ? explode("'", $config_file_lines_token[0])[1] : '';

$expected_cookie = hash_hmac('sha256', $nax_Password, $api_token);
if (isset($_COOKIE[$CookieSaveLoginName]) && hash_equals($expected_cookie, $_COOKIE[$CookieSaveLoginName])) {
    $isAuthenticated = true;
}

if ($isAuthenticated) {
    echo 'Authorized 200';
    http_response_code(200);
    exit;  // Important: Ensure script exits after successful authentication
} else {
    http_response_code(401);
    echo 'Unauthorized 401';
    exit;  // Ensure script exits after failed authentication
}
?>
