<div id="notifications-skeleton" class="spinnerTarget">
  <div class="skel-table-box">
    <div class="skel-box-header">
      <span class="skel-line skel-shimmer" style="width:200px"></span>
    </div>
    <div class="skel-table-header-row">
      <?php for ($i = 0; $i < 4; $i++): ?>
      <span class="skel-th skel-shimmer"></span>
      <?php endfor; ?>
    </div>
    <?php for ($i = 0; $i < 25; $i++): ?>
    <div class="skel-tr">
      <?php for ($j = 0; $j < 4; $j++): ?>
      <span class="skel-td skel-shimmer"></span>
      <?php endfor; ?>
    </div>
    <?php endfor; ?>
  </div>
  <div class="skel-form-footer">
      <span class="skel-form-btn skel-shimmer"></span>
      <span class="skel-form-btn skel-shimmer"></span>
  </div>
</div>
