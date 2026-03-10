/* -----------------------------------------------------------------------------
 *  NetAlertX
 *  Open Source Network Guard / WIFI & LAN intrusion detector
 *
 *  cache.js - Front module. Cache primitives, settings, strings, and device
 *             data caching. Loaded FIRST — no dependencies on other NAX files.
 *             All cross-file calls (handleSuccess, showSpinner, etc.) are
 *             call-time dependencies resolved after page load.
 *-------------------------------------------------------------------------------
 #  jokob@duck.com                GNU GPLv3
 ----------------------------------------------------------------------------- */

// Cache version stamp — injected by header.php from the app's .VERSION file.
// Changes automatically on every release, busting stale localStorage caches.
// Falls back to a build-time constant so local dev without PHP still works.
const NAX_CACHE_VERSION = (typeof window.NAX_APP_VERSION !== 'undefined')
  ? window.NAX_APP_VERSION
  : 'dev';

// -----------------------------------------------------------------------------
// Central registry of all localStorage cache keys.
// Use these constants (and the helper functions for dynamic keys) everywhere
// instead of bare string literals to prevent silent typo bugs.
// -----------------------------------------------------------------------------
const CACHE_KEYS = {
  // --- Init flags (dynamic) ---
  // Stores "true" when an AJAX init call completes. Use initFlag(name) below.
  initFlag:       (name) => `${name}_completed`,

  // --- Settings ---
  // Stores the value of a setting by its setKey.    nax_set_<setKey>
  setting:        (key) => `nax_set_${key}`,
  // Stores the resolved options array for a setting. nax_set_opt_<setKey>
  settingOpts:    (key) => `nax_set_opt_${key}`,

  // --- Language strings ---
  // Stores a translated string.                      pia_lang_<key>_<langCode>
  langString:     (key, langCode) => `pia_lang_${key}_${langCode}`,
  LANG_FALLBACK:  'en_us',            // fallback language code

  // --- Devices ---
  DEVICES_ALL:      'devicesListAll_JSON',  // full device list from table_devices.json
  DEVICES_TOPOLOGY: 'devicesListNew',       // filtered/sorted list for network topology

  // --- UI state ---
  VISIBLE_MACS:   'ntx_visible_macs',       // comma-separated MACs visible in current view
  SHOW_ARCHIVED:  'showArchived',           // topology show-archived toggle (network page)
  SHOW_OFFLINE:   'showOffline',            // topology show-offline toggle  (network page)

  // --- Internal init tracking ---
  GRAPHQL_STARTED:  'graphQLServerStarted', // set when GraphQL server responds
  STRINGS_COUNT:    'cacheStringsCountCompleted', // count of language packs loaded
  COMPLETED_CALLS:  'completedCalls',       // comma-joined list of completed init calls
  INIT_TIMESTAMP:   'nax_init_timestamp',   // ms timestamp of last successful cache init
  CACHE_VERSION:    'nax_cache_version',     // version stamp for auto-bust on deploy
};


// -----------------------------------------------------------------------------
// localStorage cache helpers
// -----------------------------------------------------------------------------
function getCache(key)
{
  // check cache
  cachedValue = localStorage.getItem(key)

  if(cachedValue)
  {
      return cachedValue;
  }

  return "";
}

// -----------------------------------------------------------------------------
function setCache(key, data)
{
  localStorage.setItem(key, data);
}

// -----------------------------------------------------------------------------
// Fetch data from a server-generated JSON file via query_json.php.
// Returns a Promise resolving with the "data" array from the response.
// -----------------------------------------------------------------------------
function fetchJson(file) {
  return new Promise((resolve, reject) => {
    $.get('php/server/query_json.php', { file: file, nocache: Date.now() })
      .done((res) => resolve(res['data'] || []))
      .fail((err) => reject(err));
  });
}

