<!-- ---------------------------------------------------------------------------
#  NetAlertX
#  Open Source Network Guard / WIFI & LAN intrusion detector
#
#  header.php - Front module. Common header to all the web pages
#-------------------------------------------------------------------------------
#  Puche 2021 / 2022+ jokob             jokob@duck.com                GNU GPLv3
#--------------------------------------------------------------------------- -->

<?php
  require dirname(__FILE__).'/../server/init.php';
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once  $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';

?>

<!DOCTYPE html>
<html>

<!-- ----------------------------------------------------------------------- -->
<head>
  <meta charset="utf-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <title>NetAlertX - <?php echo gethostname();?></title>

  <!-- Tell the browser to be responsive to screen width -->
  <meta content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" name="viewport">
  <!-- ----------------------------------------------------------------------- -->
  <!-- REQUIRED JS SCRIPTS -->
  <!-- jQuery 3 -->
  <script src="lib/jquery/jquery.min.js"></script>

  <!-- Bootstrap 3.3.7 -->
  <link rel="stylesheet" href="lib/bootstrap/bootstrap.min.css">
  <script src="lib/bootstrap/bootstrap.min.js"></script>

  <!-- Datatable -->
  <link rel="stylesheet" href="lib/datatables.net-bs/css/dataTables.bootstrap.min.css">
  <link rel="stylesheet" href="lib/datatables.net/css/select.dataTables.min.css">
  <script src="lib/datatables.net/js/jquery.dataTables.min.js"></script>
  <script src="lib/datatables.net-bs/js/dataTables.bootstrap.min.js"></script>
  <script src="lib/datatables.net/js/dataTables.select.min.js"></script>

  <script>window.NAX_APP_VERSION = "<?php echo trim(file_exists('/app/.VERSION') ? file_get_contents('/app/.VERSION') : 'dev'); ?>";</script>
  <script src="js/cache.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/common.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/app-init.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/sse_manager.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/api.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/modal.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/tests.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/db_methods.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/settings_utils.js?v=<?php include 'php/templates/version.php'; ?>"></script>
  <script src="js/device.js?v=<?php include 'php/templates/version.php'; ?>"></script>

  <!-- iCheck -->

  <link rel="stylesheet" href="lib/iCheck/all.css">
  <script src="lib/iCheck/icheck.min.js"></script>


  <!-- Font Awesome -->
  <link rel="stylesheet" href="lib/font-awesome/all.min.css">

  <!-- Ionicons -->
  <link rel="stylesheet" href="lib/Ionicons/ionicons.min.css">

  <!-- Theme style -->
  <link rel="stylesheet" href="lib/AdminLTE/dist/css/AdminLTE.min.css">

  <!-- AdminLTE Skins. We have chosen the skin-blue for this starter
        page. However, you can choose any other skin. Make sure you
        apply the skin class to the body tag so the changes take effect. -->
  <link rel="stylesheet" href="lib/AdminLTE/dist/css/skins/<?php echo $pia_skin_selected;?>.min.css">

  <!-- NetAlertX CSS -->
  <link rel="stylesheet" href="css/app.css">


  <!-- Google Font -->
  <!-- <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Source+Sans+Pro:300,400,600,700,300italic,400italic,600italic"> -->
  <link rel="stylesheet" href="css/offline-font.css">
  <link id="favicon" rel="icon" type="image/x-icon" href="img/NetAlertX_logo.png">

  <!-- For better UX on Mobile Devices using the Shortcut on the Homescreen -->
  <link rel="manifest" href="img/manifest.json" crossorigin="use-credentials">
  <!-- Dark-Mode Patch -->

  <?php
  switch ($UI_THEME) {
    case "Dark":
      echo '<link rel="stylesheet" href="css/dark-patch.css">';
      break;
    case "System":
      echo '<link rel="stylesheet" href="css/system-dark-patch.css">';
      break;
  }
  ?>



