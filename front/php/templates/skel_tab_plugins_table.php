<!-- Plugins Sub-Tab Table Skeleton (shared: Objects / Events / History) === -->
<div class="skel-table-box spinnerTarget">
  <div class="skel-table-header-row">
    <?php for ($j = 0; $j < 5; $j++): ?>
    <span class="skel-th skel-shimmer"></span>
    <?php endfor; ?>
  </div>
  <?php
    $rowWidths = array_fill(0, 20, [15, 14, 18, 12, 20]);
    foreach ($rowWidths as $widths):
  ?>
  <div class="skel-tr">
    <?php foreach ($widths as $w): ?>
    <span class="skel-td skel-shimmer" style="flex:1; max-width:<?= $w ?>%"></span>
    <?php endforeach; ?>
  </div>
  <?php endforeach; ?>
</div>
<div class="skel-form-footer-left" style="padding:8px 0;">
  <span class="skel-form-btn skel-shimmer"></span>
  <span class="skel-form-btn skel-shimmer"></span>
</div>
