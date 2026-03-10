<?php
  require 'php/templates/header.php';
  require 'php/templates/modals.php';
?>

<!-- Page ------------------------------------------------------------------ -->
<div class="content-wrapper">
  <span class="helpIcon">
    <a target="_blank" href="https://docs.netalertx.com/NETWORK_TREE">
      <i class="fa fa-circle-question"></i>
    </a>
  </span>

  <div id="toggleFilters" class="">
      <div class="checkbox icheck col-xs-12">
        <label>
          <input type="checkbox" name="showOffline" checked>
            <div style="margin-left: 10px; display: inline-block; vertical-align: top;">
              <?= lang('Network_ShowOffline');?>
              <span id="showOfflineNumber">
                <!-- placeholder -->
              </span>
            </div>
        </label>
      </div>
      <div class="checkbox icheck col-xs-12">
        <label>
          <input type="checkbox" name="showArchived">
            <div style="margin-left: 10px; display: inline-block; vertical-align: top;">
              <?= lang('Network_ShowArchived');?>
              <span id="showArchivedNumber">
                <!-- placeholder -->
              </span>
            </div>
        </label>
      </div>
  </div>

  <div id="networkTree" class="drag">
    <!-- Tree topology Placeholder -->
  </div>

  <!-- Main content ---------------------------------------------------------- -->
  <section class="content networkTable">
    <!-- /.content -->
    <div class="nav-tabs-custom">
      <ul class="nav nav-tabs">
        <!-- Placeholder -->
      </ul>
    </div>
    <div class="tab-content">
      <!-- Placeholder -->
    </div>
  </section>
  <section id="unassigned-devices-wrapper">
      <!-- Placeholder -->
    </section>
    <!-- /.content -->
</div>
<!-- /.content-wrapper -->
<!-- ----------------------------------------------------------------------- -->

<?php
  require 'php/templates/footer.php';
?>

<!-- <script src="lib/treeviz/bundle.js"></script> -->
<script src="lib/treeviz/treeviz.iife.js"></script>

<!-- Network Topology JavaScript Modules -->
<script defer src="js/network-api.js"></script>
<script defer src="js/network-tree.js"></script>
<script defer src="js/network-tabs.js"></script>
<script defer src="js/network-events.js"></script>
<script defer src="js/network-init.js"></script>