<!-- Servertime to the right of the hostname -->
<script>

  // ===================================================================
  // DEPRECATED: updateState() - Replaced by SSE-based state manager
  // Kept for backward compatibility, will be removed in future version
  // ===================================================================
  function updateState() {
    // Delegate to SSE manager if available
    if (typeof netAlertXStateManager !== 'undefined' && netAlertXStateManager.initialized) {
      return; // SSE handles this now
    }

    // Fallback for backward compatibility
    $.get('php/server/query_json.php', { file: 'app_state.json', nocache: Date.now() }, function(appState) {
      document.getElementById('state').innerHTML = appState["currentState"].replaceAll('"', '');
    })
  }

  // ===================================================================
  // updates the date and time in the header
  function update_servertime() {
    // Get the current date and time in the specified time zone
    let timeZone = "<?php echo $timeZone ?>";
    let now = new Date();

    if (document.getElementById) {
      document.getElementById("NAX_Servertime_plc").innerHTML = '(' + localizeTimestamp(now) + ')';
      document.getElementById("NAX_TZ").innerHTML = timeZone;
    }

    setTimeout(update_servertime, 1000); // Call recursively every second
  }

</script>

</head>

<!-- ----------------------------------------------------------------------- -->
<!-- Layout Boxed Yellow -->

<!-- spinner -->


<body class="hold-transition fixed <?php echo $pia_skin_selected;?>  theme-<?php echo $UI_THEME;?>  sidebar-mini" onLoad="update_servertime();" >

<div id="loadingSpinner">
  <div class="nax_semitransparent-panel"></div>
  <div class="panel panel-default nax_spinner">
    <table>
      <td id="loadingSpinnerText" width="130px" ></td>
      <td><i class="fa-solid fa-spinner fa-spin-pulse"></i></td>
    </table>
  </div>
</div>

<!-- Site wrapper -->
<div class="wrapper">


  <!-- Main Header -->
  <header class="main-header">

<!-- ----------------------------------------------------------------------- -->
    <!-- Logo -->
    <a href="devices.php" class="logo">
      <!-- mini logo for sidebar mini 50x50 pixels -->
      <span class="logo-mini">
        <img src="img/NetAlertX_logo.png" class="top-left-logo" alt="NetAlertX Logo"/>
      </span>
      <!-- logo for regular state and mobile devices -->
      <span class="logo-lg">Net<b>Alert</b><sup>x</sup>

      </span>

    </a>

<!-- ----------------------------------------------------------------------- -->
    <!-- Header Navbar -->
    <nav class="navbar navbar-static-top" role="navigation">
      <!-- Sidebar toggle button-->
      <a href="#" class="sidebar-toggle" data-toggle="push-menu" role="button">
        <i class="fa-solid fa-bars"></i>
      </a>

      <!-- ticker message  Placeholder for ticker announcement messages -->
      <div id="ticker_announcement_plc"></div>

      <!-- Navbar Right Menu -->
      <div class="navbar-custom-menu">
        <ul class="nav navbar-nav">
          <!-- Back Button -->
          <li>
            <a id="back-button" href="javascript:history.go(-1);" role="button" span class='fa fa-arrow-left'></a>
          </li>
          <!-- Next Button -->
          <li>
            <a id="next-button" href="javascript:history.go(1);" role="button" span class='fa fa-arrow-right'></a>
          </li>
          <!-- Clear cache & Reload -->
          <li>
            <a id="reload-button" href='#' role="button" span  onclick='clearCache()' class='fa-solid fa-rotate'></a>
          </li>
          <!-- Full Screen -->
          <li>
            <a id="fullscreen-button" href='#' role="button" span class='fa fa-arrows-alt' onclick='toggleFullscreen()'></a>
          </li>
          <!-- Notifications -->
          <li>
            <a id="notifications-button" href='userNotifications.php' role="button" span class='fa-solid fa-bell'></a>
            <span  id="unread-notifications-bell-count" title="" class="badge bg-red unread-notifications-bell" >0</span>
          </li>
          <!-- Server Status -->
          <li>
            <a onclick="setCache('activeMaintenanceTab', 'tab_Logging_id')" href="maintenance.php#tab_Logging">
              <div class="header-status">
                <code id="state"></code>
              </div>
              <div class="header-status-locked-db">
                <i class="fa-solid fa-database fa-fade"></i>
              </div>
            </a>
          </li>
          <!-- Server Name -->
          <li>
            <div class="header-server-time small">
              <div>
                <?php echo gethostname();?>
              </div>
              <div>
                <span id="NAX_Servertime_plc"></span>
                <span id="NAX_TZ" class="hidden"></span>
              </div>
            </div>
          </li>

          <!-- Header right info -->
          <li class="dropdown user user-menu">
            <!-- Menu Toggle Button -->
            <a href="#" class="dropdown-toggle" style=" height: 50px;" data-toggle="dropdown">

              <span class="hidden-xs" ><!-- The user image in the navbar-->
              <img src="img/NetAlertX_logo.png" class="user-image" style="border-radius: initial" alt="NetAlertX Logo">
              <!-- hidden-xs hides the username on small devices so only the image appears. --></span>
            </a>
            <ul class="dropdown-menu">
              <!-- The user image in the menu -->
              <li class="user-header" style=" height: 100px;">
                <img src="img/NetAlertX_logo.png" class="img-circle NetAlertX-logo" alt="NetAlertX Logo">
                <p style="float: right; width: 200px">
                <?= lang('About_Title');?>
                  <small><?= lang('About_Design');?> Docker</small>
                </p>
              </li>

              <!-- Menu Body -->

              <li class="user-footer">
                <div class="pull-right">
                  <a href="index.php?action=logout" class="btn btn-danger"><?= lang('About_Exit');?></a>
                </div>
              </li>
            </ul>
          </li>
        </ul>
      </div>
    </nav>


  </header>



