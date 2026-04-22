<!-- NetAlertX CSS -->
<link rel="stylesheet" href="css/app.css">

<?php

require_once $_SERVER['DOCUMENT_ROOT'].'/php/server/db.php';
require_once $_SERVER['DOCUMENT_ROOT'].'/php/templates/language/lang.php';
require_once $_SERVER['DOCUMENT_ROOT'].'/php/templates/security.php';

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

// if (session_status() === PHP_SESSION_NONE) {
//     session_start();
// }

// session_start();

const DEFAULT_REDIRECT = '/devices.php';

/* =====================================================
   LDAP Configuration
   $configLines is already loaded by security.php
===================================================== */

/**
 * Read LDAP_enabled from environment or app.conf.
 * Returns true only when the value is literally "true" (case-insensitive) or "1".
 */
$ldap_enabled = false;
$env_ldap = getenv('LDAP_ENABLED');
if ($env_ldap === false) $env_ldap = getenv('LDAP_enabled');

if ($env_ldap !== false && $env_ldap !== '') {
    $ldap_enabled = strtolower(trim($env_ldap)) === 'true' || trim($env_ldap) === '1';
} else {
    $ldap_enabled_line = getConfigLine('/^LDAP_enabled.*=/', $configLines);
    if ($ldap_enabled_line !== null && isset($ldap_enabled_line[1])) {
        $ldap_enabled_value = strtolower(trim($ldap_enabled_line[1]));
        $ldap_enabled = $ldap_enabled_value === 'true' || $ldap_enabled_value === '1';
    }
}

/**
 * Derive the Python API port from the GRAPHQL_PORT setting in app.conf.
 * Falls back to 20212 (the default) when not set.
 */
$gql_line = getConfigLine('/^GRAPHQL_PORT.*=/', $configLines);
$graphql_port = 20212;
if ($gql_line !== null && isset($gql_line[1])) {
    $parsed_port = (int) preg_replace('/[^0-9]/', '', $gql_line[1]);
    if ($parsed_port >= 1 && $parsed_port <= 65535) {
        $graphql_port = $parsed_port;
    }
}

$ldap_login_url = "http://127.0.0.1:{$graphql_port}/api/auth/login";

function get_api_token_from_config(array $configLines): string {
    $token_line = getConfigLine('/^API_TOKEN.*=/', $configLines);
    if ($token_line === null || !isset($token_line[1])) {
        return '';
    }

    return trim($token_line[1], " \t\n\r\0\x0B\"'");
}

/* =====================================================
   Helper Functions
===================================================== */

function safe_redirect(string $path): void {
    header("Location: {$path}", true, 302);
    exit;
}

function validate_local_path(?string $encoded): string {
    if (!$encoded) return DEFAULT_REDIRECT;

    $decoded = base64_decode($encoded, true);
    if ($decoded === false) {
        return DEFAULT_REDIRECT;
    }

    // strict local path check (allow safe query strings + fragments)
    // Using ~ as the delimiter instead of #
    if (!preg_match('~^(?!//)(?!.*://)/[a-zA-Z0-9_\-./?=&:%#]*$~', $decoded)) {
        return DEFAULT_REDIRECT;
    }

    return $decoded;
}

function extract_hash_from_path(string $path): array {
    /*
    Split a path into path and hash components.

    For deep links encoded in the 'next' parameter like /devices.php#device-123,
    extract the hash fragment so it can be properly included in the redirect.

    Args:
        path: Full path potentially with hash (e.g., "/devices.php#device-123")

    Returns:
        Array with keys 'path' (without hash) and 'hash' (with # prefix, or empty string)
    */
    $parts = explode('#', $path, 2);
    return [
        'path' => $parts[0],
        'hash' => !empty($parts[1]) ? '#' . $parts[1] : ''
    ];
}

function append_hash(string $url): string {
    // First check if the URL already has a hash from the deep link
    $parts = extract_hash_from_path($url);
    if (!empty($parts['hash'])) {
        return $parts['path'] . $parts['hash'];
    }

    // Fall back to POST url_hash (for browser-captured hashes)
    if (!empty($_POST['url_hash'])) {
        $sanitized = preg_replace('/[^#a-zA-Z0-9_\-]/', '', $_POST['url_hash']);
        if (str_starts_with($sanitized, '#')) {
            return $url . $sanitized;
        }
    }
    return $url;
}

