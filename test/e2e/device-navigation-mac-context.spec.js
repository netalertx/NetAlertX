// Exercise the real delayed page initialization against a synthetic deviceChip render.
const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '../..');

function functionSource(source, name, parameters) {
  const declaration = new RegExp(`^function ${name}\\(${parameters}\\)\\s*\\{[\\s\\S]*?^\\}`, 'm');
  const match = source.match(declaration);
  if (!match) throw new Error(`Could not find ${name}()`);
  return match[0];
}

test('device chip rendering cannot change the delayed device navigation context', async ({ page }) => {
  const settings = fs.readFileSync(path.join(ROOT, 'front/js/settings_utils.js'), 'utf8');
  const details = fs.readFileSync(path.join(ROOT, 'front/deviceDetails.php'), 'utf8');
  const transformer = functionSource(settings, 'reverseTransformers', 'val, transformers');
  const chevrons = functionSource(details, 'updateChevrons', 'currentMac');
  const switchDevice = functionSource(details, 'performSwitch', 'direction');
  const onloadMatch = details.match(
    /window\.onload = function\(\) \{[\s\S]*?\n\}\n+\/\/ Load history/
  );
  if (!onloadMatch) throw new Error('Could not find device-details onload initializer');
  const onload = onloadMatch[0].split('// Load history', 1)[0].trimEnd();

  await page.goto('about:blank');
  await page.addScriptTag({ content: [transformer, chevrons, switchDevice, onload].join('\n') });
  const result = await page.evaluate(() => {
    window.getDevDataByMac = (address, field) =>
      address === 'aa:bb:cc:dd:ee:02' && field === 'devName' ? 'Linked device' : null;
    window.encodeSpecialChars = value => value;
    window.getMac = () => 'aa:bb:cc:dd:ee:01';
    window.executeOnce = () => {};
    window.callAfterAppInitialized = callback => { window.pendingInitialization = callback; };
    window.updateDevicePageName = address => { window.pageNameMac = address; };
    window.getDevicesList = () => [
      { devMac: 'aa:bb:cc:dd:ee:03' }, { devMac: 'aa:bb:cc:dd:ee:01' }
    ];
    window.control = {
      html(value) { window.recordDisplay = value; return this; },
      attr() { return this; }, removeAttr() { return this; },
      addClass() { return this; }, removeClass() { return this; }, hide() { return this; }
    };
    window.$ = () => window.control;
    window.renderSmallBoxes = async () => {};
    window.main = () => {};
    window.initSourcesViewToggle = () => {};
    window.hideDeviceDetailsSkeleton = () => {};
    window.setTimeout = () => 0;

    window.onload();
    const label = reverseTransformers('aa:bb:cc:dd:ee:02', ['deviceChip']);
    window.pendingInitialization();
    return {
      globalMac: window.mac,
      pageNameMac: window.pageNameMac,
      position: window.pos,
      recordDisplay: window.recordDisplay,
      label
    };
  });

  expect(result).toEqual({
    globalMac: 'aa:bb:cc:dd:ee:01',
    pageNameMac: 'aa:bb:cc:dd:ee:01',
    position: 1,
    recordDisplay: '2 / 2',
    label: 'Linked device'
  });
});

