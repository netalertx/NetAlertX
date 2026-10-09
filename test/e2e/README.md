# Sources / Session Info characterization tests

Playwright specs for the Sources tab (Plugin View + Field View) and the
Session Info tab. These are characterization tests, not unit tests of
internal functions: each one mocks the relevant GraphQL/REST calls via
`page.route()` with fixed fixture data (no real DB, no seeded scan data)
and asserts on rendered, observable DOM - the same assertions should hold
against a future frontend rewrite, unchanged.

Run against a live NetAlertX instance (defaults to `http://localhost:20211`,
override with `NAX_BASE_URL`):

```
npm install
npx playwright install chromium
npm run test:e2e
```

Scope is deliberately narrow - four specs covering the Sources/Session Info
PRD's acceptance criteria, not a general frontend test suite. Do not add
unrelated specs here without a separate, deliberate decision to broaden this
setup.

**Status as of this implementation pass:** written and manually reviewed for
correctness against the actual frontend code (GraphQL shapes, route URLs,
DOM selectors), but not yet run against a live instance - no running
NetAlertX server was available in the environment these were written in.
Run them against a real devcontainer before considering this PRD's Playwright
work complete.
