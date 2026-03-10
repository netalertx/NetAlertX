/* -----------------------------------------------------------------------------
*  NetAlertX
*  Open Source Network Guard / WIFI & LAN intrusion detector
*
*  common.js - Front module. Common Javascript functions
*-------------------------------------------------------------------------------
#  Puche 2021 / 2022+ jokob             jokob@duck.com                GNU GPLv3
----------------------------------------------------------------------------- */

// -----------------------------------------------------------------------------
var timerRefreshData = ''

var   emptyArr      = ['undefined', "", undefined, null, 'null'];
var   UI_LANG       = "English (en_us)";
// allLanguages is populated at init via fetchAllLanguages() from GET /languages.
// Do not hardcode this list — add new languages to languages.json instead.
let   allLanguages  = [];
var   settingsJSON  = {}

// NAX_CACHE_VERSION and CACHE_KEYS moved to cache.js


// getCache, setCache, fetchJson, getAuthContext moved to cache.js

// -----------------------------------------------------------------------------
// Fetch the canonical language list from GET /languages and populate allLanguages.
// Must be called after the API token is available (e.g. alongside cacheStrings).
// -----------------------------------------------------------------------------
function fetchAllLanguages(apiToken) {
  return fetch('/languages', {
    headers: { 'Authorization': 'Bearer ' + apiToken }
  })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      if (data && data.success && Array.isArray(data.languages)) {
        allLanguages = data.languages.map(function(l) { return l.code; });
      }
    })
    .catch(function(err) {
      console.warn('[fetchAllLanguages] Failed to load language list:', err);
    });
}


// -----------------------------------------------------------------------------
function setCookie (cookie, value, expirationMinutes='') {
  // Calc expiration date
  var expires = '';
  if (typeof expirationMinutes === 'number') {
    expires = ';expires=' + new Date(Date.now() + expirationMinutes *60*1000).toUTCString();
  }

  // Save Cookie
  document.cookie = cookie + "=" + value + expires;
}

// -----------------------------------------------------------------------------
function getCookie (cookie) {
  // Array of cookies
  var allCookies = document.cookie.split(';');

  // For each cookie
  for (var i = 0; i < allCookies.length; i++) {
    var currentCookie = allCookies[i].trim();

    // If the current cookie is the correct cookie
    if (currentCookie.indexOf (cookie +'=') == 0) {
      // Return value
      return currentCookie.substring (cookie.length+1);
    }
  }

  // Return empty (not found)
  return "";
}


// -----------------------------------------------------------------------------
function deleteCookie (cookie) {
  document.cookie = cookie + '=;expires=Thu, 01 Jan 1970 00:00:00 UTC';
}




// cacheApiConfig, cacheSettings, getSettingOptions, getSetting moved to cache.js

// -----------------------------------------------------------------------------
// cacheStrings, getString, getLangCode moved to cache.js

  const tz = getSetting("TIMEZONE") || 'Europe/Berlin';
  const LOCALE = getSetting('UI_LOCALE') || 'en-GB';

