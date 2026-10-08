<?php
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once $_SERVER["DOCUMENT_ROOT"] . "/php/templates/security.php";
?>

<?php require $_SERVER['DOCUMENT_ROOT'] . '/php/templates/skel_device_details_tab_session_info.php'; ?>

<div class="row" id="deviceDetailsSessionInfo">
  <div class="box-body form-horizontal">

    <div class="field-group session-group col-lg-4 col-sm-6 col-xs-12">
      <h5><i class="fa fa-calendar"></i> <?= lang('DevDetail_SessionInfo_Title');?>
        <span class="helpIconSmallTopRight">
          <a target="_blank" href="https://docs.netalertx.com/SESSION_INFO">
            <i class="fa fa-circle-question"></i>
          </a>
        </span>
      </h5>
      <hr>

      <div class="form-group col-xs-12">
        <label class="col-sm-4 col-xs-12 control-label" id="sessionInfo_label_devPrimaryIPv4">
          <span id="sessionInfo_label_devPrimaryIPv4_text"></span>
          <i my-set-key="NEWDEV_devPrimaryIPv4"
            title="<?= lang('Settings_Show_Description');?>"
            class="fa fa-circle-info pointer helpIconSmallTopRight"
            onclick="showDescriptionPopup(this)">
          </i>
        </label>
        <div class="col-sm-8 col-xs-12 form-control-static" id="sessionInfo_devPrimaryIPv4"></div>
      </div>
      <div class="form-group col-xs-12">
        <label class="col-sm-4 col-xs-12 control-label" id="sessionInfo_label_devPrimaryIPv6">
          <span id="sessionInfo_label_devPrimaryIPv6_text"></span>
          <i my-set-key="NEWDEV_devPrimaryIPv6"
            title="<?= lang('Settings_Show_Description');?>"
            class="fa fa-circle-info pointer helpIconSmallTopRight"
            onclick="showDescriptionPopup(this)">
          </i>
        </label>
        <div class="col-sm-8 col-xs-12 form-control-static" id="sessionInfo_devPrimaryIPv6"></div>
      </div>
      <div class="form-group col-xs-12">
        <label class="col-sm-4 col-xs-12 control-label"><?= lang('Device_TableHead_Status');?>
          <i my-set-key="Device_TableHead_Status"
            title="<?= lang('Settings_Show_Description');?>"
            class="fa fa-circle-info pointer helpIconSmallTopRight"
            onclick="showDescriptionPopup(this)">
          </i>
        </label>
        <div class="col-sm-8 col-xs-12 form-control-static" id="sessionInfo_devStatus"></div>
      </div>
      <div class="form-group col-xs-12">
        <label class="col-sm-4 col-xs-12 control-label"><?= lang('Device_TableHead_LastSession');?>
          <i my-set-key="NEWDEV_devLastConnection"
            title="<?= lang('Settings_Show_Description');?>"
            class="fa fa-circle-info pointer helpIconSmallTopRight"
            onclick="showDescriptionPopup(this)">
          </i>
        </label>
        <div class="col-sm-8 col-xs-12 form-control-static" id="sessionInfo_devLastConnection"></div>
      </div>
      <div class="form-group col-xs-12">
        <label class="col-sm-4 col-xs-12 control-label"><?= lang('Device_TableHead_FirstSession');?>
          <i my-set-key="NEWDEV_devFirstConnection"
            title="<?= lang('Settings_Show_Description');?>"
            class="fa fa-circle-info pointer helpIconSmallTopRight"
            onclick="showDescriptionPopup(this)">
          </i>
        </label>
        <div class="col-sm-8 col-xs-12 form-control-static" id="sessionInfo_devFirstConnection"></div>
      </div>
      <div class="form-group col-xs-12">
        <label class="col-sm-4 col-xs-12 control-label"><?= lang('Device_TableHead_FQDN');?>
          <i my-set-key="NEWDEV_devFQDN"
            title="<?= lang('Settings_Show_Description');?>"
            class="fa fa-circle-info pointer helpIconSmallTopRight"
            onclick="showDescriptionPopup(this)">
          </i>
        </label>
        <div class="col-sm-8 col-xs-12 form-control-static" id="sessionInfo_devFQDN"></div>
      </div>
    </div>

    <div class="field-group col-lg-4 col-sm-6 col-xs-12">
      <h5><i class="fa fa-network-wired"></i> <?= lang('DevDetail_SessionInfo_KnownIPs');?></h5>
      <hr>
      <div id="sessionInfo_knownIps"></div>
    </div>

    <div class="field-group col-lg-4 col-sm-6 col-xs-12">
      <h5><i class="fa fa-clock-rotate-left"></i> <?= lang('DevDetail_SessionInfo_IPHistory');?></h5>
      <hr>
      <div id="sessionInfo_ipHistory"></div>
    </div>

  </div>
