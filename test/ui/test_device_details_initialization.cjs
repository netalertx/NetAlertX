const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const sourcePath = path.resolve(__dirname, '../../front/deviceDetailsEdit.php');
const appInitPath = path.resolve(__dirname, '../../front/js/app-init.js');
const source = fs.readFileSync(sourcePath, 'utf8');
const scriptStart = source.indexOf('<script defer>') + '<script defer>'.length;
const scriptEnd = source.indexOf('</script>', scriptStart);
assert(scriptStart >= '<script defer>'.length && scriptEnd > scriptStart, 'device details inline script exists');
const inlineScript = source.slice(scriptStart, scriptEnd);
const appInitSource = fs.readFileSync(appInitPath, 'utf8');
const apiSource = fs.readFileSync(path.resolve(__dirname, '../../front/js/api.js'), 'utf8');
const apiBaseStart = apiSource.indexOf('function getApiBase()');
const apiBaseEnd = apiSource.indexOf('\n}', apiBaseStart) + 2;
const apiBaseScript = apiSource.slice(apiBaseStart, apiBaseEnd);
const bootstrapStart = appInitSource.indexOf('// Retry a single async init step');
const bootstrapEnd = appInitSource.indexOf('// Main execution logic', bootstrapStart);
assert(bootstrapStart >= 0 && bootstrapEnd > bootstrapStart, 'shared app initialization source exists');
const bootstrapScript = appInitSource.slice(bootstrapStart, bootstrapEnd);
const initCheckStart = appInitSource.indexOf('function isAppInitialized()');
const initCheckEnd = appInitSource.indexOf('// Retry a single async init step', initCheckStart);
const initCheckScript = appInitSource.slice(initCheckStart, initCheckEnd);
const executeOnceStart = appInitSource.indexOf('async function executeOnce()');
const executeOnceEnd = appInitSource.indexOf('// Function to handle successful completion', executeOnceStart);
const executeOnceScript = appInitSource.slice(executeOnceStart, executeOnceEnd);

/** Create a VM page with controllable cache setup and observable AJAX/UI state. */
function createPage(ensureAppCacheInitialized = () => Promise.resolve(), waitForGraphQLServer = () => Promise.resolve()) {
  let loadHandler;
  const requests = [];
  const state = { errorVisible: false, errorText: '', formCleared: false, saveDisabled: false };
  const selector = target => ({
    length: 0,
    val: () => '7',
    text(value) {
      if (target === '#device-details-init-error' && value !== undefined) state.errorText = value;
      return this;
    },
    removeClass() { return this; },
    show() { if (target === '#device-details-init-error') state.errorVisible = true; return this; },
    empty() { if (target === '#edit-form') state.formCleared = true; return this; },
    prop(name, value) { if (target === '#btnSave' && name === 'disabled') state.saveDisabled = value; return this; },
    fadeOut(_duration, callback) { if (callback) callback.call(this); return this; },
    hide() { return this; },
    stop() { return this; },
    fadeIn() { return this; },
  });
  selector.ajax = options => requests.push(options);
  const context = {
    console,
    window: { addEventListener: (name, callback) => { if (name === 'load') loadHandler = callback; } },
    document: {},
    $: null, setTimeout: () => 1,
    getSetting: key => key === 'API_TOKEN' ? 'test-token' : '',
    getApiBase: () => 'http://localhost/api',
    getMac: () => 'aa:bb:cc:dd:ee:01',
    showSpinner() {}, hideSpinner() {}, hideDetailsTabSkeleton() {},
    isAppInitialized: () => true,
    isAppCacheInitialized: () => true,
    areAllStringsInitialized: () => true,
    ensureAppCacheInitialized,
    waitForGraphQLServer,
  };
  function $(...args) { return selector(...args); }
  $.ajax = selector.ajax;
  context.isFakeMac = () => {};
  context.$ = $;
  vm.createContext(context);
  vm.runInContext(inlineScript, context, { filename: sourcePath });
  return { context, requests, state, get loadHandler() { return loadHandler; } };
}

/** Wait for the editor's queued Promise handlers to settle. */
async function flushPromises() {
  await new Promise(resolve => setImmediate(resolve));
}

