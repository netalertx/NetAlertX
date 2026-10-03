//--------------------------------------------------------------
// Show the "settings still applying" indicator on page load if a save left
// the settingsPendingReload cookie set (front/settings.php's save handler).
// No polling: resolution is pushed via SSE and handled entirely in
// sse_manager.js's handleStateUpdate() (step 4), which clears this same
// cookie the moment appState.settingsImported confirms the import landed.
function settingsPendingUpdateUI() {
  var isPending = getCookie("settingsPendingReload") === "true";

  $('#settingsPendingReload').toggleClass('myhidden', !isPending);
  updateNavPendingDot();
}

settingsPendingUpdateUI();