</div>

<script>

// -----------------------------------------------------------------------------
function hideSessionInfoTabSkeleton() {
  $('#skel-tab-session-info').fadeOut(0, function() { $(this).hide(); });
}
function showSessionInfoTabSkeleton() {
  var $skel = $('#skel-tab-session-info');
  $skel.stop(true, true).fadeIn(10);
}

// -----------------------------------------------------------------------------
// Labels for devPrimaryIPv4/devPrimaryIPv6 reuse NEWDEV's own setName
// (newdevSettingsByKey, populated by deviceDetailsEdit.php's getDeviceData())
// instead of a second, hand-maintained lang key with the same text. These are
// locale text, not per-device values - fill them in independently of the
// per-mac render below, once the settings fetch has actually resolved, and
// skip re-writing once already set.
function renderSessionInfoLabels() {
  if ($('#sessionInfo_label_devPrimaryIPv4_text').text()) {
    return; // already set - settings are locale text, not per-mac
  }
  const ipv4Setting = newdevSettingsByKey['NEWDEV_devPrimaryIPv4'];
  const ipv6Setting = newdevSettingsByKey['NEWDEV_devPrimaryIPv6'];
  if (!ipv4Setting || !ipv6Setting) {
    return; // settings fetch hasn't resolved yet - try again next tick
  }
  // Write into the inner _text span, not the <label> itself - the label also
  // holds the static help-icon <i>, which a .text() on the label would wipe out.
  $('#sessionInfo_label_devPrimaryIPv4_text').text(ipv4Setting.setName);
  $('#sessionInfo_label_devPrimaryIPv6_text').text(ipv6Setting.setName);
}

// -----------------------------------------------------------------------------
// Plain read-only rows sourced directly from the already-fetched global
// deviceData (deviceDetailsEdit.php's getDeviceData()) - no settings lookup,
// no form inputs, no save path. devStatus is rendered via the same
// badgeFromDevice() the rest of the UI already uses for device status,
// rather than printing the raw devStatus string.
function renderSessionInfoFields() {
  $('#sessionInfo_devPrimaryIPv4').text(deviceData.devPrimaryIPv4 || '');
  $('#sessionInfo_devPrimaryIPv6').text(deviceData.devPrimaryIPv6 || '');
  $('#sessionInfo_devFQDN').text(deviceData.devFQDN || '');
  $('#sessionInfo_devLastConnection').text(localizeTimestamp(deviceData.devLastConnection));
  $('#sessionInfo_devFirstConnection').text(localizeTimestamp(deviceData.devFirstConnection));

  // Same badge markup devices-table.js/network-tabs.js/network-api.js all use
  // (<span class="badge ${cssClass}">) - a plain span, not their <a href>, since
  // that link just points back at the device page we're already on.
  const statusBadge = badgeFromDevice(deviceData);
  $('#sessionInfo_devStatus').html(`<span class="badge ${statusBadge.cssClass}">${statusBadge.iconHtml} ${statusBadge.label}</span>`);
}

// -----------------------------------------------------------------------------
// Renders one chip list (Known IPs or IP History) into targetSelector, or a
// "No data" placeholder if items is empty. Shared by renderIpLists() below so
// both lists use identical chip markup.
function renderIpChipList(targetSelector, items) {
  if (items.length === 0) {
    $(targetSelector).html(`<span class="text-muted">${getString('Gen_No_Data')}</span>`);
    return;
  }

  const chips = items.map(({ entry, value }) => {
    return `<span class="label label-default" style="margin: 2px; display: inline-block;">${value} &middot; ${entry.plugin}</span>`;
  }).join(' ');

  $(targetSelector).html(chips);
}

