// Playwright config scoped to the Sources (Plugin View + Field View) and
// Session Info characterization tests only - see test/e2e/README.md.
// baseURL points at a running NetAlertX instance (devcontainer nginx by
// default); every spec mocks its own GraphQL/REST calls via page.route(),
// so no real DB or seeded scan data is required.
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: 'test/e2e',
  timeout: 30000,
  use: {
    baseURL: process.env.NAX_BASE_URL || 'http://localhost:20211',
  },
});
