---
name: netalertx-ux-design-patterns
description: Read before adding or changing any front/ UI element - a control, layout, button, or interaction pattern. Covers the don't-invent-new-UX-without-a-PRD rule and the priority order for design tradeoffs (existing behavior > intuitiveness > information density > usability > utility > uniqueness > industry practices > generic UI).
---

# UX / Frontend Design Patterns

## Core principle: reuse before inventing

Don't introduce new UX behavior or visual patterns unless a PRD explicitly calls for it. Before building any new UI element, search the existing frontend for a pattern that already solves this exact need, and reuse its markup/CSS/behavior instead of inventing a new one.

Real, recent example: a presence-page Prev/Next pager was first built with custom `<button class="btn btn-xs">` elements floated in a `.box-header`. The DataTables pagination pattern (`dataTables_wrapper` / `dataTables_paginate` / `ul.pagination` / `li.paginate_button.previous|next`) already existed elsewhere in the app and does the exact same job. The custom version looked visually broken in the actual UI and had to be reimplemented using the existing pattern once that was caught in manual testing - reusing it also picked up dark-mode theming (`front/css/dark-patch.css`'s `.pagination li > a` / `.disabled` rules) for free, which the hand-rolled version didn't have. Grep first: e.g. `grep -rn "pagination\|paginate_button" front/` before adding a "previous/next" control of your own; the same applies to modals, filter inputs, badges, tooltips, tables - anything that already has an established shape somewhere in `front/`.

A second real example: a new device-details tab's status display was hand-written as `${icon} ${label}` plain text, and its field-group markup was approximated from memory (`<div class="form-group">` / plain `<div class="col-sm-8">`) instead of read from the actual existing tab it was meant to match. Both were wrong in ways that only showed up once rendered: the real status chip everywhere else in the app (`devices-table.js`, `network-tabs.js`, `network-api.js`) is `<span class="badge ${cssClass}">${iconHtml} ${label}</span>` via the shared `getStatusBadgeParts()`, not bare text; the real field-group markup needs `col-xs-12` on both the `.form-group` and its value `<div>` (plus `.input-group` on the value div), which a plain `grep` for the class names would have shown immediately. Approximating a reference pattern "from memory" instead of reading its actual current markup is the same mistake as not searching at all - read the real template/function that produces the reference UI, don't reconstruct it from a general impression of what it probably looks like.

A third real example, and the one to remember when the new thing isn't markup but behavior: Field View's per-field tables were first built as raw `<table><tbody>` HTML-string concatenation, when `pluginsCore.php`'s own `buildDT()` - a few hundred lines away, same feature area - already builds near-identical plugin-data tables: same DataTables paging/searching/ordering/lengthMenu options, same `createdCell` + `getFormControl()` cell-rendering approach. The fix was extracting the shared options into `getStandardDataTableOptions()` (`front/js/plugin_column_render.js`) and reusing the same cell-rendering pattern, rather than two parallel table implementations answering the same "render a plugin-sourced table" need. Duplication risk isn't only in markup/CSS - a JS initialization config or rendering callback can be just as duplicated. Before writing a new `.DataTable({...})` call (or any other substantial JS behavior-config object), grep for existing instances of it in the same subsystem first: `grep -rn '\.DataTable(' front/`.

## Loading skeletons and spinnerTarget

Two non-obvious mechanisms govern how a per-tab loading skeleton behaves, and skipping either produces a skeleton that visually escapes its own tab or gets stuck showing forever.

**Positioning:** `resolveSpinnerTarget()` (`front/js/common.js`) looks for `.spinnerTarget` among the active tab-pane's *direct children only* (`activePane.children(".spinnerTarget:visible")`), falling back to the pane itself if none is found. A skeleton needs its own `#panX` id added to `app.css`'s positioning-anchor rule (`#panDetails, #panSessions, #panPresence, #panEvents, #appEvents, #panSessionInfo { position: relative; }`) and must be a direct child of that pane - no wrapper `<div>` in between. Introducing an extra wrapper div (even just to group the skeleton with its content) breaks the direct-child lookup and the pane's own `position: relative`, and the skeleton escapes to overlay the whole page instead of staying inside its tab. Match the existing pattern exactly: `front/deviceDetailsPresence.php`'s `<?php require '.../skel_device_details_tab_presence.php'; ?>` as the very first line, no wrapper, `#panPresence` already in the anchor list.

**Lifecycle:** a per-tab polling updater (`setTimeout(updater, 200)`) that shows a skeleton while data loads and hides it once rendered needs to track *what it's waiting for*, not just whether it has ever rendered once. Track the mac (or whatever identity the content depends on) and re-render when it changes - `currentMac !== lastMac`, not just a one-time boolean flag - or switching to a different device while the tab stays active leaves stale data on screen with no re-render. Use `.finally(hideSkeleton)` on the render promise, not `.then(hideSkeleton)` - if the render throws or its fetch rejects, `.then()` never runs and the skeleton is stuck visible forever; `.finally()` always runs regardless of outcome. The render call itself must also sit inside a `try`/`catch` (or be deferred into an async callback, as below) - the updater's own `setTimeout(updater, 200)` call is what keeps the polling loop alive, and if it sits *after* an inline render call that throws synchronously, the throw skips it and the loop dies permanently, leaving the skeleton stuck with no further retries ever.

**Show/hide symmetry:** `showSpinner()`/`hideSpinner()` (`front/js/common.js`) are a pair and must resolve their target the same way. `showSpinner()` calls `resolveSpinnerTarget()`; `hideSpinner()` must too, not an independent lookup (e.g. grabbing `$(".spinnerTarget").last()` in raw document order) - two different targeting strategies on the two halves of one show/hide pair means the one feature whose tab happens to sit earliest in the page's markup gets the wrong element locked in when the overlay animates closed. If you add a new global or shared show/hide pair, check that both halves call the identical resolver.

**Readiness gating:** a render function invoked from a per-tab polling updater that issues its own network call (GraphQL/REST) must be gated the same way an existing equivalent is - e.g. wrapped in `callAfterAppInitialized()` (`front/js/app-init.js`), which waits for both `isAppInitialized()` and the GraphQL server to be confirmed running before calling back. A render path added without this gate can fire its request at the earliest possible point in the page lifecycle (most likely when its tab loads as the *default* tab on page load, before the server is confirmed up) and fail. If the underlying request is wrapped in a cache keyed by id (e.g. a per-mac promise cache) that caches unconditionally, that one early failure poisons the cache entry permanently - nothing will ever retry it, even once the server comes up moments later. Any such cache must evict its own entry on rejection so a later poll tick gets a fresh attempt.

## Fetch once, filter client-side

When a page needs two or more related views over the same underlying data (e.g. a "currently valid" list and a "stale/historical" list derived from the same rows), issue one request and split the result client-side rather than issuing a second request with a different filter. The data doesn't change between the two views, so a second round-trip only adds latency and server load for no new information. Example: Session Info's "Known IPs" and "IP History" chip lists (`front/deviceDetailsSessionInfo.php`) both come from one `getSourcesFieldData()` call - the response is partitioned into the two lists by `entry.status` in JS, not fetched twice with two different status filters. This is also why `getSourcesFieldData()`/`getFieldViewDefinitions()` are themselves cached per-mac (`front/deviceDetails.php`) - so Field View and Session Info, which need the same underlying rows for different purposes, share one fetch instead of each issuing its own.

## Don't omit information to simplify a view

A UI must not be made worse by omitting information - if data exists and is relevant, default to showing it (with a status/staleness indicator if needed) rather than hiding it outright to make a view look cleaner. Example: Session Info's "Known IPs" chip list originally filtered out any plugin entry with `status === 'missing-in-last-scan'`, which produced a confusing "sometimes shows No data" bug even when a plugin had reported the IP recently - the fix was a separate "IP History" list for those entries (mirroring Field View's own "Not Reported" status badge for the same status, rather than hiding it), not filtering them out of existence. Reserve actual omission for genuinely irrelevant data (e.g. a field the user has no permission to see), not for data that's merely uncertain, pending, or outdated.

