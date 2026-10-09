// Test #5 (PRD): Session Info renders without a settings lookup - all 6
// migrated fields display, including devStatus (the one that's never
// actually worked before this PRD), and there's no save/submit control.
const { test, expect } = require('@playwright/test');
const { TEST_MAC, mockSourcesBackend } = require('./fixtures');

test('Session Info displays all 6 migrated fields including devStatus, with no save control', async ({ page }) => {
  await mockSourcesBackend(page);

  await page.goto(`/deviceDetails.php?mac=${encodeURIComponent(TEST_MAC)}`);
  await page.click('#tabSessionInfo');

  await expect(page.locator('#sessionInfo_devPrimaryIPv4')).toHaveText('192.168.1.50');
  await expect(page.locator('#sessionInfo_devPrimaryIPv6')).toHaveText('fe80::1');
  await expect(page.locator('#sessionInfo_devFQDN')).toHaveText('test-device.lan');
  await expect(page.locator('#sessionInfo_devLastConnection')).not.toBeEmpty();
  await expect(page.locator('#sessionInfo_devFirstConnection')).not.toBeEmpty();

  // devStatus: the dead field this PRD fixes - must actually render something,
  // not be silently blank the way it always has been before this change.
  await expect(page.locator('#sessionInfo_devStatus')).not.toBeEmpty();

  await expect(page.locator('#panSessionInfo button[type="submit"]')).toHaveCount(0);
  await expect(page.locator('#panSessionInfo .pa-btn-save, #panSessionInfo #btnSave')).toHaveCount(0);
});
