<!--
#---------------------------------------------------------------------------------#
#  NetAlertX                                                                       #
#  Open Source Network Guard / WIFI & LAN intrusion detector                      #
#                                                                                 #
# footer.php - Front module. Common footer to all the web pages                   #
#---------------------------------------------------------------------------------#
#    Puche      2021        pi.alert.application@gmail.com   GNU GPLv3            #
#    jokob-sk   2022        jokob.sk@gmail.com               GNU GPLv3            #
#    leiweibau  2022        https://github.com/leiweibau     GNU GPLv3            #
#    cvc90      2023        https://github.com/cvc90         GNU GPLv3            #
#---------------------------------------------------------------------------------#
-->

<?php
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once  $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
?>

  <!-- Main Footer -->
  <footer class="main-footer">
    <!-- Default to the left -->

    <!-- NetAlertX footer with url -->
    <a href="https://github.com/jokob-sk/NetAlertX" target="_blank">Net<b>Alert</b><sup>x</sup></a>
    <!-- To the right -->
    <div class="pull-right no-hidden-xs">
      | <a href="https://gurubase.io/g/netalertx" class="pointer" target="_blank" title="Ask AI"><i class="fa fa-comment-dots fa-flip-horizontal"></i></a>
      | <a href="/llms.txt" class="pointer" target="_blank" data-agent-role="mcp-setup" aria-label="Agentic MCP instructions" title="Agent MCP Instructions"><i class="fa fa-robot"></i></a>
      | <a href="https://docs.netalertx.com/" class="pointer" target="_blank" title="Documentation"><i class="fa fa-book"></i></a>
      | <a href="https://github.com/jokob-sk/NetAlertX/issues" class="pointer" target="_blank"><i class="fa fa-bug" title="Report a bug"></i></a>
      | <a href="https://discord.com/invite/NczTUTWyRr" class="pointer" target="_blank"><i class="fa-brands fa-discord" title="Join Discord"></i></a>
      | <?= lang('Maintenance_built_on');?>:  <span data-plc="build-timestamp"></span>
      |  Version:  <span data-plc="version"></span>
      |
    </div>
  </footer>

<!-- ----------------------------------------------------------------------- -->
  <!-- Control Sidebar -->
    <!-- DELETED -->

</div>
<!-- ./wrapper -->

<!-- jQuery UI -->
<script src="lib/jquery-ui/jquery-ui.min.js"></script>

<!-- AdminLTE App -->
<script src="lib/AdminLTE/dist/js/adminlte.min.js"></script>

<!-- Select2 CSS -->
<link rel="stylesheet" href="lib/select2/select2.min.css">

<!-- NetAlertX -->
<script defer src="js/handle_version.js"></script>
<script src="js/device-columns.js?v=<?php include 'php/templates/version.php'; ?>"></script>
<script src="js/ui_components.js?v=<?php include 'php/templates/version.php'; ?>"></script>


<!-- Select2 JavaScript -->
<script src="lib/select2/select2.full.min.js" defer></script>


  <?php
    require 'migrationCheck.php';
  ?>

</body>
</html>
