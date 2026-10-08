// Test #8 (PRD): ?tab=<plugin_prefix> (existing deep-link) and ?field=<key>
// (new) must not interfere with each other's resolution. Note: the
// top-level Sources tab itself isn't auto-activated by either param today
// (initializeTabs() on the device-details page only reads cache, not the
// URL) - that's pre-existing behavior, unchanged by this PRD, so both tests
// click the Sources tab explicitly before asserting, matching reality.
const { test, expect } = require('@playwright/test');
const { TEST_MAC, mockSourcesBackend } = require('./fixtures');

test('?tab=<plugin> deep-link resolves to Plugin View with that plugin active', async ({ page }) => {
  await mockSourcesBackend(page);

  await page.goto(`/deviceDetails.php?mac=${encodeURIComponent(TEST_MAC)}&tab=FREEBOX`);
  await page.click('#tabSources');

  await expect(page.locator('#sourcesPluginView')).toBeVisible();
  await expect(page.locator('#sourcesFieldView')).toBeHidden();
  await expect(page.locator('#sourcesViewToggle')).toHaveAttribute('data-view', 'plugin');
  await expect(page.locator('a#FREEBOX_id')).toHaveClass(/active/);
});

test('?field=<key> deep-link resolves to Field View with that field active', async ({ page }) => {
  await mockSourcesBackend(page);

  await page.goto(`/deviceDetails.php?mac=${encodeURIComponent(TEST_MAC)}&field=ip`);
  await page.click('#tabSources');

  await expect(page.locator('#sourcesFieldView')).toBeVisible();
  await expect(page.locator('#sourcesPluginView')).toBeHidden();
  await expect(page.locator('#sourcesViewToggle')).toHaveAttribute('data-view', 'field');
  await expect(page.locator('#fieldPane_ip')).toHaveClass(/active/);
});