/** Evaluate the actual app-init bootstrap with controllable cache steps. */
function createBootstrap({ initiallyReady = false, initiallyStringsReady = true, failSettings = false, failApiConfig = false, initiallyFallbackReady = false, fallbackToken = 'fallback-token', apiBase = '/server' } = {}) {
  const calls = {};
  const flags = new Set();
  let stringsReady = initiallyStringsReady;
  let apiToken = initiallyFallbackReady ? fallbackToken : '';
  if (initiallyFallbackReady) {
    for (const name of ['cacheDevices', 'cacheSettings', 'cacheStrings', 'cachePluginStrings']) flags.add(name);
  }
  let completedCalls = 0;
  const step = name => {
    calls[name] = (calls[name] || 0) + 1;
    if (name === 'cacheSettings' && failSettings) return Promise.reject(new Error('mock settings failure'));
    if (name === 'cacheApiConfig' && failApiConfig) return Promise.resolve();
    flags.add(name);
    if (name === 'cacheSettings') apiToken = fallbackToken;
    return Promise.resolve();
  };
  const context = {
    Promise,
    Error,
    setTimeout: callback => setTimeout(callback, 0),
    console: { log() {}, warn() {}, error() {} },
    CACHE_KEYS: { initFlag: name => `${name}_completed`, STRINGS_COUNT: 'strings_count', CACHE_VERSION: 'cache_version' },
    completedCalls_final: ['cacheApiConfig', 'cacheDevices', 'cacheSettings', 'cacheStrings', 'cachePluginStrings'],
    getCache: key => key === 'strings_count' ? '1' : key === 'cache_version' ? 'dev' : typeof key === 'string' && flags.has(key.replace('_completed', '')) ? 'true' : '',
    getLangCode: () => 'en_us',
    _isAppInitLog: () => {},
    getSetting: key => key === 'API_TOKEN' ? apiToken : key === 'BACKEND_API_URL' ? apiBase : '',
    isAppInitialized: () => initiallyReady,
    areAllStringsInitialized: () => stringsReady,
    cacheApiConfig: () => step('cacheApiConfig'),
    cacheDevices: () => step('cacheDevices'),
    cacheSettings: () => step('cacheSettings'),
    cacheStrings: () => step('cacheStrings'),
    cachePluginStrings: () => step('cachePluginStrings'),
    onAllCallsComplete: () => { completedCalls += 1; },
  };
  vm.createContext(context);
  vm.runInContext(apiBaseScript, context, { filename: path.resolve(__dirname, '../../front/js/api.js') });
  vm.runInContext(initCheckScript, context, { filename: appInitPath });
  vm.runInContext(bootstrapScript, context, { filename: appInitPath });
  return {
    context,
    calls,
    setStringsReady: value => { stringsReady = value; },
    get completedCalls() { return completedCalls; },
  };
}

/** Run the real startup and editor callers together against one app-init context. */
function createConcurrentStartupAndEditor() {
  const bootstrap = createBootstrap();
  const context = bootstrap.context;
  let loadHandler;
  let releaseBackend;
  const backendReady = new Promise(resolve => { releaseBackend = resolve; });
  let backendWaits = 0;
  const requests = [];
  const state = { errorVisible: false, errorText: '', formCleared: false, saveDisabled: false };
  const selector = target => ({
    length: 0,
    val: () => '7',
    text(value) { if (target === '#device-details-init-error' && value !== undefined) state.errorText = value; return this; },
    removeClass() { return this; },
    show() { if (target === '#device-details-init-error') state.errorVisible = true; return this; },
    empty() { if (target === '#edit-form') state.formCleared = true; return this; },
    prop(name, value) { if (target === '#btnSave' && name === 'disabled') state.saveDisabled = value; return this; },
    fadeOut(_duration, callback) { if (callback) callback.call(this); return this; },
    hide() { return this; }, stop() { return this; }, fadeIn() { return this; },
  });
  function $(...args) { return selector(...args); }
  $.ajax = options => requests.push(options);
  context.$ = $;
  context.window = { addEventListener: (name, callback) => { if (name === 'load') loadHandler = callback; } };
  context.document = {};
  context.isFakeMac = () => {};
  context.getMac = () => 'aa:bb:cc:dd:ee:01';
  context.showSpinner = () => {};
  context.hideSpinner = () => {};
  context.hideDetailsTabSkeleton = () => {};
  context.showDeviceDetailsInitError = message => { state.errorVisible = true; state.errorText = message; };
  context.localStorage = { clear() {} };
  context.sessionStorage = { clear() {} };
  context.NAX_CACHE_VERSION = 'dev';
  context._executeOnceRunning = false;
  context.waitForGraphQLServer = () => {
    backendWaits += 1;
    return backendReady;
  };
  vm.runInContext(executeOnceScript, context, { filename: appInitPath });
  vm.runInContext(inlineScript, context, { filename: sourcePath });
  return { context, requests, state, calls: bootstrap.calls, get backendWaits() { return backendWaits; }, get loadHandler() { return loadHandler; }, releaseBackend() { releaseBackend(); } };
}

