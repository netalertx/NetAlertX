<div id="report-skeleton" class="spinnerTarget">
  <div class="skel-table-box">
    <div class="skel-box-header">
      <span class="skel-line skel-shimmer" style="width:160px"></span>
    </div>

    <!-- nav controls + format select -->
    <div style="display:flex; align-items:center; flex-wrap:wrap; gap:12px; padding:12px 15px; border-bottom:1px solid var(--skel-border);">
      <span class="skel-shimmer" style="height:32px; width:34px; border-radius:4px;"></span>
      <span class="skel-shimmer" style="height:14px; width:40px;"></span>
      <span class="skel-shimmer" style="height:32px; width:34px; border-radius:4px;"></span>
      <span class="skel-shimmer" style="height:32px; width:80px; border-radius:4px;"></span>
      <span class="skel-shimmer" style="height:14px; width:160px;"></span>
    </div>

    <!-- report body shimmer lines -->
    <div style="padding:20px 15px; display:flex; flex-direction:column; gap:10px;">
      <?php foreach ([90, 75, 85, 60, 80, 70, 65, 88] as $w): ?>
      <span class="skel-shimmer" style="height:16px; width:<?= $w ?>%;"></span>
      <?php endforeach; ?>
    </div>
  </div>
</div>
