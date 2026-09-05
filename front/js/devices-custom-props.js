// =============================================================================
// devices-custom-props.js — Devices list page: per-device custom property
// action icons (see docs/CUSTOM_PROPERTIES.md).
// =============================================================================

// -----------------------------------------------------------------------------
// Handle custom actions/properties on a device.
//
// CUSTPROP_name and CUSTPROP_args support {{fieldName}} wildcards (e.g.
// {{devLastIP}}) resolved against this row's own fields - see GH #1773. The
// resulting action is dispatched via a single delegated click handler reading
// data-* attributes (see below) rather than an inline onclick="..." string,
// so a device-controlled value (a DHCP hostname containing a quote, say)
// can't break out of inline JS the way it could with string-built onclick
// handlers.
function renderCustomProps(custProps, device) {
  const mac = device.devMac;

  if (!isBase64(custProps)) {
    console.error(`Unable to decode CustomProps for ${mac}`);
    console.error(custProps);
    return "Error, check browser Console log";
  }

  const props = JSON.parse(atob(custProps));
  let html = "";

  props.forEach((propGroup) => {
    const propMap = Object.fromEntries(
      propGroup.map(prop => Object.entries(prop)[0]) // Convert array of objects to key-value pairs
    );

    if (propMap["CUSTPROP_show"] !== true) {
      return; // Not visible
    }

    const type = propMap["CUSTPROP_type"];
    const isUrlType = (type === "link" || type === "link_new_tab");

    // Plain (unescaped) resolved values, for the human-readable tooltip.
    const namePlain = resolveDeviceWildcards(propMap["CUSTPROP_name"], device);
    const argsPlain = resolveDeviceWildcards(propMap["CUSTPROP_args"], device);

    // The value actually used for navigation: URL-encode substituted fields
    // when this prop's args is a URL, so e.g. a device name with a space or
    // "&" in it can't corrupt the query string.
    const argsForAction = isUrlType
      ? resolveDeviceWildcards(propMap["CUSTPROP_args"], device, encodeURIComponent)
      : argsPlain;

    const notesPlain = propMap["CUSTPROP_notes"] || "";

    html += `<div class="pointer devicePropAction"
                  data-action="${encodeSpecialChars(type)}"
                  data-args="${encodeSpecialChars(argsForAction)}"
                  data-name="${encodeSpecialChars(namePlain)}"
                  data-notes="${encodeSpecialChars(notesPlain)}"
                  data-mac="${encodeSpecialChars(mac)}"
                  title="${encodeSpecialChars(`${namePlain} ${argsPlain}`)}">
               ${atob(propMap["CUSTPROP_icon"])}
             </div>`;
  });

  return html;
}

// Single delegated handler for every custom-property action rendered by
// renderCustomProps() above - bound once, so it keeps working after
// DataTables redraws without needing to be re-attached per row.
$(document).on('click', '.devicePropAction', function () {
  const el = $(this);
  const action = el.data('action');
  const args = el.data('args') ?? '';
  const name = el.data('name') ?? '';
  const notes = el.data('notes') ?? '';
  const mac = el.data('mac') ?? '';

  switch (action) {
    case "show_notes":
      showModalOK(name, notes);
      break;
    case "link":
      window.location.href = args;
      break;
    case "link_new_tab":
      openInNewTab(args);
      break;
    case "run_plugin":
      runPlugin(args, name);
      break;
    case "delete_dev":
      askDeleteDeviceByMac(mac);
      break;
    default:
      break;
  }
});