// -----------------------------------------------------------------------------
// DateTime utilities
// -----------------------------------------------------------------------------
function localizeTimestamp(input) {


  input = String(input || '').trim();

  // 1. Unix timestamps (10 or 13 digits)
  if (/^\d+$/.test(input)) {
    const ms = input.length === 10 ? parseInt(input, 10) * 1000 : parseInt(input, 10);
    return new Intl.DateTimeFormat('default', {
      timeZone: tz,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false
    }).format(new Date(ms));
  }

 // 2. European DD/MM/YYYY
  let match = input.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:[ ,]+(\d{1,2}:\d{2}(?::\d{2})?))?$/);
  if (match) {
    let [, d, m, y, t = "00:00:00", tzPart = ""] = match;
    const dNum = parseInt(d, 10);
    const mNum = parseInt(m, 10);

    if (dNum <= 12 && mNum > 12) {
    } else {
      const iso = `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}T${t.length===5 ? t + ":00" : t}${tzPart}`;
      return formatSafe(iso, tz);
    }
  }

  // 3. US MM/DD/YYYY
  match = input.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:[ ,]+(\d{1,2}:\d{2}(?::\d{2})?))?(.*)$/);
  if (match) {
    let [, m, d, y, t = "00:00:00", tzPart = ""] = match;
    const iso = `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}T${t.length===5?t+":00":t}${tzPart}`;
    return formatSafe(iso, tz);
  }

  // 4. ISO YYYY-MM-DD with optional Z/+offset
  match = input.match(/^(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])[ T](\d{1,2}:\d{2}(?::\d{2})?)(Z|[+-]\d{2}:?\d{2})?$/);
  if (match) {
    let [, y, m, d, time, offset = ""] = match;
    const iso = `${y}-${m}-${d}T${time.length===5?time+":00":time}${offset}`;
    return formatSafe(iso, tz);
  }

  // 5. RFC2822 / "25 Aug 2025 13:45:22 +0200"
  match = input.match(/^\d{1,2} [A-Za-z]{3,} \d{4}/);
  if (match) {
    return formatSafe(input, tz);
  }

  // 6. DD-MM-YYYY with optional time
  match = input.match(/^(\d{1,2})-(\d{1,2})-(\d{4})(?:[ T](\d{1,2}:\d{2}(?::\d{2})?))?$/);
  if (match) {
    let [, d, m, y, time = "00:00:00"] = match;
    const iso = `${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}T${time.length===5?time+":00":time}`;
    return formatSafe(iso, tz);
  }

  // 7. Strict YYYY-DD-MM with optional time
  match = input.match(/^(\d{4})-(0[1-9]|[12]\d|3[01])-(0[1-9]|1[0-2])(?:[ T](\d{1,2}:\d{2}(?::\d{2})?))?$/);
  if (match) {
    let [, y, d, m, time = "00:00:00"] = match;
    const iso = `${y}-${m}-${d}T${time.length === 5 ? time + ":00" : time}`;
    return formatSafe(iso, tz);
  }

  // 8. Fallback
  return formatSafe(input, tz);

  function formatSafe(str, tz) {

    // CHECK: Does the input string have timezone information?
    // - Ends with Z: "2026-02-11T11:37:02Z"
    // - Has GMT±offset: "Wed Feb 11 2026 12:34:12 GMT+1100 (...)"
    // - Has offset at end: "2026-02-11 11:37:02+11:00"
    // - Has timezone name in parentheses: "(Australian Eastern Daylight Time)"
    const hasOffset = /Z$/i.test(str.trim()) ||
                      /GMT[+-]\d{2,4}/.test(str) ||
                      /[+-]\d{2}:?\d{2}$/.test(str.trim()) ||
                      /\([^)]+\)$/.test(str.trim());

    // ⚠️ CRITICAL: All DB timestamps are stored in UTC without timezone markers.
    // If no offset is present, we must explicitly mark it as UTC by appending 'Z'
    // so JavaScript doesn't interpret it as local browser time.
    let isoStr = str.trim();
    if (!hasOffset) {
      // Ensure proper ISO format before appending Z
      // Replace space with 'T' if needed: "2026-02-11 11:37:02" → "2026-02-11T11:37:02Z"
      isoStr = isoStr.trim().replace(/^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})$/, '$1T$2') + 'Z';
    }

    const date = new Date(isoStr);
    if (!isFinite(date)) {
      console.error(`ERROR: Couldn't parse date: '${str}' with TIMEZONE ${tz}`);
      return 'Failed conversion';
    }

    return new Intl.DateTimeFormat(LOCALE, {
      // Convert from UTC to user's configured timezone
      timeZone: tz,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false
    }).format(date);
  }
}


/**
 * Returns start and end date for a given period.
 * @param {string} period - "1 day", "7 days", "1 month", "1 year", "100 years"
 * @returns {{start: string, end: string}} - Dates in "YYYY-MM-DD HH:MM:SS" format
 */