// -----------------------------------------------------------------------------
// Safely parse and normalize device cache data.
// Handles both direct array format and { data: [...] } format.
// Returns an array, or empty array on failure.
function parseDeviceCache(cachedStr) {
  if (!cachedStr || cachedStr === "") {
    return [];
  }

  let parsed;
  try {
    parsed = JSON.parse(cachedStr);
  } catch (err) {
    console.error('[parseDeviceCache] Failed to parse:', err);
    return [];
  }

  // If result is an object with a .data property, extract it (handles legacy format)
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed) && Array.isArray(parsed.data)) {
    console.debug('[parseDeviceCache] Extracting .data property from wrapper object');
    parsed = parsed.data;
  }

  // Ensure result is an array
  if (!Array.isArray(parsed)) {
    console.error('[parseDeviceCache] Result is not an array:', parsed);
    return [];
  }

  return parsed;
}

// -----------------------------------------------------------------------------
// Returns the API token, base URL, and a ready-to-use Authorization header
// object for all backend API calls. Centralises the repeated
// getSetting("API_TOKEN") + getApiBase() pattern.
// -----------------------------------------------------------------------------
function getAuthContext() {
  const token   = getSetting('API_TOKEN');
  const apiBase = getApiBase();
  return {
    token,
    apiBase,
    authHeader: { 'Authorization': 'Bearer ' + token },
  };
}


// -----------------------------------------------------------------------------
// Get settings from the .json file generated by the python backend
// and cache them, if available, with options
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// Bootstrap: fetch API_TOKEN and GRAPHQL_PORT directly from app.conf via the
// PHP helper endpoint. Runs before cacheSettings so that API calls made during
// or after init always have a token available — even if table_settings.json
// hasn't been generated yet. Writes values into the setting() namespace so
// getSetting("API_TOKEN") and getSetting("GRAPHQL_PORT") work immediately.
// -----------------------------------------------------------------------------
function cacheApiConfig() {
  return new Promise((resolve, reject) => {
    if (getCache(CACHE_KEYS.initFlag('cacheApiConfig')) === 'true') {
      resolve();
      return;
    }

    $.get('php/server/app_config.php', { nocache: Date.now() })
      .done((res) => {
        if (res && res.api_token) {
          setCache(CACHE_KEYS.setting('API_TOKEN'),    res.api_token);
          setCache(CACHE_KEYS.setting('GRAPHQL_PORT'), String(res.graphql_port || 20212));
          handleSuccess('cacheApiConfig');
          resolve();
        } else {
          console.warn('[cacheApiConfig] Response missing api_token — will rely on cacheSettings fallback');
          resolve(); // non-fatal: cacheSettings will still populate these
        }
      })
      .fail((err) => {
        console.warn('[cacheApiConfig] Failed to reach app_config.php:', err);
        resolve(); // non-fatal fallback
      });
  });
}

function cacheSettings()
{
  return new Promise((resolve, reject) => {
    if(getCache(CACHE_KEYS.initFlag('cacheSettings')) === "true")
    {
      resolve();
      return;
    }

    // plugins.json may not exist on first boot — treat its absence as non-fatal
    Promise.all([fetchJson('table_settings.json'), fetchJson('plugins.json').catch(() => [])])
        .then(([settingsArr, pluginsArr]) => {
          pluginsData = pluginsArr;
          settingsData = settingsArr;

          // Defensive: Accept either array or object with .data property
          // for both settings and plugins
          if (!Array.isArray(settingsData)) {
            if (settingsData && Array.isArray(settingsData.data)) {
              settingsData = settingsData.data;
            } else {
              console.error('[cacheSettings] settingsData is not an array:', settingsData);
              reject(new Error('settingsData is not an array'));
              return;
            }
          }

          // Normalize plugins array too (may have { data: [...] } format)
          if (!Array.isArray(pluginsData)) {
            if (pluginsData && Array.isArray(pluginsData.data)) {
              pluginsData = pluginsData.data;
            } else {
              console.warn('[cacheSettings] pluginsData is not an array, treating as empty');
              pluginsData = [];
            }
          }

          settingsData.forEach((set) => {
            resolvedOptions = createArray(set.setOptions)
            resolvedOptionsOld = resolvedOptions
            setPlugObj     = {};
            options_params = [];
            resolved = ""

            // proceed only if first option item contains something to resolve
            if( !set.setKey.includes("__metadata") &&
                resolvedOptions.length != 0 &&
                resolvedOptions[0].includes("{value}"))
            {
              // get setting definition from the plugin config if available
              setPlugObj = getPluginSettingObject(pluginsData, set.setKey)

              // check if options contains parameters and resolve
              if(setPlugObj != {} && setPlugObj["options_params"])
              {
                // get option_params for {value} resolution
                options_params = setPlugObj["options_params"]

                if(options_params != [])
                {
                  // handles only strings of length == 1

                  resolved = resolveParams(options_params, resolvedOptions[0])

                  if(resolved.includes('"')) // check if list of strings
                  {
                    resolvedOptions = `[${resolved}]`
                  } else // one value only
                  {
                    resolvedOptions = `["${resolved}"]`
                  }
                }
              }
            }

            setCache(CACHE_KEYS.setting(set.setKey), set.setValue)
            setCache(CACHE_KEYS.settingOpts(set.setKey), resolvedOptions)
          });

          handleSuccess('cacheSettings');
          resolve();
        })
        .catch((err) => { handleFailure('cacheSettings'); reject(err); });
  });
}

