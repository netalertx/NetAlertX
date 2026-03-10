<?php
#---------------------------------------------------------------------------------#
#  NetAlertX                                                                       #
#  Open Source Network Guard / WIFI & LAN intrusion detector                      #
#                                                                                 #
#  systeminfo.php - Front module. Server side. System Information                 #
#---------------------------------------------------------------------------------#
#    Puche      2021        pi.alert.application@gmail.com   GNU GPLv3            #
#    jokob-sk   2022        jokob.sk@gmail.com               GNU GPLv3            #
#    leiweibau  2022        https://github.com/leiweibau     GNU GPLv3            #
#    cvc90      2023        https://github.com/cvc90         GNU GPLv3            #
#---------------------------------------------------------------------------------#

  require 'php/templates/header.php';
?>
<?php require 'php/templates/modals.php'; ?>
<!-- ----------------------------------------------------------------------- -->


<script>

  // show spinning icon
  showSpinner()

</script>

<!-- Page ------------------------------------------------------------------ -->
<div class="content-wrapper">

    <!-- Main content ---------------------------------------------------------- -->
    <section class="content">
    <div class="row">
        <div class="col-lg-12 col-sm-12 col-xs-12">
        <!-- <div class="box-transparent"> -->
          <div id="navSysInfo" class="nav-tabs-custom">
            <ul class="nav nav-tabs" style="font-size:16px;">
              <li>
                <a id="tabServer"  href="#panServer"  data-toggle="tab">
                  <i class="fa fa-info-circle"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('Systeminfo_System');?>
                    </span>
                </a>
              </li>
              <li>
                <a id="tabNetwork"    href="#panNetwork"    data-toggle="tab">
                  <i class="fa fa-sitemap fa-rotate-270"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('Systeminfo_Network');?>
                    </span>
                </a>
              </li>
              <li>
                <a id="tabStorage" href="#panStorage" data-toggle="tab">
                  <i class="fa fa-hdd"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('Systeminfo_Storage');?>
                    </span>
                </a>
              </li>
              <li>
                <a id="tabInitCheck" href="#panInitCheck" data-toggle="tab">
                  <i class="fa fa-check"></i>
                    <span class="dev-detail-tab-name">
                      <?= lang('Maintenance_InitCheck');?>
                    </span>
                </a>
              </li>
            </ul>

            <div class="tab-content spinnerTarget" style="min-height: 430px;">
              <div class="tab-pane fade" data-php-file="systeminfoServer.php" id="panServer">
               <!-- PLACEHOLDER -->
              </div>
              <div class="tab-pane fade" data-php-file="systeminfoNetwork.php" id="panNetwork">
                 <!-- PLACEHOLDER -->
              </div>
              <div class="tab-pane fade table-responsive" data-php-file="systeminfoStorage.php" id="panStorage">
               <!-- PLACEHOLDER -->
              </div>
              <div class="tab-pane fade table-responsive" data-php-file="systeminfoInitCheck.php" id="panInitCheck">
               <!-- PLACEHOLDER -->
              </div>
            </div>
            <!-- /.tab-content -->
          </div>
          <!-- /.nav-tabs-custom -->
          <!-- </div> -->
        </div>
        <!-- /.col -->
      </div>

    </section>

    <!-- /.content -->

  </div>
  <!-- /.content-wrapper -->

  <?php
      require 'php/templates/footer.php';
    ?>

<!-- ----------------------------------------------------------------------- -->

<script>

function loadTabContent(target) {
  const $tab = $(target);
  const phpFile = $tab.data('php-file');

  if (phpFile && !$tab.data('loaded')) {
    showSpinner();
    $tab.load(phpFile, function () {
      $tab.data('loaded', true);
    });
  }
}

function initializeTabs() {
  initializeTabsShared({
    cacheKey:     'activeSysinfoTab',
    defaultTab:   'tabServer',
    onTabChange:  loadTabContent
  });
}

window.onload = function async() {
  initializeTabs();
}

</script>
