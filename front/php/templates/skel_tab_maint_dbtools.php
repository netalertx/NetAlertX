<div class="skel-tab-pane spinnerTarget" id="skel-tab-maint-dbtools">
  <?php
    $widths = [55, 70, 45, 62, 58, 50, 55, 48];
    for ($i = 0; $i < 8; $i++):
  ?>
  <div class="skel-tr">
    <span class="skel-shimmer" style="height:32px; width:185px; flex-shrink:0; border-radius:4px;"></span>
    <span class="skel-line skel-shimmer" style="width:<?= $widths[$i] ?>%"></span>
  </div>
  <?php endfor; ?>
</div>
