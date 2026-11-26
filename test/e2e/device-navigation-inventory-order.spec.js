// Exercise the production navigation functions against a synthetic inventory.
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

async function installSyntheticInventory(page) {
  await page.route('http://inventory.test/**', route => route.fulfill({
    status: 200, contentType: 'text/html', body: '<!doctype html><title>fixture</title>'
  }));
  await page.goto('http://inventory.test/deviceDetails.php?mac=aa%3Abb%3Acc%3Add%3Aee%3A01&tab=events&field=ip');
  const source = fs.readFileSync(path.join(ROOT, 'front/deviceDetails.php'), 'utf8');
  const listHelper = source.match(/^function getDetailsDeviceList\(\)\s*\{[\s\S]*?^\}/m);
  const extractedFunctions = [
    ...(listHelper ? [listHelper[0]] : []),
    functionSource(source, 'performSwitch', 'direction')
  ];
  await page.addScriptTag({ content: extractedFunctions.join('\n') });
  await page.evaluate(() => {
    const devices = [
      { devMac: 'aa:bb:cc:dd:ee:01' },
      { devMac: 'aa:bb:cc:dd:ee:02' },
      { devMac: 'aa:bb:cc:dd:ee:03' }
    ];
    window.CACHE_KEYS = { VISIBLE_MACS: 'visible', DEVICES_ALL: 'all' };
    window.getCache = key => key === 'visible'
      ? 'aa:bb:cc:dd:ee:03,aa:bb:cc:dd:ee:01,aa:bb:cc:dd:ee:02'
      : JSON.stringify(devices);
    window.parseDeviceCache = JSON.parse;
    // Mirrors the existing helper: membership is filtered, but cache order remains.
    window.getDevicesList = () => devices.filter(device =>
      window.getCache('visible').split(',').includes(device.devMac));
    window.getMac = () => new URL(location.href).searchParams.get('mac');
    window.setCache = () => {};
    window.hideSpinner = () => {};
    window.somethingChanged = false;
  });
}

test('details navigation follows displayed inventory order and preserves URL context', async ({ page }) => {
  await installSyntheticInventory(page);
  const visibleMacs = await page.evaluate(() => {
    const effectiveList = typeof getDetailsDeviceList === 'function'
      ? getDetailsDeviceList()
      : getDevicesList();
    return effectiveList.map(device => device.devMac);
  });
  expect(visibleMacs).toEqual([
    'aa:bb:cc:dd:ee:03', 'aa:bb:cc:dd:ee:01', 'aa:bb:cc:dd:ee:02'
  ]);

  await page.evaluate(() => { window.pos = 0; }); // stale position: selected identity is authoritative
  await Promise.all([
    page.waitForURL(url => url.searchParams.get('mac') === 'aa:bb:cc:dd:ee:02'),
    page.evaluate(() => performSwitch('next'))
  ]);
  expect(new URL(page.url()).searchParams.get('tab')).toBe('events');
  expect(new URL(page.url()).searchParams.get('field')).toBe('ip');
});

test('previous/next boundaries and devices outside the visible inventory are inert', async ({ page }) => {
  await installSyntheticInventory(page);
  await page.evaluate(() => { history.replaceState({}, '', '/deviceDetails.php?mac=aa%3Abb%3Acc%3Add%3Aee%3A03'); });
  await page.evaluate(() => performSwitch('prev'));
  expect(new URL(page.url()).searchParams.get('mac')).toBe('aa:bb:cc:dd:ee:03');

  await page.evaluate(() => { history.replaceState({}, '', '/deviceDetails.php?mac=aa%3Abb%3Acc%3Add%3Aee%3A99'); });
  await page.evaluate(() => performSwitch('next'));
  expect(new URL(page.url()).searchParams.get('mac')).toBe('aa:bb:cc:dd:ee:99');
});
