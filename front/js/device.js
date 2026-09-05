// -----------------------------------------------------------------------------
function askDeleteDeviceByMac(mac) {

  // only try getting mac from URL if not supplied - used in inline buttons on in the my devices listing pages
  if(isEmpty(mac))
  {
    mac = getMac()
  }

  showModalWarning(
    getString("DevDetail_button_Delete"),
    getString("DevDetail_button_Delete_ask"),
    getString('Gen_Cancel'),
    getString('Gen_Delete'),
    () => deleteDeviceByMac(mac))
}

// -----------------------------------------------------------------------------
function deleteDeviceByMac(mac) {
  // only try getting mac from URL if not supplied - used in inline buttons on in the my devices listing pages
  if(isEmpty(mac))
  {
    mac = getMac()
  }

  const apiBase = getApiBase();
  const apiToken = getSetting("API_TOKEN");
  const url = `${apiBase}/device/${mac}/delete`;


  $.ajax({
    url,
    method: "DELETE",
    headers: { "Authorization": `Bearer ${apiToken}` },
    success: function(response) {
      showMessage(response.success ? "Device deleted successfully" : (response.error || "Unknown error"));
      updateApi("devices,appevents");
    },
    error: function(xhr, status, error) {
      console.error("Error deleting device:", status, error);
      showMessage("Error: " + (xhr.responseJSON?.error || error));
    }
  });
}

// -----------------------------------------------------------------------------
// Manually trigger an on-demand plugin run, regardless of its configured RUN
// schedule. Used by the "run_plugin" device custom property action, where
// `prefix` is the plugin's unique_prefix (e.g. NMAPDEV) supplied via CUSTPROP_args.
function runPlugin(prefix, name) {
  const apiBase = getApiBase();
  const apiToken = getSetting("API_TOKEN");
  const url = `${apiBase}/plugin/${encodeURIComponent(prefix)}/run`;
  const label = name || prefix;

  $.ajax({
    url,
    method: "POST",
    headers: { "Authorization": `Bearer ${apiToken}` },
    success: function(response) {
      showMessage(response.success ? `Run triggered for ${label}` : (response.error || "Unknown error"));
    },
    error: function(xhr, status, error) {
      console.error("Error running plugin:", status, error);
      showMessage("Error: " + (xhr.responseJSON?.error || error));
    }
  });
}


