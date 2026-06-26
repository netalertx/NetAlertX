<div id="workflows-skeleton" class="spinnerTarget">
  <?php for ($i = 0; $i < 3; $i++): ?>
  <div class="skel-workflow-card">
    <div class="skel-workflow-header">
      <span class="skel-line skel-shimmer" style="width:<?= [220, 180, 200][$i] ?>px"></span>
      <span class="skel-line skel-shimmer" style="width:55px; margin-left:auto;"></span>
      <span class="skel-line skel-shimmer" style="width:55px; margin-left:auto;"></span>
      <span class="skel-line skel-shimmer" style="width:55px; margin-left:auto;"></span>
    </div>
  </div>
  <?php endfor; ?>
</div>