// -----------------------------------------------------------------------------
// Get a setting options value by key
function getSettingOptions (key) {

  result = getCache(CACHE_KEYS.settingOpts(key));

  if (result == "")
  {
    result = []
  }

  return result;
}

// -----------------------------------------------------------------------------
// Get a setting value by key
function getSetting (key) {

  result = getCache(CACHE_KEYS.setting(key));

  return result;
}

// -----------------------------------------------------------------------------
// Get language string
// -----------------------------------------------------------------------------
function cacheStrings() {
  return new Promise((resolve, reject) => {
    if(getCache(CACHE_KEYS.initFlag('cacheStrings')) === "true")
    {
      // Core strings are cached, but plugin strings may have failed silently on
      // the first load (non-fatal fetch).  Always re-fetch them so that plugin
      // keys like "CSVBCKP_overwrite_description" are available without needing
      // a full clearCache().
      fetchJson('table_plugins_language_strings.json')
        .catch((pluginError) => {
          console.warn('[cacheStrings early-return] Plugin language strings unavailable (non-fatal):', pluginError);
          return [];
        })
        .then((data) => {
          if (!Array.isArray(data)) { data = []; }
          data.forEach((langString) => {
            setCache(CACHE_KEYS.langString(langString.String_Key, langString.Language_Code), langString.String_Value);
          });
          resolve();
        });
      return;
    }

      // Create a promise for each language (include en_us by default as fallback)
      languagesToLoad = ['en_us']

      additionalLanguage = getLangCode()

      if(additionalLanguage != 'en_us')
      {
        languagesToLoad.push(additionalLanguage)
      }

      console.log(languagesToLoad);

      const languagePromises = languagesToLoad.map((language_code) => {
        return new Promise((resolveLang, rejectLang) => {
          // Fetch core strings and translations

          $.get(`php/templates/language/${language_code}.json?nocache=${Date.now()}`)
            .done((res) => {
              // Iterate over each key-value pair and store the translations
              Object.entries(res).forEach(([key, value]) => {
                setCache(CACHE_KEYS.langString(key, language_code), value);
              });

              // Fetch strings and translations from plugins (non-fatal — file may
              // not exist on first boot or immediately after a cache clear)
              fetchJson('table_plugins_language_strings.json')
                .catch((pluginError) => {
                  console.warn('[cacheStrings] Plugin language strings unavailable (non-fatal):', pluginError);
                  return []; // treat as empty list
                })
                .then((data) => {
                  // Defensive: ensure data is an array (fetchJson may return
                  // an object, undefined, or empty string on edge cases)
                  if (!Array.isArray(data)) { data = []; }
                  // Store plugin translations
                  data.forEach((langString) => {
                    setCache(CACHE_KEYS.langString(langString.String_Key, langString.Language_Code), langString.String_Value);
                  });

                  // Handle successful completion of language processing
                  handleSuccess('cacheStrings');
                  resolveLang();
                });
            })
            .fail((error) => {
              // Handle failure in core strings fetching
              rejectLang(error);
            });
        });
      });

      // Wait for all language promises to complete
      Promise.all(languagePromises)
        .then(() => {
          // All languages processed successfully
          resolve();
        })
        .catch((error) => {
          // Handle failure in any of the language processing
          handleFailure('cacheStrings');
          reject(error);
        });

  });
}

