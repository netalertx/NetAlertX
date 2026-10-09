// Shared fixture data and route-mocking helpers for the Sources/Session Info
// characterization tests. Every spec uses these instead of hand-rolling its
// own mock shapes, so a GraphQL/REST contract change only needs updating here.

const TEST_MAC = 'aa:bb:cc:dd:ee:01';

const PLUGINS_JSON_FIXTURE = {
  data: [
    { unique_prefix: 'FREEBOX', show_ui: true, mapped_to_table: 'CurrentScan' },
    { unique_prefix: 'ARPSCAN', show_ui: true, mapped_to_table: 'CurrentScan' },
    { unique_prefix: 'SNMPDSC', show_ui: true, mapped_to_table: 'CurrentScan' },
  ],
  field_views: {
    ip: {
      label_key: 'DevDetail_SessionTable_IP',
      value_type: 'device_ip',
      columns: [
        { plugin: 'FREEBOX', column: 'objectSecondaryId' },
        { plugin: 'ARPSCAN', column: 'watchedValue1' },
        { plugin: 'SNMPDSC', column: 'watchedValue2' },
      ],
    },
  },
};

const PLUGINS_OBJECTS_FIXTURE = [
  {
    plugin: 'FREEBOX', objectSecondaryId: 'fe80::1', watchedValue1: null, watchedValue2: null,
    watchedValue3: null, watchedValue4: null, status: 'watched-not-changed', dateTimeChanged: '2026-10-05 10:00:00',
  },
  {
    plugin: 'ARPSCAN', objectSecondaryId: null, watchedValue1: '192.168.1.50', watchedValue2: null,
    watchedValue3: null, watchedValue4: null, status: 'new', dateTimeChanged: '2026-10-05 10:01:00',
  },
  {
    plugin: 'SNMPDSC', objectSecondaryId: null, watchedValue1: null, watchedValue2: 'fe80::2',
    watchedValue3: null, watchedValue4: null, status: 'missing-in-last-scan', dateTimeChanged: '2026-10-05 09:50:00',
  },
];

// Minimal settings fixture matching the real settings GraphQL query's response
// shape (data.settings.settings) - deviceDetailsEdit.php's getDeviceData()
// reads response.data.settings.settings unconditionally, so a generic empty
// `{ data: {} }` fallback would throw there instead of letting
// renderSessionInfoLabels() populate the Known IPs labels.
const SETTINGS_FIXTURE = [
  { setKey: 'NEWDEV_devPrimaryIPv4', setName: 'Primary IPv4' },
  { setKey: 'NEWDEV_devPrimaryIPv6', setName: 'Primary IPv6' },
];

const DEVICE_DATA_FIXTURE = {
  devMac: TEST_MAC,
  devName: 'Test Device',
  devStatus: 'Online',
  devPresentLastScan: 1,
  devAlertDown: 1,
  devFlapping: 0,
  devIsSleeping: 0,
  devIsArchived: 0,
  devIsNew: 0,
  devPrimaryIPv4: '192.168.1.50',
  devPrimaryIPv6: 'fe80::1',
  devFQDN: 'test-device.lan',
  devLastConnection: '2026-10-05 10:00:00',
  devFirstConnection: '2025-01-01 00:00:00',
};

// Routes every GraphQL call through to the right fixture based on the query
// text in the POST body, and plugins.json/device endpoint by URL.
async function mockSourcesBackend(page, { mac = TEST_MAC, pluginsObjects = PLUGINS_OBJECTS_FIXTURE } = {}) {
  let pluginsObjectsCallCount = 0;

  await page.route('**/php/server/query_json.php?file=plugins.json*', route => {
    route.fulfill({ json: PLUGINS_JSON_FIXTURE });
  });

  await page.route('**/server/graphql', route => {
    const body = JSON.parse(route.request().postData());

    if (body.query.includes('pluginsObjects')) {
      pluginsObjectsCallCount += 1;
      route.fulfill({
        json: { data: { pluginsObjects: { entries: pluginsObjects } } },
      });
      return;
    }

    if (body.query.includes('settings')) {
      route.fulfill({
        json: { data: { settings: { settings: SETTINGS_FIXTURE, count: SETTINGS_FIXTURE.length } } },
      });
      return;
    }

    // Any other GraphQL query this flow happens to fire - return an
    // empty-but-valid shape rather than failing the request.
    route.fulfill({ json: { data: {} } });
  });

  await page.route(`**/server/device/${encodeURIComponent(mac)}*`, route => {
    route.fulfill({ json: DEVICE_DATA_FIXTURE });
  });

  return {
    getPluginsObjectsCallCount: () => pluginsObjectsCallCount,
  };
}

module.exports = {
  TEST_MAC,
  PLUGINS_JSON_FIXTURE,
  PLUGINS_OBJECTS_FIXTURE,
  SETTINGS_FIXTURE,
  DEVICE_DATA_FIXTURE,
  mockSourcesBackend,
};
