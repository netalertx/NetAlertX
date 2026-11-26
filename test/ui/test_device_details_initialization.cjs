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
const bootstrapStart = appInitSource.indexOf('// Retry a single async init step');
const bootstrapEnd = appInitSource.indexOf('// Main execution logic', bootstrapStart);
assert(bootstrapStart >= 0 && bootstrapEnd > bootstrapStart, 'shared app initialization source exists');
const bootstrapScript = appInitSource.slice(bootstrapStart, bootstrapEnd);

/** Create a VM page with controllable cache setup and observable AJAX/UI state. */
function createPage(ensureAppCacheInitialized = () => Promise.resolve()) {
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
    areAllStringsInitialized: () => true,
    ensureAppCacheInitialized,
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
function createBootstrap({ initiallyReady = false, initiallyStringsReady = true, failSettings = false } = {}) {
  const calls = {};
  const flags = new Set();
  let stringsReady = initiallyStringsReady;
  let completedCalls = 0;
  const step = name => {
    calls[name] = (calls[name] || 0) + 1;
    if (name === 'cacheSettings' && failSettings) return Promise.reject(new Error('mock settings failure'));
    flags.add(name);
    return Promise.resolve();
  };
  const context = {
    Promise,
    Error,
    setTimeout: callback => setTimeout(callback, 0),
    console: { warn() {}, error() {} },
    isAppInitialized: () => initiallyReady || ['cacheApiConfig', 'cacheDevices', 'cacheSettings', 'cacheStrings', 'cachePluginStrings'].every(name => flags.has(name)),
    areAllStringsInitialized: () => stringsReady,
    cacheApiConfig: () => step('cacheApiConfig'),
    cacheDevices: () => step('cacheDevices'),
    cacheSettings: () => step('cacheSettings'),
    cacheStrings: () => step('cacheStrings'),
    cachePluginStrings: () => step('cachePluginStrings'),
    onAllCallsComplete: () => { completedCalls += 1; },
  };
  vm.createContext(context);
  vm.runInContext(bootstrapScript, context, { filename: appInitPath });
  return {
    context,
    calls,
    setStringsReady: value => { stringsReady = value; },
    get completedCalls() { return completedCalls; },
  };
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

  let finishBootstrap;
  const pending = createPage(() => new Promise(resolve => { finishBootstrap = resolve; }));
  pending.loadHandler();
  await flushPromises();
  assert.equal(pending.requests.length, 0, 'device request does not race cache initialization');
  finishBootstrap();
  await flushPromises();
  assert.equal(pending.requests.length, 1, 'device request proceeds once cache initialization completes');

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