// -----------------------------------------------------------------------------
// Get translated language string
function getString(key) {

  function fetchString(key) {

    lang_code = getLangCode();

    let result = getCache(CACHE_KEYS.langString(key, lang_code));

    if (isEmpty(result)) {
      result = getCache(CACHE_KEYS.langString(key, CACHE_KEYS.LANG_FALLBACK));
    }

    return result;
  }

  if (isAppInitialized()) {
    return fetchString(key);
  } else {
    callAfterAppInitialized(() => fetchString(key));
  }
}

// -----------------------------------------------------------------------------
// Get current language ISO code.
// The UI_LANG setting value is always in the form "Name (code)", e.g. "English (en_us)".
// Extracting the code with a regex means this function never needs updating when a
// new language is added — the single source of truth is languages.json.
function getLangCode() {
    UI_LANG = getSetting("UI_LANG");

    const match = (UI_LANG || '').match(/\(([a-z]{2}_[a-z]{2})\)\s*$/i);
    return match ? match[1].toLowerCase() : 'en_us';
}

// -----------------------------------------------------------------------------
// A function to get a device property using the mac address as key and DB column name as parameter
//  for the value to be returned
function getDevDataByMac(macAddress, dbColumn) {

  const sessionDataKey = CACHE_KEYS.DEVICES_ALL;
  const devicesCache = getCache(sessionDataKey);

  if (!devicesCache || devicesCache == "") {
      console.warn(`[getDevDataByMac] Cache key "${sessionDataKey}" is empty — cache may not be initialized yet.`);
      return null;
  }

  const devices = parseDeviceCache(devicesCache);

  if (devices.length === 0) {
    return null;
  }

  for (const device of devices) {
      if (device["devMac"].toLowerCase() === macAddress.toLowerCase()) {

        if(dbColumn)
        {
          return device[dbColumn];
        }
        else
        {
          return device
        }
      }
  }

  console.error("⚠ Device with MAC not found:" + macAddress)
  return null; // Return a default value if MAC address is not found
}

// -----------------------------------------------------------------------------
// Cache the devices as one JSON
function cacheDevices()
{
  return new Promise((resolve, reject) => {
    if(getCache(CACHE_KEYS.initFlag('cacheDevices')) === "true")
    {
      // One-time migration: normalize legacy { data: [...] } wrapper to a plain array.
      // Old cache entries from prior versions stored the raw API envelope; re-write
      // them in the flat format so parseDeviceCache never needs the fallback branch.
      const raw = getCache(CACHE_KEYS.DEVICES_ALL);
      if (raw) {
        try {
          const p = JSON.parse(raw);
          if (p && typeof p === 'object' && !Array.isArray(p) && Array.isArray(p.data)) {
            setCache(CACHE_KEYS.DEVICES_ALL, JSON.stringify(p.data));
          }
        } catch (e) { /* ignore malformed cache – will be refreshed next init */ }
      }
      resolve();
      return;
    }

    fetchJson('table_devices.json')
      .then((arr) => {

        devicesListAll_JSON = arr;

        devicesListAll_JSON_str = JSON.stringify(devicesListAll_JSON)

        if(devicesListAll_JSON_str == "")
        {
          showSpinner()

          setTimeout(() => {
            cacheDevices()
          }, 1000);
        }

        setCache(CACHE_KEYS.DEVICES_ALL, devicesListAll_JSON_str)

        handleSuccess('cacheDevices');
        resolve();
      })
      .catch((err) => { handleFailure('cacheDevices'); reject(err); });
    }
  );
}

var devicesListAll_JSON      = [];   // this will contain a list off all devices
