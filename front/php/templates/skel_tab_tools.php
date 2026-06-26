<div id="skel-tab-tools" class="spinnerTarget">

  <!-- events table -->
  <div class="row" style="margin-top:12px">
    <div class="col-xs-12">
      <div class="skel-table-box">
        <div class="skel-box-header">
          <span class="skel-line skel-shimmer" style="width:120px"></span>
          <span class="skel-line skel-shimmer" style="width:90px; margin-left:auto;"></span>
        </div>
        <div class="skel-table-header-row">
          <?php for ($i = 0; $i < 6; $i++): ?>
          <span class="skel-th skel-shimmer"></span>
          <?php endfor; ?>
        </div>
        <?php for ($i = 0; $i < 20; $i++): ?>
        <div class="skel-tr">
          <?php for ($j = 0; $j < 6; $j++): ?>
          <span class="skel-td skel-shimmer"></span>
          <?php endfor; ?>
        </div>
        <?php endfor; ?>
      </div>
    </div>
  </div>

</div>
