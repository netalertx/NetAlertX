<!--
#---------------------------------------------------------------------------------#
#  NetAlertX                                                                      #
#  Open Source Network Guard / WIFI & LAN intrusion detector                      #
#                                                                                 #
#  devices.php - Front module. Devices list page                                  #
#---------------------------------------------------------------------------------#
#    Puche      2021        pi.alert.application@gmail.com   GNU GPLv3            #
#    jokob-sk   2022        jokob.sk@gmail.com               GNU GPLv3            #
#    leiweibau  2022        https://github.com/leiweibau     GNU GPLv3            #
#    cvc90      2023        https://github.com/cvc90         GNU GPLv3            #
#---------------------------------------------------------------------------------#
-->

<?php

  require 'php/templates/header.php';

  // check permissions
  // Use environment-aware paths with fallback to legacy locations
  $dbFolderPath = rtrim(getenv('NETALERTX_DB') ?: '/data/db', '/');
  $configFolderPath = rtrim(getenv('NETALERTX_CONFIG') ?: '/data/config', '/');

  $dbPath = $dbFolderPath . '/app.db';
  $confPath = $configFolderPath . '/app.conf';

  // Fallback to legacy paths if new locations don't exist
  if (!file_exists($dbPath) && file_exists('../db/app.db')) {
      $dbPath = '../db/app.db';
  }
  if (!file_exists($confPath) && file_exists('../config/app.conf')) {
      $confPath = '../config/app.conf';
  }
?>

<!-- ----------------------------------------------------------------------- -->


<!-- Page ------------------------------------------------------------------ -->
  <div class="content-wrapper" id="devicesPage">

    <?php require 'php/templates/skel_devices.php'; ?>

<!-- Main content ---------------------------------------------------------- -->
    <section class="content">

      <!-- Tile toggle cards ------------------------------------------------------- -->
      <div class="row " id="TileCards">
        <!-- Placeholder ------------------------------------------------------- -->
      </div>

<!-- Device presence / Activity Chart ------------------------------------------------------- -->

      <div class="row" id="DevicePresence">
          <div class="col-md-12">
            <div class="box" id="clients">
              <div class="box-header ">
                <h3 class="box-title"><?= lang('Device_Shortcut_OnlineChart');?> </h3>
                <div class="box-tools pull-right">
                  <button type="button" class="btn btn-box-tool" data-widget="collapse">
                    <i class="fa fa-minus"></i>
                  </button>
                </div>
              </div>
              <div class="box-body">
                <div class="chart">
                  <script src="lib/chart.js/Chart.js"></script>
                  <!-- presence chart -->
                  <?php
                      require 'php/components/graph_online_history.php';
                  ?>
                </div>
              </div>
              <!-- /.box-body -->
            </div>
          </div>
      </div>

      <!-- Device Filters ------------------------------------------------------- -->
      <div class="box box-aqua hidden" id="columnFiltersWrap">
        <div class="box-header ">
          <h3 class="box-title"><?= lang('Devices_Filters');?> </h3>
          <div class="box-tools pull-right">
            <button type="button" class="btn btn-box-tool" data-widget="collapse">
              <i class="fa fa-minus"></i>
            </button>
          </div>
        </div>
        <!-- Placeholder ------------------------------------------------------- -->
        <div class="box-body" id="columnFilters"></div>
      </div>

<!-- datatable ------------------------------------------------------------- -->
      <div class="row">
        <div class="col-xs-12">
          <div id="tableDevicesBox" class="box">

            <!-- box-header -->
            <div class="box-header">
              <div class=" col-sm-8 ">
                <h3 id="tableDevicesTitle" class="box-title text-gray "></h3>
                <span class="helpIconSmallTopRight">
                  <a target="_blank" href="https://docs.netalertx.com/DEVICE_FILTERS">
                    <i class="fa fa-circle-question"></i>
                  </a>
                </span>
              <!-- Next scan ETA — populated by sse_manager.js via nax:scanEtaUpdate -->
              <small id="nextScanEta" class="text-muted" style="display:none;margin-left:8px;font-weight:normal;font-size:0.75em;"></small>
              </div>
              <div  class="dummyDevice col-sm-4 ">
                <span id="multiEditPlc">
                  <!-- multi edit button placeholder -->
                </span>
                <span>
                  <a href="deviceDetails.php?mac=new"><i title="<?= lang('Gen_create_new_device');?>" class="fa fa-square-plus"></i> <?= lang('Gen_create_new_device');?></a>
                </span>
              </div>
            </div>

            <!-- table -->
            <div class="box-body table-responsive">
              <table id="tableDevices" class="table table-bordered table-hover table-striped">
                <thead>
                <tr>

                </tr>
                </thead>
              </table>
            </div>
            <!-- /.box-body -->

          </div>
          <!-- /.box -->
        </div>
        <!-- /.col -->
      </div>
      <!-- /.row -->

<!-- ----------------------------------------------------------------------- -->
    </section>
    <!-- /.content -->

  </div>
  <!-- /.content-wrapper -->


<!-- ----------------------------------------------------------------------- -->
<?php
  require 'php/templates/footer.php';
?>


<!-- page script ----------------------------------------------------------- -->
<script src="js/devices-totals.js?v=<?php include 'php/templates/version.php'; ?>"></script>
<script src="js/devices-filters.js?v=<?php include 'php/templates/version.php'; ?>"></script>
<script src="js/devices-table.js?v=<?php include 'php/templates/version.php'; ?>"></script>
<script src="js/devices-custom-props.js?v=<?php include 'php/templates/version.php'; ?>"></script>
<script src="js/devices-init.js?v=<?php include 'php/templates/version.php'; ?>"></script>