function is_authenticated(): bool {
    return isset($_SESSION['login']) && $_SESSION['login'] === 1;
}

function login_user(): void {
    global $nax_Password, $api_token, $configLines;

    $resolved_api_token = !empty($api_token)
        ? $api_token
        : get_api_token_from_config($configLines);

    if (empty($resolved_api_token)) {
        throw new RuntimeException('API_TOKEN is not configured');
    }

    $_SESSION['login'] = 1;
    session_regenerate_id(true);
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));

    // Set remember-me cookie with HMAC (not raw password hash)
    $cookie_value = hash_hmac('sha256', $nax_Password, $resolved_api_token);
    setcookie(COOKIE_SAVE_LOGIN_NAME, $cookie_value, [
        'expires'  => time() + 3600 * 24 * 7,
        'path'     => '/',
        'httponly'  => true,
        'secure'   => !empty($_SERVER['HTTPS']),
        'samesite' => 'Strict',
    ]);
}


function logout_user(): void {
    $_SESSION = [];
    session_destroy();
}

/* =====================================================
   Redirect Handling
===================================================== */

$redirectTo = validate_local_path($_GET['next'] ?? null);

/* =====================================================
   Web Protection Disabled
===================================================== */

if ($nax_WebProtection !== 'true') {
    if (!is_authenticated()) {
        login_user();
    }
    safe_redirect(append_hash($redirectTo));
}

/* =====================================================
   Login Attempt
===================================================== */