function getPeriodStartEnd(period) {
  const now = new Date();
  let start = new Date(now); // default start = now
  let end = new Date(now);   // default end = now

  switch (period) {
    case "1 day":
      start.setDate(now.getDate() - 1);
      break;
    case "7 days":
      start.setDate(now.getDate() - 7);
      break;
    case "1 month":
      start.setMonth(now.getMonth() - 1);
      break;
    case "1 year":
      start.setFullYear(now.getFullYear() - 1);
      break;
    case "100 years":
      start = new Date(0); // very old date for "all"
      break;
    default:
      console.warn("Unknown period, using 1 month as default");
      start.setMonth(now.getMonth() - 1);
  }

  // Helper function to format date as "YYYY-MM-DD HH:MM:SS"
  const formatDate = (date) => {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
           `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  };

  return {
    start: formatDate(start),
    end: formatDate(end)
  };
}

// -----------------------------------------------------------------------------
// String utilities
// -----------------------------------------------------------------------------


// ----------------------------------------------------
/**
 * Replaces double quotes within single-quoted strings, then converts all single quotes to double quotes,
 * while preserving the intended structure.
 *
 * @param {string} inputString - The input string to process.
 * @returns {string} - The processed string with transformations applied.
 */
function processQuotes(inputString) {
  // Step 1: Replace double quotes within single-quoted strings
  let tempString = inputString.replace(/'([^']*?)'/g, (match, p1) => {
    const escapedContent = p1.replace(/"/g, '_escaped_double_quote_'); // Temporarily replace double quotes
    return `'${escapedContent}'`;
  });

  // Step 2: Replace all single quotes with double quotes
  tempString = tempString.replace(/'/g, '"');

  // Step 3: Restore escaped double quotes
  const processedString = tempString.replace(/_escaped_double_quote_/g, "'");

  return processedString;
}

// ----------------------------------------------------
function jsonSyntaxHighlight(json) {
  if (typeof json != 'string') {
       json = JSON.stringify(json, undefined, 2);
  }
  json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
      var cls = 'number';
      if (/^"/.test(match)) {
          if (/:$/.test(match)) {
              cls = 'key';
          } else {
              cls = 'string';
          }
      } else if (/true|false/.test(match)) {
          cls = 'boolean';
      } else if (/null/.test(match)) {
          cls = 'null';
      }
      return '<span class="' + cls + '">' + match + '</span>';
  });
}

// ----------------------------------------------------
function isValidBase64(str) {
  // Base64 characters set
  var base64CharacterSet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
  // Remove all valid characters from the string
  var invalidCharacters = str.replace(new RegExp('[' + base64CharacterSet + ']', 'g'), '');
  // If there are any characters left, the string is invalid
  return invalidCharacters === '';
}

// -------------------------------------------------------------------
// Utility function to check if the value is already Base64
function isBase64(value) {
  if (typeof value !== "string" || value.trim() === "") return false;

  // Must have valid length
  if (value.length % 4 !== 0) return false;

  // Valid Base64 characters
  const base64Regex = /^[A-Za-z0-9+/]+={0,2}$/;
  if (!base64Regex.test(value)) return false;


  try {
    const decoded = atob(value);

    // Re-encode
    const reencoded = btoa(decoded);

    if (reencoded !== value) return false;

    // Extra verification:
    // Ensure decoding didn't silently drop bytes (atob bug)
    // Encode raw bytes: check if large char codes exist (invalid UTF-16)
    for (let i = 0; i < decoded.length; i++) {
      const code = decoded.charCodeAt(i);
      if (code > 255) return false; // invalid binary byte
    }

    return true;
  } catch (e) {
    return false;
  }
}


// ----------------------------------------------------
function isValidJSON(jsonString) {
  try {
      JSON.parse(jsonString);
      return true;
  } catch (e) {
      return false;
  }
}

// ----------------------------------------------------
// method to sanitize input so that HTML and other things don't break
function encodeSpecialChars(str) {
  return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
}
// ----------------------------------------------------
function decodeSpecialChars(str) {
  return str
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#039;/g, '\'');
}

// ----------------------------------------------------
// base64 conversion of UTF8 chars
function utf8ToBase64(str) {
  // Convert the string to a Uint8Array using TextEncoder
  const utf8Bytes = new TextEncoder().encode(str);

  // Convert the Uint8Array to a base64-encoded string
  return btoa(String.fromCharCode(...utf8Bytes));
}


// -----------------------------------------------------------------------------
// General utilities
// -----------------------------------------------------------------------------

// check if JSON object
function isJsonObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}


// remove unnecessary lines from the result
function sanitize(data)
{
  return data.replace(/(\r\n|\n|\r)/gm,"").replace(/[^\x00-\x7F]/g, "")
}


// -----------------------------------------------------------------------------
// Check and handle locked database
function handle_locked_DB(data)
{
  if(data.includes('database is locked'))
  {
    // console.log(data)
    showSpinner()

    setTimeout(function() {
      console.warn("Database locked - reload")
      location.reload();
    }, 5000);
  }
}

// -----------------------------------------------------------------------------
function numberArrayFromString(data)
{
  data = JSON.parse(sanitize(data));
  return data.replace(/\[|\]/g, '').split(',').map(Number);
}

// -----------------------------------------------------------------------------
// Update network parent/child relationship (network tree)
function updateNetworkLeaf(leafMac, parentMac) {
  const { apiBase, authHeader } = getAuthContext();
  const url = `${apiBase}/device/${leafMac}/update-column`;

  $.ajax({
    method: "POST",
    url: url,
    headers: authHeader,
    data: JSON.stringify({ columnName: "devParentMAC", columnValue: parentMac }),
    contentType: "application/json",
    success: function(response) {
      if(response.success) {
        showMessage("Saved");
        // Remove navigation prompt "Are you sure you want to leave..."
        window.onbeforeunload = null;
      } else {
        showMessage("ERROR: " + (response.error || "Unknown error"));
      }
    },
    error: function(xhr, status, error) {
      console.error("Error updating network leaf:", status, error);
      showMessage("ERROR: " + (xhr.responseJSON?.error || error));
    }
  });
}

// -----------------------------------------------------------------------------
// Legacy function wrapper for backward compatibility
function saveData(functionName, id, value) {
  if (functionName === 'updateNetworkLeaf') {
    updateNetworkLeaf(id, value);
  } else {
    console.warn("saveData called with unknown functionName:", functionName);
    showMessage("ERROR: Unknown function");
  }
}


// -----------------------------------------------------------------------------
// create a link to the device
function createDeviceLink(input)
{
  if(checkMacOrInternet(input))
  {
    return `<span class="anonymizeMac"><a href="/deviceDetails.php?mac=${input}" target="_blank">${getDevDataByMac(input, "devName")}</a><span>`
  }

  return input;
}


// -----------------------------------------------------------------------------
// remove an item from an array
function removeItemFromArray(arr, value) {
  var index = arr.indexOf(value);
  if (index > -1) {
    arr.splice(index, 1);
  }
  return arr;
}

// -----------------------------------------------------------------------------
function sleep(milliseconds) {
  const date = Date.now();
  let currentDate = null;
  do {
    currentDate = Date.now();
  } while (currentDate - date < milliseconds);
}

// ---------------------------------------------------------
somethingChanged = false;
function settingsChanged()
{
  somethingChanged = true;
  // Enable navigation prompt ... "Are you sure you want to leave..."
  window.onbeforeunload = function() {
    return true;
  };
}

// -----------------------------------------------------------------------------
// Get Anchor from URL
function getUrlAnchor(defaultValue){

  target = defaultValue

  var url = window.location.href;
  if (url.includes("#")) {

    // default selection
    selectedTab = defaultValue

    // the #target from the url
    target = window.location.hash.substr(1)

    // get only the part between #...?
    if(target.includes('?'))
    {
      target = target.split('?')[0]
    }

    return target

  }

}

// -----------------------------------------------------------------------------
// get query string from URL
function getQueryString(key){
  params = new Proxy(new URLSearchParams(window.location.search), {
    get: (searchParams, prop) => searchParams.get(prop),
  });

  tmp = params[key]

  if(emptyArr.includes(tmp))
  {
    var queryParams = {};
    fullUrl = window.location.toString();

    // console.log(fullUrl);

    if (fullUrl.includes('?')) {
      var queryString = fullUrl.split('?')[1];

      // Split the query string into individual parameters
      var paramsArray = queryString.split('&');

      // Loop through the parameters array
      paramsArray.forEach(function(param) {
          // Split each parameter into key and value
          var keyValue = param.split('=');
          var keyTmp = decodeURIComponent(keyValue[0]);
          var value = decodeURIComponent(keyValue[1] || '');

          // Store key-value pair in the queryParams object
          queryParams[keyTmp] = value;
      });
    }

    // console.log(queryParams);

    tmp = queryParams[key]
  }

  result = emptyArr.includes(tmp) ? "" : tmp;

  return result
}
// -----------------------------------------------------------------------------
function translateHTMLcodes (text) {
  if (text == null || emptyArr.includes(text)) {
    return null;
  } else if (typeof text === 'string' || text instanceof String)
  {
    var text2 = text.replace(new RegExp(' ', 'g'), "&nbsp");
    text2 = text2.replace(new RegExp('<', 'g'), "&lt");
    return text2;
  }

  return "";
}


// -----------------------------------------------------------------------------
function stopTimerRefreshData () {
  try {
    clearTimeout (timerRefreshData);
  } catch (e) {}
}


// -----------------------------------------------------------------------------
function newTimerRefreshData (refeshFunction, timeToRefresh) {

  if(timeToRefresh && (timeToRefresh != 0 || timeToRefresh != ""))
  {
    time = parseInt(timeToRefresh)
  } else
  {
    time = 60000
  }

  timerRefreshData = setTimeout (function() {
    refeshFunction();
  }, time);
}


// -----------------------------------------------------------------------------
function debugTimer () {
  $('#pageTitle').html (new Date().getSeconds());
}

// -----------------------------------------------------------------------------
function secondsSincePageLoad() {
  // Get the current time since the page was loaded
  var timeSincePageLoad = performance.now();

  // Convert milliseconds to seconds
  var secondsAgo = Math.floor(timeSincePageLoad / 1000);

  return secondsAgo;
}

// -----------------------------------------------------------------------------
// Open url in new tab
function openInNewTab (url) {
  window.open(url, "_blank");
}

// -----------------------------------------------------------------------------
// Navigate to URL if the current URL is not in the provided list of URLs
function openUrl(urls) {
  var currentUrl = window.location.href;
  var mainUrl = currentUrl.match(/^.*?(?=#|\?|$)/)[0]; // Extract main URL

  var isMatch = false;

  $.each(urls,function(index, obj){

    // remove . for comaprison if in the string, e.g.: ./devices.php
    arrayUrl = obj.replace('.','')

    // check if we are on a url contained in the array
    if(mainUrl.includes(arrayUrl))
    {
      isMatch = true;
    }
  });

  // if we are not, redirect
  if (isMatch == false) {
    window.location.href = urls[0]; // Redirect to the first URL in the list if not found
  }
}

// -----------------------------------------------------------------------------
// force load URL in current window with specific anchor
function forceLoadUrl(relativeUrl) {

  window.location.replace(relativeUrl);
  window.location.reload()

}

// -----------------------------------------------------------------------------
function navigateToDeviceWithIp (ip) {

  $.get('php/server/query_json.php', { file: 'table_devices.json', nocache: Date.now() }, function(res) {

    devices = res["data"];

    mac = ""

    $.each(devices, function(index, obj) {

      if(obj.devLastIP.trim() == ip.trim())
      {
        mac = obj.devMac;

        window.open('./deviceDetails.php?mac=' + mac , "_blank");
      }
    });

  });
}

// -----------------------------------------------------------------------------
// Check if MAC or Internet
function checkMacOrInternet(inputStr) {
  // Regular expression pattern for matching a MAC address
  const macPattern = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;

  if (inputStr.toLowerCase() === 'internet') {
      return true;
  } else if (macPattern.test(inputStr)) {
      return true;
  } else {
      return false;
  }
}

// Alias
function isValidMac(value) {
  return checkMacOrInternet(value);
}

// -----------------------------------------------------------------------------
// Gte MAC from query string
function getMac(){
  params = new Proxy(new URLSearchParams(window.location.search), {
    get: (searchParams, prop) => searchParams.get(prop),
  });

  mac = params.mac;

  if (mac == "") {
    console.error("Couldn't retrieve mac");
  }

  return mac;
}

// -----------------------------------------------------------------------------
// A function used to make the IP address orderable
function isValidIPv6(ipAddress) {
  // Regular expression for IPv6 validation
  const ipv6Regex = /^([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}$|^([0-9a-fA-F]{1,4}:){1,7}:|^([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$|^([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}$|^([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}$|^([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}$|^([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}$|^[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})$/;

  return ipv6Regex.test(ipAddress);
}

function isValidIPv4(ip) {
  const ipv4Regex = /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
  return ipv4Regex.test(ip);
}


function formatIPlong(ipAddress) {
  if (ipAddress.includes(':') && isValidIPv6(ipAddress)) {
    const parts = ipAddress.split(':');

    return parts.reduce((acc, part, index) => {
      if (part === '') {
        const remainingGroups = 8 - parts.length + 1;
        return acc << (16 * remainingGroups);
      }

      const hexValue = parseInt(part, 16);
      return acc | (hexValue << (112 - index * 16));
    }, 0);
  } else {
    // Handle IPv4 address
    const parts = ipAddress.split('.');

    if (parts.length !== 4) {
      console.log("⚠ Invalid IPv4 address: " + ipAddress);
      return -1; // or any other default value indicating an error
    }

    return (parseInt(parts[0]) << 24) |
           (parseInt(parts[1]) << 16) |
           (parseInt(parts[2]) << 8) |
           parseInt(parts[3]);
  }
}

// -----------------------------------------------------------------------------
// Check if MAC is a random one
function isRandomMAC(mac)
{
  isRandom = false;

  isRandom = ["2", "6", "A", "E", "a", "e"].includes(mac[1]);

  // if detected as random, make sure it doesn't start with a prefix which teh suer doesn't want to mark as random
  if(isRandom)
  {
    $.each(createArray(getSetting("UI_NOT_RANDOM_MAC")), function(index, prefix) {

      if(mac.startsWith(prefix))
      {
        isRandom = false;
      }

    });

  }

  return isRandom;
}

  // ---------------------------------------------------------
  // Generate an array object from a string representation of an array
  function createArray(input) {
    // Is already array, return
    if (Array.isArray(input)) {
      return input;
    }
    // Empty array
    // if (input === '[]' || input === '') {
    if (input === '[]') {
      return [];
    }
    // handle integer
    if (typeof input === 'number') {
      input = input.toString();
    }

    // Regex pattern for brackets
    const patternBrackets = /(^\s*\[)|(\]\s*$)/g;
    const replacement = '';

    // Remove brackets
    const noBrackets = input.replace(patternBrackets, replacement);

    const options = [];

    // Detect the type of quote used after the opening bracket
    const firstChar = noBrackets.trim()[0];
    const isDoubleQuoted = firstChar === '"';
    const isSingleQuoted = firstChar === "'";

    // Create array while handling commas within quoted segments
    let currentSegment = '';
    let withinQuotes = false;
    for (let i = 0; i < noBrackets.length; i++) {
      const char = noBrackets[i];
      if ((char === '"' && !isSingleQuoted) || (char === "'" && !isDoubleQuoted)) {
        withinQuotes = !withinQuotes;
      }
      if (char === ',' && !withinQuotes) {
        options.push(currentSegment.trim());
        currentSegment = '';
      } else {
        currentSegment += char;
      }
    }
    // Push the last segment
    options.push(currentSegment.trim());

    // Remove quotes based on detected type
    options.forEach((item, index) => {
      let trimmedItem = item.trim();
      // Check if the string starts and ends with the same type of quote
      if ((isDoubleQuoted && trimmedItem.startsWith('"') && trimmedItem.endsWith('"')) ||
          (isSingleQuoted && trimmedItem.startsWith("'") && trimmedItem.endsWith("'"))) {
        // Remove the quotes
        trimmedItem = trimmedItem.substring(1, trimmedItem.length - 1);
      }
      options[index] = trimmedItem;
    });

    return options;
  }

// getDevDataByMac, cacheDevices, devicesListAll_JSON moved to cache.js

// -----------------------------------------------------------------------------
function isEmpty(value)
{
  return emptyArr.includes(value)
}

// -----------------------------------------------------------------------------
function mergeUniqueArrays(arr1, arr2) {
  let mergedArray = [...arr1]; // Make a copy of arr1

  arr2.forEach(element => {
      if (!mergedArray.includes(element)) {
          mergedArray.push(element);
      }
  });

  return mergedArray;
}

// -----------------------------------------------------------------------------
// Generate a GUID
function getGuid() {
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}

// -----------------------------------------------------------------------------
// UI
// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
//  Loading Spinner overlay
// -----------------------------------------------------------------------------

let spinnerTimeout = null;
let animationTime = 300

function showSpinner(stringKey = 'Loading') {
  let text = isEmpty(stringKey) ? "Loading..." : getString(stringKey || "Loading");

  if (text == ""){
    text = "Loading"
  }

  const spinner = $("#loadingSpinner");
  const target = $(".spinnerTarget").first(); // Only use the first one if multiple exist

  $("#loadingSpinnerText").text(text);

  if (target.length) {
    // Position relative to target
    const offset = target.offset();
    const width = target.outerWidth();
    const height = target.outerHeight();

    spinner.css({
      position: "absolute",
      top: offset.top,
      left: offset.left,
      width: width,
      height: height,
      zIndex: 800
    });
  } else {
    // Fullscreen fallback
    spinner.css({
      position: "fixed",
      top: 0,
      left: 0,
      width: "100%",
      height: "100%",
      zIndex: 800
    });
  }

  requestAnimationFrame(() => {
    spinner.addClass("visible");
    spinner.fadeIn(animationTime);
  });
}

function hideSpinner() {
  clearTimeout(spinnerTimeout);
  const spinner = $("#loadingSpinner");

  if (!spinner.length) return;

  const target = $(".spinnerTarget").first();

  if (target.length) {
    // Lock position to target
    const offset = target.offset();
    const width = target.outerWidth();
    const height = target.outerHeight();

    spinner.css({
      position: "absolute",
      top: offset.top,
      left: offset.left,
      width: width,
      height: height,
      zIndex: 800
    });
  } else {
    // Fullscreen fallback
    spinner.css({
      position: "fixed",
      top: 0,
      left: 0,
      width: "100%",
      height: "100%",
      zIndex: 800
    });
  }

  // Trigger fade-out and only remove styles AFTER fade completes AND display is none
  spinner.removeClass("visible").fadeOut(animationTime, () => {
    // Ensure it's really hidden before resetting styles
    spinner.css({
      display: "none"
    });

    spinner.css({
      position: "",
      top: "",
      left: "",
      width: "",
      height: "",
      zIndex: ""
    });
  });
}


// --------------------------------------------------------
// Calls a backend function to add a front-end event to an execution queue
function updateApi(apiEndpoints)
{

  // value has to be in format event|param. e.g. run|ARPSCAN
  action = `${getGuid()}|update_api|${apiEndpoints}`

  const { token: apiToken, apiBase: apiBaseUrl, authHeader } = getAuthContext();
  const url = `${apiBaseUrl}/logs/add-to-execution-queue`;

  $.ajax({
    method: "POST",
    url: url,
    headers: { ...authHeader, "Content-Type": "application/json" },
    data: JSON.stringify({ action: action }),
    success: function(data, textStatus) {
        console.log(data)
    }
  })
}

// -----------------------------------------------------------------------------
// handling smooth scrolling
// -----------------------------------------------------------------------------
function setupSmoothScrolling() {
  // Function to scroll to the element
  function scrollToElement(id) {
      $('html, body').animate({
          scrollTop: $("#" + id).offset().top - 50
      }, 1000);
  }

  // Scroll to the element when clicking on anchor links
  $('a[href*="#"]').on('click', function(event) {
      var href = $(this).attr('href');
      if (href !=='#' && href && href.includes('#') && !$(this).is('[data-toggle="collapse"]')) {
          var id = href.substring(href.indexOf("#") + 1); // Get the ID from the href attribute
          if ($("#" + id).length > 0) {
              event.preventDefault(); // Prevent default anchor behavior
              scrollToElement(id); // Scroll to the element
          }
      }
  });

  // Check if there's an ID in the URL and scroll to it
  var url = window.location.href;
  if (url.includes("#")) {
      var idFromURL = url.substring(url.indexOf("#") + 1);
      if (idFromURL != "" && $("#" + idFromURL).length > 0) {
          scrollToElement(idFromURL);
      }
  }
}

// -------------------------------------------------------------------
// Function to check if options_params contains a parameter with type "sql"
function hasSqlType(params) {
  for (let param of params) {
      if (param.type === "sql") {
          return true; // Found a parameter with type "sql"
      }
  }
  return false; // No parameter with type "sql" found
}

// -------------------------------------------------------------------
// Function to check if string is SQL query
function isSQLQuery(query) {
  // Regular expression to match common SQL keywords and syntax with word boundaries
  var sqlRegex = /\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|FROM|JOIN|WHERE|SET|VALUES|GROUP BY|ORDER BY|LIMIT)\b/i;

  return sqlRegex.test(query);
}


// -------------------------------------------------------------------
// Get corresponding plugin setting object
function getPluginSettingObject(pluginsData, setting_key, unique_prefix ) {

  result = {}
  unique_prefix == undefined ? unique_prefix = setting_key.split("_")[0] : unique_prefix = unique_prefix;

  $.each(pluginsData, function (i, plgnObj){
    // go thru plugins
    if(plgnObj.unique_prefix == unique_prefix)
    {
      // go thru plugin settings
      $.each(plgnObj["settings"], function (j, setObj){

        if(`${unique_prefix}_${setObj.function}` == setting_key)
        {
          result = setObj
        }

      });
    }
  });

  return result
}

// -------------------------------------------------------------------
// Resolve all option parameters
function resolveParams(params, template) {
  params.forEach(param => {
      // Check if the template includes the parameter name
      if (template.includes("{" + param.name + "}")) {
          // If the parameter type is 'setting', retrieve setting value
          if (param.type == "setting") {
              var value = getSetting(param.value);

              // Remove brackets and single quotes, replace them with double quotes
              value = value.replace('[','').replace(']','').replace(/'/g, '"');

              // Split the string into an array, remove empty elements
              const arr = value.split(',').filter(Boolean);

              // Join the array elements with commas
              const result = arr.join(', ');

              // Replace placeholder with setting value
              template = template.replace("{" + param.name + "}", result);
          } else {
              // If the parameter type is not 'setting', use the provided value
              template = template.replace("{" + param.name + "}", param.value);
          }
      }
  });

  // Log the resolved template
  // console.log(template);

  // Return the resolved template
  return template;
}

// -----------------------------------------------------------------------------
// check if two arrays contain same values even if out of order
function arraysContainSameValues(arr1, arr2) {
  // Check if both parameters are arrays
  if (!Array.isArray(arr1) || !Array.isArray(arr2)) {
    return false;
  } else
  {
    // Sort and stringify arrays, then compare
    return JSON.stringify(arr1.slice().sort()) === JSON.stringify(arr2.slice().sort());
  }
}

// -----------------------------------------------------------------------------
// Hide elements on the page based on the supplied setting
function hideUIelements(setKey) {

  hiddenSectionsSetting = getSetting(setKey)

  if(hiddenSectionsSetting != "") // handle if settings not yet initialized
  {

    sectionsArray = createArray(hiddenSectionsSetting)

    // remove spaces to get IDs
    var newArray = $.map(sectionsArray, function(value) {
        return value.replace(/\s/g, '');
    });

    $.each(newArray, function(index, hiddenSection) {

      if($('#' + hiddenSection))
      {
        $('#' + hiddenSection).hide()
      }

    });
  }

}

// ------------------------------------------------------------
function getDevicesList()
{
  // Read cache (skip cookie expiry check)
  const cached = getCache(CACHE_KEYS.DEVICES_ALL);
  let devicesList = parseDeviceCache(cached);

  // only loop thru the filtered down list
  visibleDevices = getCache(CACHE_KEYS.VISIBLE_MACS)

  if(visibleDevices != "") {
    visibleDevicesMACs = visibleDevices.split(',');

    devicesList_tmp = [];

    // Iterate through the data and filter only visible devices
    $.each(devicesList, function(index, item) {
      // Check if the current item's MAC exists in visibleDevicesMACs
      if (visibleDevicesMACs.includes(item.devMac)) {
        devicesList_tmp.push(item);
      }
    });

    // Update devicesList with the filtered items
    devicesList = devicesList_tmp;
  }

  return devicesList;
}


// -----------------------------------------------------------------------------
// apply theme

$(document).ready(function() {
  let theme = getSetting("UI_theme");
  if (theme) {
    theme = theme.replace("['","").replace("']","");
    // Add the theme stylesheet
    setCookie("UI_theme", theme);
    switch(theme) {
      case "Dark":
	$('head').append('<link rel="stylesheet" href="css/dark-patch.css">');
	break;
      case "System":
	$('head').append('<link rel="stylesheet" href="css/system-dark-patch.css">');
	break
    }
  } else {
    setCookie("UI_theme", "Light");
  }
});

// -----------------------------------------------------------
// Restart Backend Python Server

function askRestartBackend() {
  // Ask
  showModalWarning(getString('Maint_RestartServer'), getString('Maint_Restart_Server_noti_text'),
  getString('Gen_Cancel'), getString('Maint_RestartServer'), 'restartBackend');
}

// -----------------------------------------------------------
function restartBackend() {

  modalEventStatusId = 'modal-message-front-event'

  const { token: apiToken, apiBase: apiBaseUrl, authHeader } = getAuthContext();
  const url = `${apiBaseUrl}/logs/add-to-execution-queue`;

  // Execute
  $.ajax({
      method: "POST",
      url: url,
      headers: { ...authHeader, "Content-Type": "application/json" },
      data: JSON.stringify({ action: `cron_restart_backend` }),
      success: function(data, textStatus) {
          // showModalOk ('Result', data );

          // show message
          showModalOk(getString("general_event_title"), `${getString("general_event_description")}  <br/> <br/> <code id='${modalEventStatusId}'></code>`);

          updateModalState()

          write_notification('[Maintenance] App manually restarted', 'info')
      }
    })
}

// App lifecycle (completedCalls, executeOnce, handleSuccess, clearCache, etc.) moved to app-init.js