(async () => {
  const page = createPage();
  assert.equal(typeof page.loadHandler, 'function', 'initialization waits for parser-loaded UI dependencies');
  page.loadHandler();
  await flushPromises();
  assert.equal(page.requests.length, 1, 'device request starts after cache bootstrap resolves');
  assert.match(page.requests[0].url, /\/device\/aa:bb:cc:dd:ee:01\?/);
  page.requests[0].error({}, 'error', 'network failure');
  assert.equal(page.state.errorVisible, true, 'device API failure is visible');
  assert.equal(page.state.formCleared, true, 'device API failure clears the edit form');
  assert.equal(page.state.saveDisabled, true, 'device API failure disables Save');

  const missingComponent = createPage();
  delete missingComponent.context.isFakeMac;
  missingComponent.loadHandler();
  await flushPromises();
  assert.equal(missingComponent.requests.length, 0, 'missing UI component prevents API requests');
  assert.equal(missingComponent.state.errorVisible, true, 'missing UI component is reported visibly');
  assert.match(missingComponent.state.errorText, /Required UI component/);

  const rejectedBootstrap = createPage(() => Promise.reject(new Error('cache unavailable')));
  rejectedBootstrap.loadHandler();
  await flushPromises();
  assert.equal(rejectedBootstrap.requests.length, 0, 'rejected cache bootstrap prevents API requests');
  assert.equal(rejectedBootstrap.state.errorVisible, true, 'rejected cache bootstrap is reported visibly');
  assert.equal(rejectedBootstrap.state.saveDisabled, true, 'rejected cache bootstrap disables Save');
  assert.match(rejectedBootstrap.state.errorText, /could not be initialized/);

  let finishBackend;
  let cacheInitCalls = 0;
  const pending = createPage(() => { cacheInitCalls += 1; return Promise.resolve(); }, () => new Promise(resolve => { finishBackend = resolve; }));
  pending.loadHandler();
  await flushPromises();
  assert.equal(cacheInitCalls, 0, 'editor waits for backend readiness before starting cache initialization');
  assert.equal(pending.requests.length, 0, 'device request does not race backend readiness');
  finishBackend();
  await flushPromises();
  assert.equal(cacheInitCalls, 1, 'cache initialization starts once backend becomes ready');
  assert.equal(pending.requests.length, 1, 'device request proceeds once cache initialization completes');

  const concurrent = createConcurrentStartupAndEditor();
  const startupPromise = concurrent.context.executeOnce();
  concurrent.loadHandler();
  await flushPromises();
  assert.equal(concurrent.backendWaits, 2, 'startup and editor independently wait for backend readiness');
  assert.deepEqual(concurrent.calls, {}, 'neither caller starts cache work before backend readiness');
  concurrent.releaseBackend();
  await startupPromise;
  await flushPromises();
  assert.deepEqual(Object.keys(concurrent.calls).sort(), [
    'cacheApiConfig', 'cacheDevices', 'cachePluginStrings', 'cacheSettings', 'cacheStrings',
  ].sort(), 'concurrent startup and editor share one cache initialization');
  assert.ok(Object.values(concurrent.calls).every(count => count === 1), 'each cache init step runs exactly once across both callers');
  assert.equal(concurrent.requests.length, 1, 'editor API request follows shared startup initialization');

  const bootstrap = createBootstrap();
  const firstCall = bootstrap.context.ensureAppCacheInitialized();
  const concurrentCall = bootstrap.context.ensureAppCacheInitialized();
  assert.equal(firstCall, concurrentCall, 'cold callers share a single in-flight bootstrap');
  await firstCall;
  assert.deepEqual(Object.keys(bootstrap.calls).sort(), [
    'cacheApiConfig', 'cacheDevices', 'cachePluginStrings', 'cacheSettings', 'cacheStrings',
  ].sort());
  assert.equal(bootstrap.completedCalls, 1, 'successful cold bootstrap completes once');
  const warmCalls = { ...bootstrap.calls };
  await bootstrap.context.ensureAppCacheInitialized();
  assert.deepEqual(bootstrap.calls, warmCalls, 'warm ready bootstrap performs no additional cache requests');

  bootstrap.setStringsReady(false);
  await assert.rejects(bootstrap.context.ensureAppCacheInitialized(), /strings are incomplete/);
  assert.equal(bootstrap.completedCalls, 1, 'incomplete strings do not report successful completion');
  bootstrap.setStringsReady(true);
  await bootstrap.context.ensureAppCacheInitialized();
  assert.equal(bootstrap.completedCalls, 1, 'completed cache state becomes warm-ready once strings are available');

  const warmFallback = createBootstrap({ initiallyFallbackReady: true });
  let warmFallbackWaits = 0;
  Object.assign(warmFallback.context, {
    _executeOnceRunning: false,
    NAX_CACHE_VERSION: 'dev',
    showSpinner() {},
    localStorage: { clear() {} },
    sessionStorage: { clear() {} },
    waitForGraphQLServer: () => { warmFallbackWaits += 1; return Promise.resolve(); },
  });
  vm.runInContext(executeOnceScript, warmFallback.context, { filename: appInitPath });
  await warmFallback.context.executeOnce();
  assert.equal(warmFallback.context.isAppInitialized(), true, 'preloaded valid settings fallback satisfies shared readiness');
  assert.equal(warmFallbackWaits, 1, 'startup still polls backend when cacheApiConfig flag is absent');
  assert.deepEqual(warmFallback.calls, {}, 'warm fallback does not repeat completed cache work');

  const fallbackBootstrap = createBootstrap({ failApiConfig: true });
  await fallbackBootstrap.context.ensureAppCacheInitialized();
  assert.equal(fallbackBootstrap.calls.cacheApiConfig, 1, 'non-fatal API config fetch is attempted once');
  assert.equal(fallbackBootstrap.context.getCache('cacheApiConfig_completed'), '', 'fallback does not write the completion flag');
  assert.equal(fallbackBootstrap.context.getApiBase(), '/server', 'the real API base helper supplies its same-origin default');
  assert.equal(fallbackBootstrap.context.isAppInitialized(), true, 'valid settings fallback is accepted by all shared initialization consumers without forging cacheApiConfig flag');

  for (const fallback of [
    { fallbackToken: '', apiBase: '/server', label: 'missing token' },
    { fallbackToken: '   ', apiBase: '/server', label: 'invalid blank token' },
    { fallbackToken: 'fallback-token', apiBase: '   ', label: 'missing API base' },
  ]) {
    const invalidFallback = createBootstrap({ failApiConfig: true, ...fallback });
    await assert.rejects(invalidFallback.context.ensureAppCacheInitialized(), /initialization incomplete/);
    assert.equal(invalidFallback.context.isAppInitialized(), false, `${fallback.label} does not satisfy API config readiness`);
  }

  const failedBootstrap = createBootstrap({ failSettings: true });
  await assert.rejects(failedBootstrap.context.ensureAppCacheInitialized(), /incomplete after bounded retries/);
  assert.equal(failedBootstrap.calls.cacheSettings, 3, 'failed cache step follows the existing finite three-attempt policy');
  assert.equal(failedBootstrap.completedCalls, 0, 'failed bootstrap never reports completion');
  console.log('device details initialization: load/cache gate, missing dependency, rejected bootstrap, and API failure PASS');
  console.log('app-init source: single-flight cold, warm no-op, incomplete strings, and finite retries PASS');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
