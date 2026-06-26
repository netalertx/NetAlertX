<div id="presence-skeleton" class="spinnerTarget">

  <!-- 6 stat tiles -->
  <div class="row">
    <?php for ($i = 0; $i < 6; $i++): ?>
    <div class="col-lg-2 col-sm-4 col-xs-6">
      <div class="skel-tile">
        <div class="skel-tile-inner">
          <span class="skel-tile-num   skel-shimmer"></span>
          <span class="skel-tile-label skel-shimmer"></span>
        </div>
        <div class="skel-tile-icon-area">
          <span class="skel-tile-icon-shape skel-shimmer"></span>
        </div>
      </div>
    </div>
    <?php endfor; ?>
  </div>

  <!-- activity chart -->
  <div class="row" style="margin-top:12px">
    <div class="col-md-12">
      <div class="skel-chart-box">
        <div class="skel-box-header">
          <span class="skel-line skel-shimmer" style="width:160px"></span>
        </div>
        <div class="skel-chart-body skel-shimmer" style="height:160px"></div>
      </div>
    </div>
  </div>

  <!-- presence calendar -->
  <div class="row">
    <div class="col-md-12">
      <div class="skel-chart-box">
        <div class="skel-box-header">
          <span class="skel-line skel-shimmer" style="width:100px"></span>
          <span class="skel-line skel-shimmer" style="width:180px; margin-left:auto;"></span>
        </div>
        <div class="skel-chart-body skel-shimmer" style="height:580px"></div>
      </div>
    </div>
  </div>

</div>