// -----------------------------------------------------------------------------
// Known IPs / IP History: two compact chip lists, not a table, split from a
// single getSourcesFieldData() fetch (the same one Field View uses) rather
// than two separate queries - one request, filtered client-side into two
// buckets by status. Only plugins registered in field_views.ip are
// considered, and each one's value is read from its exact registered column
// (getFieldViewDefinitions()/resolveFieldValueForPlugin(), shared with Field
// View) - not a fallback chain over whichever watchedValue happens to be
// non-empty, which would also pick up unrelated data (e.g. a port number)
// from a plugin that was never registered for the "ip" field.
//
// status === 'missing-in-last-scan' doesn't mean the IP is permanently gone -
// it only means the owning plugin's own last run didn't re-report it, and it
// can flip back to 'exists' on that plugin's very next run. So rather than
// hiding those entries outright (which just looks like missing data), they
// go into their own "IP History" list instead of being dropped.
async function renderIpLists(mac) {
  const [fieldViews, entries] = await Promise.all([getFieldViewDefinitions(), getSourcesFieldData(mac)]);
  const ipColumns = (fieldViews.ip && fieldViews.ip.columns) || [];

  const withIpValue = entries
    .map(e => ({ entry: e, value: resolveFieldValueForPlugin(ipColumns, e) }))
    .filter(({ value }) => value);

  const known = withIpValue.filter(({ entry }) => entry.status !== 'missing-in-last-scan');
  const history = withIpValue.filter(({ entry }) => entry.status === 'missing-in-last-scan');

  renderIpChipList('#sessionInfo_knownIps', known);
  renderIpChipList('#sessionInfo_ipHistory', history);
}

// -----------------------------------------------------------------------------
// Poll for visibility the same way pluginsFieldView.php's fieldViewUpdater()
// does - deviceData is populated asynchronously by deviceDetailsEdit.php's own
// getDeviceData(), so wait for it rather than assuming it's ready.
//
// Tracks the mac (not just a one-time flag) so switching devices while this
// tab stays active re-renders instead of leaving the previous device's stale
// values on screen - mirroring fieldViewUpdater()'s currentMac !== lastMac
// check. Also resets the "initialized" flag whenever deviceData becomes
// unavailable (e.g. cleared mid-switch), so the skeleton that gets shown
// again in that case is guaranteed a matching hide once real data returns -
// without this, a device switch could re-show the skeleton while the
// one-time flag silently blocked the render path that would hide it again.
// .finally() (not .then()) on the render promise is a second safety net:
// if renderIpLists() ever throws or its fetch rejects, the skeleton still
// gets hidden instead of staying stuck forever.
let sessionInfoInitialized = false;
let sessionInfoLastMac = null;

function sessionInfoUpdater() {
  // A throw anywhere in here must never skip the setTimeout below - otherwise
  // the polling loop dies permanently and the skeleton is stuck visible forever
  // (this is exactly what fieldViewUpdater() avoids by deferring its render into
  // an async callback instead of calling it inline).
  try {
    if ($('#panSessionInfo').is(':visible')) {
      renderSessionInfoLabels();

      const currentMac = getMac();
      if (!deviceData || !deviceData.devMac) {
        showSessionInfoTabSkeleton();
        sessionInfoInitialized = false;
      } else if (!sessionInfoInitialized || currentMac !== sessionInfoLastMac) {
        sessionInfoInitialized = true;
        sessionInfoLastMac = currentMac;
        renderSessionInfoFields();
        // Known IPs/IP History need the GraphQL server up - gated the same
        // way fieldViewUpdater() gates renderFieldView(), so this never fires
        // (and never poisons getSourcesFieldData()'s per-mac cache with a
        // too-early failure) before the server is actually ready to answer.
        callAfterAppInitialized(() => {
          Promise.resolve(renderIpLists(currentMac)).finally(hideSessionInfoTabSkeleton);
        });
      }
    }
  } catch (err) {
    console.error('[Session Info] render failed, will retry next tick:', err);
    sessionInfoInitialized = false;
    hideSessionInfoTabSkeleton();
  }
  setTimeout(sessionInfoUpdater, 200);
}

sessionInfoUpdater();

</script>