if (!empty($_POST['loginpassword']) &&
    isset($_POST['csrf_token']) &&
    hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {

    if ($ldap_enabled) {
        // LDAP path: delegate credential validation to the Python API.
        // The API token is required so only server-side callers can reach the endpoint.
        $resolved_api_token = !empty($api_token)
            ? $api_token
            : get_api_token_from_config($configLines);

        if (empty($resolved_api_token)) {
            throw new RuntimeException('API_TOKEN is not configured');
        }

        $ldap_payload = json_encode([
            'username' => isset($_POST['loginusername']) ? trim($_POST['loginusername']) : '',
            'password' => $_POST['loginpassword'],
        ]);
        $stream_opts = [
            'http' => [
                'method'        => 'POST',
                'header'        => "Content-Type: application/json\r\n"
                                 . "Authorization: Bearer " . $resolved_api_token . "\r\n"
                                 . "X-Forwarded-For: " . ($_SERVER['REMOTE_ADDR'] ?? '127.0.0.1') . "\r\n",
                'content'       => $ldap_payload,
                'timeout'       => 5,
                'ignore_errors' => true,
            ]
        ];
        $ctx      = stream_context_create($stream_opts);
        $raw      = @file_get_contents($ldap_login_url, false, $ctx);
        $api_resp = ($raw !== false) ? @json_decode($raw, true) : null;

        if (is_array($api_resp) && $api_resp['success'] === true) {
            login_user();
            safe_redirect(append_hash($redirectTo));
        }
        // Fall through to show the login form with an error state.
    } else {
        // Local path: compare SHA-256 digest against the stored hash (same as before).
        $incomingHash = hash('sha256', $_POST['loginpassword']);

        if (hash_equals($nax_Password, $incomingHash)) {
            login_user();

            // Redirect to target page, preserving deep link hash if present
            safe_redirect(append_hash($redirectTo));
        }
    }
}

/* =====================================================
   Already Logged In
===================================================== */

if (is_authenticated()) {
    safe_redirect(append_hash($redirectTo));
}

/* =====================================================
   Login UI Variables
===================================================== */

$login_headline = lang('Login_Toggle_Info_headline');
$login_info     = lang('Login_Info');
$login_mode     = 'info';
$login_display_mode = 'display:none;';
$login_icon     = 'fa-info';

if ($nax_Password === '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92') {
    $login_info = lang('Login_Default_PWD');
    $login_mode = 'danger';
    $login_display_mode = 'display:block;';
    $login_headline = lang('Login_Toggle_Alert_headline');
    $login_icon = 'fa-ban';
}
?>

<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="Pragma" content="no-cache" />
  <meta http-equiv="Expires" content="0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>NetAlert X | Log in</title>
  <!-- Tell the browser to be responsive to screen width -->
  <meta content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" name="viewport">
  <!-- Bootstrap 3.3.7 -->
  <link rel="stylesheet" href="lib/bootstrap/bootstrap.min.css">
  <!-- Ionicons -->
  <link rel="stylesheet" href="lib/Ionicons/ionicons.min.css">
  <!-- Theme style -->
  <link rel="stylesheet" href="lib/AdminLTE/dist/css/AdminLTE.min.css">
  <!-- iCheck -->
  <link rel="stylesheet" href="lib/iCheck/square/blue.css">
  <!-- Font Awesome -->
  <link rel="stylesheet" href="lib/font-awesome/all.min.css">

  <!-- Favicon -->
  <link id="favicon" rel="icon" type="image/x-icon" href="img/NetAlertX_logo.png">
  <link rel="stylesheet" href="/css/offline-font.css">
</head>
<body class="hold-transition login-page col-sm-12 col-sx-12">
<div class="login-box login-custom">
  <div class="login-logo">
    <a href="/index2.php">Net<b>Alert</b><sup>x</sup></a>
  </div>
  <!-- /.login-logo -->
  <div class="login-box-body">
    <p class="login-box-msg"><?= lang('Login_Box');?></p>
      <form action="index.php<?php
      echo !empty($_GET['next'])
          ? '?next=' . htmlspecialchars($_GET['next'], ENT_QUOTES, 'UTF-8')
          : '';
      ?>" method="post">
      <?php if ($ldap_enabled): ?>
      <div class="form-group has-feedback">
        <input type="text" class="form-control"
               placeholder="<?= lang('Login_Username');?>"
               name="loginusername"
               autocomplete="username"
               required>
        <span class="glyphicon glyphicon-user form-control-feedback"></span>
      </div>
      <?php endif; ?>
      <div class="form-group has-feedback">
        <input type="hidden" name="url_hash" id="url_hash">
        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token'], ENT_QUOTES, 'UTF-8') ?>">
        <input type="password" class="form-control" placeholder="<?= lang('Login_Psw-box');?>" name="loginpassword">
        <span class="glyphicon glyphicon-lock form-control-feedback"></span>
      </div>
      <div class="row">
        <div class="col-xs-12">
          <button type="submit" class="btn btn-primary btn-block btn-flat"><?= lang('Login_Submit');?></button>
        </div>
        <!-- /.col -->
      </div>
    </form>

    <div style="padding-top: 10px;">
      <button class="btn btn-xs btn-primary btn-block btn-flat" onclick="Passwordhinfo()"><?= lang('Login_Toggle_Info');?></button>
    </div>

  </div>
  <!-- /.login-box-body -->

  <div id="myDIV" class="box-body" style="margin-top: 50px; <?php echo $login_display_mode;?>">
      <div class="alert alert-<?php echo $login_mode;?> alert-dismissible">
          <button type="button" class="close" onclick="Passwordhinfo()" aria-hidden="true">X</button>
          <h4><i class="icon fa <?php echo $login_icon;?>"></i><?php echo $login_headline;?></h4>
          <p><?php echo $login_info;?></p>
      </div>
  </div>


</div>
<!-- /.login-box -->


<!-- jQuery 3 -->
<script src="lib/jquery/jquery.min.js"></script>

<!-- iCheck -->
<script src="lib/iCheck/icheck.min.js"></script>
<script>
  if (window.location.hash) {
      document.getElementById('url_hash').value = window.location.hash;
  }
  $(function () {
    $('input').iCheck({
      checkboxClass: 'icheckbox_square-blue',
      radioClass: 'iradio_square-blue',
      increaseArea: '20%' /* optional */
    });
  });

function Passwordhinfo() {
  var x = document.getElementById("myDIV");
  if (x.style.display === "none") {
    x.style.display = "block";
  } else {
    x.style.display = "none";
  }
}

</script>
</body>
</html>