## Priority order for design decisions

When several options are all locally reasonable, resolve the choice in this order - highest wins on conflict:

1. **Existing behavior** - what does this codebase already do for the same or a similar need? Copy it.
2. **Intuitiveness** - will a user already familiar with the rest of the app understand this without being told?
3. **Information density** - does it show what's needed without wasting space or hiding what matters?
4. **Usability** - is it easy and low-friction to actually use (reachability, click count, error tolerance)?
5. **Utility** - does it solve the real problem, not just resemble a solution?
6. **Uniqueness** - is this the app's own distinct answer, used only where nothing generic fits well?
7. **Industry practices** - conventions users bring in from other apps.
8. **Generic UI** - a default/framework-provided look, used only when nothing above applies.

This list exists to end debates quickly, not to be argued from the bottom up. The reason it's written down is that #1 is exactly the step that gets skipped under time pressure - checking it first is meant to be fast, not a detour.

## Practical checklist before building a new UI element

1. Grep `front/js/`, `front/css/`, `front/php/` for an existing implementation of the same interaction - a table, a pager, a filter box, a modal, a badge, a status indicator.
2. If found, reuse its markup and CSS classes directly rather than writing new ones - matching classes inherit theming (dark mode, responsive breakpoints) a new hand-rolled version won't have.
3. If nothing fits, check whether the PRD driving this change actually calls for new UX. If it doesn't, that's a signal to look harder for an existing pattern, not license to invent one.
4. If a new pattern is genuinely warranted and the PRD says so, design it using the priority order above, and record the choice and why existing patterns didn't fit in the PRD - the next change will hit the same fork and shouldn't have to re-derive the answer.
5. Verify visually in a real browser/devcontainer before calling it done. A change that "should work" per the markup isn't confirmed until it's actually rendered - matches the project's general "test the golden path in a browser" rule for frontend changes.