test('previous and next switches use the selected row identity', async ({ browser }) => {
  for (const [direction, expectedMac] of [
    ['prev', 'aa:bb:cc:dd:ee:03'],
    ['next', 'aa:bb:cc:dd:ee:02']
  ]) {
    const page = await browser.newPage();
    await page.route('http://navigation.test/**', route => route.fulfill({
      status: 200, contentType: 'text/html', body: '<!doctype html><title>fixture</title>'
    }));
    await page.goto('http://navigation.test/deviceDetails.php?mac=aa%3Abb%3Acc%3Add%3Aee%3A01');
    const details = fs.readFileSync(path.join(ROOT, 'front/deviceDetails.php'), 'utf8');
    const switchDevice = functionSource(details, 'performSwitch', 'direction');
    const chevrons = functionSource(details, 'updateChevrons', 'currentMac');
    await page.addScriptTag({ content: [chevrons, switchDevice].join('\n') });
    await page.evaluate(() => {
      window.getDevicesList = () => [
        { devMac: 'aa:bb:cc:dd:ee:03' },
        { devMac: 'aa:bb:cc:dd:ee:01' },
        { devMac: 'aa:bb:cc:dd:ee:02' }
      ];
      window.control = {
        html() { return this; }, attr() { return this; }, removeAttr() { return this; },
        addClass() { return this; }, removeClass() { return this; }, hide() { return this; }
      };
      window.$ = () => window.control;
      window.setCache = () => {};
      window.pos = 1;
      window.somethingChanged = false;
      window.mac = 'aa:bb:cc:dd:ee:01';
    });

    const destination = `http://navigation.test/deviceDetails.php?mac=${encodeURIComponent(expectedMac)}`;
    await Promise.all([
      page.waitForURL(destination),
      page.evaluate(directionValue => performSwitch(directionValue), direction)
    ]);
    expect(page.url()).toBe(destination);
    await page.close();
  }
});

test('a mocked no-change save callback keeps the selected device and list index', async ({ page }) => {
  const details = fs.readFileSync(path.join(ROOT, 'front/deviceDetails.php'), 'utf8');
  const edit = fs.readFileSync(path.join(ROOT, 'front/deviceDetailsEdit.php'), 'utf8');
  const save = functionSource(edit, 'setDeviceData', "direction = '', refreshCallback = ''");
  const chevrons = functionSource(details, 'updateChevrons', 'currentMac');
  await page.goto('about:blank');
  await page.addScriptTag({ content: [save, chevrons].join('\n') });

  const result = await page.evaluate(() => {
    const selectedMac = 'aa:bb:cc:dd:ee:01';
    const values = {
      '#NEWDEV_devLastIP': '192.0.2.12', '#NEWDEV_devMac': selectedMac,
      '#NEWDEV_devSkipRepeated': '0 days'
    };
    window.$ = selector => ({
      0: { checked: false },
      val: () => values[selector] ?? (selector.endsWith('NEWDEV_devSkipRepeated') ? '0 days' : ''),
      html(value) { window.recordDisplay = value; return this; },
      attr() { return this; }, removeAttr() { return this; },
      addClass() { return this; }, removeClass() { return this; }, hide() { return this; }
    });
    window.$.ajax = request => {
      window.savedUrl = request.url;
      window.savedPayload = JSON.parse(request.data);
      request.success({ success: true });
    };
    window.getMac = () => selectedMac;
    window.getApiBase = () => '/api';
    window.getSetting = () => 'synthetic-token';
    window.getString = key => key;
    window.isEmpty = () => false;
    window.isValidMac = value => value === selectedMac;
    window.isValidIPv4 = value => value === '192.0.2.12';
    window.isValidIPv6 = () => false;
    window.showMessage = () => {};
    window.showSpinner = () => {};
    window.hideSpinner = () => {};
    window.showDetailsTabSkeleton = () => {};
    window.hideDetailsTabSkeleton = () => {};
    window.updateApi = () => {};
    window.collectTableData = () => [];
    window.getDevicesList = () => [
      { devMac: 'aa:bb:cc:dd:ee:03' }, { devMac: selectedMac }
    ];
    window.setCache = () => {};
    window.pos = -1;
    window.somethingChanged = false;
    window.mac = selectedMac;
    window.control = window.$('');

    setDeviceData('', () => updateChevrons(window.mac));
    return {
      url: window.savedUrl,
      payloadIP: window.savedPayload.devLastIP,
      callbackMac: window.mac,
      position: window.pos,
      recordDisplay: window.recordDisplay
    };
  });

  expect(result).toEqual({
    url: '/api/device/aa%3Abb%3Acc%3Add%3Aee%3A01',
    payloadIP: '192.0.2.12',
    callbackMac: 'aa:bb:cc:dd:ee:01',
    position: 1,
    recordDisplay: '2 / 2'
  });
});
