<!-- NetAlertX CSS -->
<link rel="stylesheet" href="css/app.css">

<?php

require_once $_SERVER['DOCUMENT_ROOT'].'/php/server/db.php';
require_once $_SERVER['DOCUMENT_ROOT'].'/php/templates/language/lang.php';
require_once $_SERVER['DOCUMENT_ROOT'].'/php/templates/security.php';

const DEFAULT_REDIRECT = '/devices.php';

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
    $_SESSION['login'] = 1;
    session_regenerate_id(true);
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

if (!empty($_POST['loginpassword'])) {

    $incomingHash = hash('sha256', $_POST['loginpassword']);

    if (hash_equals($nax_Password, $incomingHash)) {

        login_user();

        // Redirect to target page, preserving deep link hash if present
        safe_redirect(append_hash($redirectTo));
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
      <div class="form-group has-feedback">
        <input type="hidden" name="url_hash" id="url_hash">
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
