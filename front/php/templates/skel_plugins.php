<div id="plugins-skeleton" class="spinnerTarget">
  <div class="skel-plugins-wrap  col-sm-12">

    <!-- Left nav sidebar -->
    <div class="skel-plugins-nav col-sm-2">
      <?php
        $widths = [72, 60, 80, 55, 68, 75];
        for ($i = 0; $i < 6; $i++):
      ?>
      <div class="skel-plugins-nav-item">
        <span class="skel-line skel-shimmer" style="width:<?= $widths[$i] ?>%"></span>
      </div>
      <?php endfor; ?>
    </div>

    <!-- Right content area -->
    <div class="skel-plugins-body  col-sm-10">
      <!-- Sub-tab bar -->
      <div class="skel-tabs-bar" style="border-radius: 0 4px 0 0; margin-bottom: 0;">
        <span class="skel-tab skel-shimmer"></span>
        <span class="skel-tab skel-shimmer"></span>
        <span class="skel-tab skel-shimmer"></span>
      </div>
      <!-- Data table -->
      <div class="skel-table-box" style="border-top: none; border-radius: 0 0 4px 4px;">
        <div class="skel-table-header-row">
          <?php for ($j = 0; $j < 5; $j++): ?>
          <span class="skel-th skel-shimmer"></span>
          <?php endfor; ?>
        </div>
        <?php for ($i = 0; $i < 25; $i++): ?>
        <div class="skel-tr">
          <?php for ($j = 0; $j < 5; $j++): ?>
          <span class="skel-td skel-shimmer"></span>
          <?php endfor; ?>
        </div>
        <?php endfor; ?>
      </div>
    </div>
  </div>
  <div class="skel-form-footer col-sm-12 padding-5px">
    <span class="skel-form-btn skel-shimmer"></span>
    <span class="skel-form-btn skel-shimmer"></span>
  </div>
</div>
