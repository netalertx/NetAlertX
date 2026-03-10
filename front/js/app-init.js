/* -----------------------------------------------------------------------------
 *  NetAlertX
 *  Open Source Network Guard / WIFI & LAN intrusion detector
 *
 *  app-init.js - Front module. Application lifecycle: initialization,
 *                cache orchestration, and startup sequencing.
 *                Loaded AFTER common.js — depends on showSpinner(), isEmpty(),
 *                mergeUniqueArrays(), getSetting(), getString(), getCache(),
 *                setCache(), and all cache* functions from cache.js.
 *-------------------------------------------------------------------------------
 #  jokob@duck.com                GNU GPLv3
 ----------------------------------------------------------------------------- */

// -----------------------------------------------------------------------------
// initialize
// -----------------------------------------------------------------------------

var completedCalls = []
var completedCalls_final = ['cacheApiConfig', 'cacheSettings', 'cacheStrings', 'cacheDevices'];
var lang_completedCalls = 0;


// -----------------------------------------------------------------------------
// Clearing all the caches
function clearCache() {
  showSpinner();
  sessionStorage.clear();
  localStorage.clear();
  // Wait for spinner to show and cache to clear, then reload
  setTimeout(() => {
    console.warn("clearCache called");
    window.location.reload();
  }, 100);
}

// ===================================================================
// DEPRECATED: checkSettingChanges() - Replaced by SSE-based manager
// Settings changes are now handled via SSE events
// Kept for backward compatibility, will be removed in future version
// ===================================================================
function checkSettingChanges() {
  // SSE manager handles settings_changed events now
  if (typeof netAlertXStateManager !== 'undefined' && netAlertXStateManager.initialized) {
    return; // SSE handles this now
  }

  // Fallback for backward compatibility
  $.get('php/server/query_json.php', { file: 'app_state.json', nocache: Date.now() }, function(appState) {
    const importedMilliseconds = parseInt(appState["settingsImported"] * 1000);
    const lastReloaded = parseInt(getCache(CACHE_KEYS.INIT_TIMESTAMP));

    if (importedMilliseconds > lastReloaded) {
      console.log("Cache needs to be refreshed because of setting changes");
      setTimeout(() => {
        clearCache();
      }, 500);
    }
  });
}

// ===================================================================
// Display spinner and reload page if not yet initialized
async function handleFirstLoad(callback) {
  if (!isAppInitialized()) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    callback();
  }
}

// ===================================================================
// Execute callback once the app is initialized and GraphQL server is running
async function callAfterAppInitialized(callback) {
  if (!isAppInitialized() || !(await isGraphQLServerRunning())) {
    setTimeout(() => {
      callAfterAppInitialized(callback);
    }, 500);
  } else {
    callback();
  }
}

// ===================================================================
// Polling function to repeatedly check if the server is running
async function waitForGraphQLServer() {
  const pollInterval = 2000; // 2 seconds between each check
  let serverRunning = false;

  while (!serverRunning) {
    serverRunning = await isGraphQLServerRunning();
    if (!serverRunning) {
      console.log("GraphQL server not running, retrying in 2 seconds...");
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }
  }

  console.log("GraphQL server is now running.");
}

// -----------------------------------------------------------------------------
// Returns 1 if running, 0 otherwise
async function isGraphQLServerRunning() {
  try {
    const response = await $.get('php/server/query_json.php', { file: 'app_state.json', nocache: Date.now()});
    console.log("graphQLServerStarted: " + response["graphQLServerStarted"]);
    setCache(CACHE_KEYS.GRAPHQL_STARTED, response["graphQLServerStarted"]);
    return response["graphQLServerStarted"];
  } catch (error) {
    console.error("Failed to check GraphQL server status:", error);
    return false;
  }
}

// Throttle isAppInitialized logging so the console isn't spammed on every poll.
let _isAppInit_lastLogTime = 0;
function _isAppInitLog(msg) {
  const now = Date.now();
  if (now - _isAppInit_lastLogTime > 5000) { // log at most once per 5s
    console.log(msg);
    _isAppInit_lastLogTime = now;
  }
}

// -----------------------------------------------------------------------------
// Check if the code has been executed before by checking localStorage
function isAppInitialized() {

  lang_shouldBeCompletedCalls = getLangCode() == 'en_us' ? 1 : 2;

  // check if each ajax call completed succesfully
  for (const call_name of completedCalls_final) {
    if (getCache(CACHE_KEYS.initFlag(call_name)) != "true") {
      _isAppInitLog(`[isAppInitialized] waiting on ${call_name} (value: ${getCache(CACHE_KEYS.initFlag(call_name))})`);
      return false;
    }
  }

  // check if all required languages chached
  if(parseInt(getCache(CACHE_KEYS.STRINGS_COUNT)) != lang_shouldBeCompletedCalls)
  {
    _isAppInitLog(`[isAppInitialized] waiting on cacheStrings: ${getCache(CACHE_KEYS.STRINGS_COUNT)} of ${lang_shouldBeCompletedCalls}`);
    return false;
  }

  return true;
}