<!-- ----------------------------------------------------------------------- -->
  <!-- Left side column. contains the logo and sidebar -->
  <aside class="main-sidebar">

    <!-- sidebar: style can be found in sidebar.less -->
    <section class="sidebar">

      <!-- search form (Optional) -->
        <!-- DELETED -->

      <!-- Navigation Mneu -->
      <ul class="sidebar-menu" data-widget="tree">

        <li class=" treeview  <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('devices.php', 'deviceDetails.php') ) ){ echo 'active menu-open'; } ?>">
          <a href="#"  onclick="openUrl(['./devices.php', './deviceDetails.php'])">

          <i class="fa fa-fw fa-laptop"></i> <span><?= lang('Navigation_Devices');?></span>
            <span class="pull-right-container">
              <i class="fa fa-angle-left pull-right"></i>
            </span>
          </a>
          <ul class="treeview-menu" style="display: <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('devices.php', 'deviceDetails.php') ) ){ echo 'block'; } else {echo 'none';} ?>;">
            <li>
              <a href="devices.php#my_devices" onclick="forceLoadUrl('devices.php#my_devices')" >  <?= lang("Device_Shortcut_AllDevices");?> </a>
            </li>
            <li>
              <a href="devices.php#connected" onclick="forceLoadUrl('devices.php#connected')" >  <?= lang("Device_Shortcut_Connected");?> </a>
            </li>
            <li>
              <a href="devices.php#favorites" onclick="forceLoadUrl('devices.php#favorites')" > <?= lang("Device_Shortcut_Favorites");?> </a>
            </li>
            <li>
              <a href="devices.php#new" onclick="forceLoadUrl('devices.php#new')" >  <?= lang("Device_Shortcut_NewDevices");?> </a>
            </li>
            <li>
              <a href="devices.php#down" onclick="forceLoadUrl('devices.php#down')" >  <?= lang("Device_Shortcut_DownOnly");?> </a>
            </li>
            <li>
              <a href="devices.php#offline" onclick="forceLoadUrl('devices.php#offline')" > <?= lang("Gen_Offline");?> </a>
            </li>
            <li>
              <a href="devices.php#archived" onclick="forceLoadUrl('devices.php#archived')" >  <?= lang("Device_Shortcut_Archived");?> </a>
            </li>
            <li>
              <a href="devices.php#unstable_devices" onclick="forceLoadUrl('devices.php#unstable_devices')" >  <?= lang("Device_Shortcut_Unstable");?> </a>
            </li>
            <li>
              <a href="devices.php#all_devices" onclick="forceLoadUrl('devices.php#all_devices')" >  <?= lang("Gen_All_Devices");?> </a>
            </li>
            <li>
              <a href="devices.php#network_devices" onclick="forceLoadUrl('devices.php#network_devices')" >  <?= lang("Network_Devices");?> </a>
            </li>
          </ul>

        </li>

        <!-- Monitoring menu item -->

        <li class=" treeview <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('presence.php', 'report.php', 'events.php', 'userNotifications.php' ) ) ){ echo 'active menu-open'; } ?>">
          <a href="#">
          <i class="fa fa-fw fa-chart-bar"></i> <span><?= lang('Navigation_Monitoring');?></span>
            <span class="pull-right-container">
              <i class="fa fa-angle-left pull-right"></i>
            </span>
          </a>
          <ul class="treeview-menu " style="display: <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('presence.php', 'report.php', 'events.php', 'userNotifications.php' ) ) ){ echo 'block'; } else {echo 'none';} ?>;">
            <li>
              <a href="presence.php">  <?= lang("Navigation_Presence");?> </a>
            </li>
            <li>
              <a href="events.php">  <?= lang("Navigation_Events");?> </a>
            </li>
            <li>
              <a href="report.php"> <?= lang("Navigation_Report");?> </a>
            </li>
            <li>
              <a href="userNotifications.php"> <?= lang("Navigation_Notifications");?> </a>
            </li>

          </ul>
        </li>

	      <!-- Network menu item -->
        <li class=" <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('network.php') ) ){ echo 'active'; } ?>">
          <a href="network.php"><i class="fa fa-fw fa-sitemap fa-rotate-270"></i> <span><?= lang('Navigation_Network');?></span></a>
        </li>

        <!-- Maintenance menu item -->
        <li class=" treeview  <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('maintenance.php') ) ){ echo 'active menu-open'; } ?>">
          <a href="#" onclick="openUrl(['./maintenance.php'])">
          <!-- NEW version available -->
          <div class="info-icon-nav myhidden" id="version" title="<?= lang('new_version_available');?>" data-build-time="<?php echo file_get_contents( "buildtimestamp.txt");?>">
            <i class="fa-solid fa-rocket fa-beat"></i>
          </div>
          <i class="fa fa-fw fa-wrench"></i> <span><?= lang('Navigation_Maintenance');?></span>
            <span class="pull-right-container">
              <i class="fa fa-angle-left pull-right"></i>
            </span>
          </a>
          <ul class="treeview-menu" style="display: <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('maintenance.php') ) ){ echo 'block'; } else {echo 'none';} ?>;">
            <li>
              <a href="maintenance.php#tab_DBTools" onclick="initializeTabs()">  <?= lang("Maintenance_Tools_Tab_Tools");?> </a>
            </li>
            <li>
              <a href="maintenance.php#tab_BackupRestore" onclick="initializeTabs()"> <?= lang("Maintenance_Tools_Tab_BackupRestore");?> </a>
            </li>
            <li>
              <a href="maintenance.php#tab_Logging" onclick="initializeTabs()">  <?= lang("Maintenance_Tools_Tab_Logging");?> </a>
            </li>
            <li>
              <a href="maintenance.php#tab_multiEdit" onclick="initializeTabs()">  <?= lang("Device_MultiEdit");?> </a>
            </li>
          </ul>
        </li>

        <!-- Settings menu item -->
        <li class=" treeview  <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('settings.php') ) ){ echo 'active menu-open'; } ?>">
          <a href="#" onclick="openUrl(['./settings.php'])">
          <i class="fa fa-fw fa-cog"></i> <span><?= lang('Navigation_Settings');?></span>
            <span class="pull-right-container">
              <i class="fa fa-angle-left pull-right"></i>
            </span>
          </a>
          <ul class="treeview-menu" style="display: <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('settings.php') ) ){ echo 'block'; } else {echo 'none';} ?>;">
            <li>
              <a href="settings.php#settingsOverview">  <?= lang("settings_enabled");?> </a>
            </li>
            <li>
              <a href="settings.php#core_content_header">  <?= lang("settings_core_label");?> </a>
            </li>
            <li>
              <a href="settings.php#system_content_header"> <?= lang("settings_system_label");?> </a>
            </li>
            <li>
              <a href="settings.php#device_scanners_content_header">  <?= lang("settings_device_scanners_label");?> </a>
            </li>
            <li>
              <a href="settings.php#other_scanners_content_header">  <?= lang("settings_other_scanners_label");?> </a>
            </li>
            <li>
              <a href="settings.php#publishers_content_header"> <?= lang("settings_publishers_label");?> </a>
            </li>

          </ul>
        </li>

        <!-- Integrations menu item -->
        <li class=" treeview <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('plugins.php', 'appEvents.php' ) ) ){ echo 'active menu-open'; } ?>">
          <a href="#">
          <i class="fa fa-fw fa-plug"></i> <span><?= lang('Navigation_Integrations');?></span>
            <span class="pull-right-container">
              <i class="fa fa-angle-left pull-right"></i>
            </span>
          </a>
          <ul class="treeview-menu " style="display: <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('plugins.php', 'appEvents.php' ) ) ){ echo 'block'; } else {echo 'none';} ?>;">
            <li>
              <a href="appEvents.php"><?= lang('Navigation_AppEvents');?></a>
            </li>
            <li>
              <a href="plugins.php"><?= lang("Navigation_Plugins");?> </a>
            </li>
          </ul>
        </li>

         <!-- workflows menu item -->
         <li class=" <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('workflows.php') ) ){ echo 'active'; } ?>">
          <a href="workflows.php"><i class="fa fa-fw  fa-shuffle"></i> <span><?= lang('Navigation_Workflows');?></span></a>
        </li>

        <!-- system info menu item -->
        <li class=" treeview <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('systeminfo.php') ) ){ echo 'active menu-open'; } ?>">
          <a href="#">
          <i class="fa fa-fw fa-info-circle"></i> <span><?= lang('Navigation_SystemInfo');?></span>
            <span class="pull-right-container">
              <i class="fa fa-angle-left pull-right"></i>
            </span>
          </a>
          <ul class="treeview-menu " style="display: <?php if (in_array (basename($_SERVER['SCRIPT_NAME']), array('systeminfo.php') ) ){ echo 'block'; } else {echo 'none';} ?>;">
            <li>
              <a href="systeminfo.php#panServer" onclick="setCache('activeSysinfoTab','tabServer');initializeTabs()"><?= lang('Systeminfo_System');?></a>
            </li>
            <li>
              <a href="systeminfo.php#panNetwork"  onclick="setCache('activeSysinfoTab','tabNetwork');initializeTabs()"><?= lang('Systeminfo_Network');?></a>
            </li>
            <li>
              <a href="systeminfo.php#panStorage" onclick="setCache('activeSysinfoTab','tabStorage');initializeTabs()"><?= lang('Systeminfo_Storage');?></a>
            </li>
             <li>
              <a href="systeminfo.php#panInitCheck" onclick="setCache('activeSysinfoTab','tabInitCheck');initializeTabs()">  <?= lang("Maintenance_InitCheck");?> </a>
            </li>
          </ul>
        </li>

      </ul>

      <!-- /.sidebar-menu -->
    </section>
    <!-- /.sidebar -->
  </aside>


<script defer>

  function toggleFullscreen() {

   if (document.fullscreenElement) {
     document.exitFullscreen();
    }
   else {
     document.documentElement.requestFullscreen();
	}
   }

  //--------------------------------------------------------------

  // Update server time in the header
  update_servertime()

  // Initialize SSE-based state manager (replaces updateState polling)
  if (typeof netAlertXStateManager !== 'undefined') {
    netAlertXStateManager.init();
  }

</script>
