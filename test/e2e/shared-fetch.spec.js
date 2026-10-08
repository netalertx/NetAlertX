// Test #6 (PRD): Known IPs (Session Info) and Field View read the same
// pluginsObjects data via exactly one fetch - the data assertion alone
// wouldn't catch two independently-issued calls that happen to agree, so
// this also asserts the call count.
const { test, expect } = require('@playwright/test');
const { TEST_MAC, mockSourcesBackend } = require('./fixtures');

test('Known IPs and Field View show consistent filtered data via one shared fetch', async ({ page }) => {
  const mocks = await mockSourcesBackend(page);

  await page.goto(`/deviceDetails.php?mac=${encodeURIComponent(TEST_MAC)}`);

  // Open Session Info first.
  await page.click('#tabSessionInfo');
  await expect(page.locator('#sessionInfo_knownIps')).toContainText('fe80::1');
  await expect(page.locator('#sessionInfo_knownIps')).toContainText('192.168.1.50');
  // SNMPDSC's fe80::2 is missing-in-last-scan - excluded from Known IPs.
  await expect(page.locator('#sessionInfo_knownIps')).not.toContainText('fe80::2');

  // Then open Sources -> Field View, which shows the full, unfiltered set.
  await page.click('#tabSources');
  await page.click('#sourcesViewToggle');
  await page.click('#sourcesViewMenu a[data-view="field"]');
  const rows = page.locator('#fieldPane_ip tbody tr');
  await expect(rows).toHaveCount(3); // includes the missing-in-last-scan row

  // The actual proof of the shared-fetch mechanism: exactly one network
  // call for pluginsObjects across both views, not one per view.
  expect(mocks.getPluginsObjectsCallCount()).toBe(1);
});