// Retry a single async init step up to maxAttempts times with a delay.
async function retryStep(name, fn, maxAttempts = 3, delayMs = 1500) {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      await fn();
      return; // success
    } catch (err) {
      console.warn(`[executeOnce] ${name} failed (attempt ${attempt}/${maxAttempts}):`, err);
      if (attempt < maxAttempts) {
        await new Promise(r => setTimeout(r, delayMs));
      } else {
        console.error(`[executeOnce] ${name} permanently failed after ${maxAttempts} attempts.`);
      }
    }
  }
}

// -----------------------------------------------------------------------------
// Main execution logic
let _executeOnceRunning = false;
async function executeOnce() {
  if (_executeOnceRunning) {
    console.log('[executeOnce] Already running — skipping duplicate call.');
    return;
  }
  _executeOnceRunning = true;
  showSpinner();

  // Auto-bust stale cache if code version has changed since last init.
  // Clears localStorage in-place so the subsequent init runs fresh without
  // requiring a page reload.
  if (getCache(CACHE_KEYS.CACHE_VERSION) !== NAX_CACHE_VERSION) {
    console.log(`[executeOnce] Cache version mismatch (stored: "${getCache(CACHE_KEYS.CACHE_VERSION)}", expected: "${NAX_CACHE_VERSION}"). Clearing cache.`);
    localStorage.clear();
    sessionStorage.clear();
  }

  if (!isAppInitialized()) {
    try {
      await waitForGraphQLServer(); // Wait for the server to start

      await retryStep('cacheApiConfig', cacheApiConfig);  // Bootstrap: API_TOKEN + GRAPHQL_PORT from app.conf
      await retryStep('cacheDevices',   cacheDevices);
      await retryStep('cacheSettings',  cacheSettings);
      await retryStep('cacheStrings',   cacheStrings);

      console.log("All AJAX callbacks have completed");
      onAllCallsComplete();
    } finally {
      _executeOnceRunning = false;
    }
  } else {
    _executeOnceRunning = false;
  }
}


// -----------------------------------------------------------------------------
// Function to handle successful completion of an AJAX call
const handleSuccess = (callName) => {
  console.log(`AJAX call successful: ${callName}`);

  if(callName.includes("cacheStrings"))
  {
    completed_tmp = getCache(CACHE_KEYS.STRINGS_COUNT);
    completed_tmp == "" ? completed_tmp = 0 : completed_tmp = completed_tmp;
    completed_tmp++;
    setCache(CACHE_KEYS.STRINGS_COUNT, completed_tmp);
  }

  setCache(CACHE_KEYS.initFlag(callName), true)
};

// -----------------------------------------------------------------------------
// Function to handle failure of an AJAX call
const handleFailure = (callName, callback) => {
  msg = `AJAX call ${callName} failed`
  console.error(msg);
  if (typeof callback === 'function') {
    callback(new Error(msg));
  }
};

// -----------------------------------------------------------------------------
// Function to execute when all AJAX calls have completed
const onAllCallsComplete = () => {
  completedCalls = mergeUniqueArrays(getCache(CACHE_KEYS.COMPLETED_CALLS).split(','), completedCalls);
  setCache(CACHE_KEYS.COMPLETED_CALLS, completedCalls);

  // Check if all necessary strings are initialized
  if (areAllStringsInitialized()) {
    const millisecondsNow = Date.now();
    setCache(CACHE_KEYS.INIT_TIMESTAMP, millisecondsNow);
    setCache(CACHE_KEYS.CACHE_VERSION, NAX_CACHE_VERSION);

    console.log('✔ Cache initialized');

  } else {
    // If not all strings are initialized, retry initialization
    console.log('❌ Not all strings are initialized. Retrying...');
    executeOnce();
    return;
  }

  // Call any other initialization functions here if needed

};

// Function to check if all necessary strings are initialized
const areAllStringsInitialized = () => {
  // Implement logic to check if all necessary strings are initialized
  // Return true if all strings are initialized, false otherwise
  return getString('UI_LANG_name') != ""
};

// Call the function to execute the code
executeOnce();

// Set timer for regular UI refresh if enabled
setTimeout(() => {

  // page refresh if configured
  const refreshTime = getSetting("UI_REFRESH");
  if (refreshTime && refreshTime !== "0" && refreshTime !== "") {
    console.log("Refreshing page becasue UI_REFRESH setting enabled.");
    newTimerRefreshData(clearCache, parseInt(refreshTime)*1000);
  }

  // Check if page needs to refresh due to setting changes
  checkSettingChanges()

}, 10000);


console.log("init app-init.js");
