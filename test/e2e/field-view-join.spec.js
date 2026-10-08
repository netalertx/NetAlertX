// Test #4 (PRD): Field View's join logic - picks each plugin's value from
// whichever Plugins_Objects column field_views.ip names for it, not a
// hardcoded column role, and status renders as plugin-observation wording.
const { test, expect } = require('@playwright/test');
const { TEST_MAC, mockSourcesBackend } = require('./fixtures');

test('Field View renders Plugin/Value/Status/Last-Changed from the correct column per plugin', async ({ page }) => {
  await mockSourcesBackend(page);

  await page.goto(`/deviceDetails.php?mac=${encodeURIComponent(TEST_MAC)}`);
  await page.click('#tabSources');
  await page.click('#sourcesViewToggle');
  await page.click('#sourcesViewMenu a[data-view="field"]');

  const rows = page.locator('#fieldPane_ip tbody tr');
  await expect(rows).toHaveCount(3);

  // FREEBOX's value comes from objectSecondaryId.
  await expect(rows.filter({ hasText: 'FREEBOX' })).toContainText('fe80::1');
  // ARPSCAN's value comes from watchedValue1 - not objectSecondaryId.
  await expect(rows.filter({ hasText: 'ARPSCAN' })).toContainText('192.168.1.50');
  // SNMPDSC's value comes from watchedValue2 - proves the join isn't
  // hardcoded to either of the other two roles.
  await expect(rows.filter({ hasText: 'SNMPDSC' })).toContainText('fe80::2');

  // missing-in-last-scan renders as plugin-observation wording, not a
  // liveness claim.
  const snmpRow = rows.filter({ hasText: 'SNMPDSC' });
  await expect(snmpRow).toContainText('Not reported last run');
  await expect(snmpRow).not.toContainText('offline');
  await expect(snmpRow).not.toContainText('unreachable');
});
