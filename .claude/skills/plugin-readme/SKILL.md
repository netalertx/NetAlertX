---
name: plugin-readme
description: Write or review a NetAlertX plugin's README.md (server/plugins/<code_name>/README.md). Use this when asked to create, enhance, audit, or clean up a plugin README, or plugin docs generally.
---

# Plugin README Documentation

## Structure

- `## Overview` — prose: what the plugin does and why, 1-3 sentences. Link out to a full guide under `docs/*.md` if one exists for this topic.
- `### Requirements` / `### Prerequisites` (optional) — only when there's a real precondition beyond installing the app (credentials, specific hardware/firmware, host networking, a third-party account).
- `### Usage` — how a user actually engages with the plugin: where to enable it, the overall flow, which non-obvious values they need to go find elsewhere (e.g. "grab your API key from your provider's dashboard"). Not a settings reference table.
- `### Notes` (optional) — caveats, gotchas, limitations, similar/related plugins worth cross-linking.
- `## Other info` (optional) — Version / Author / Maintainer(s) / Release Date. **Never drop this when rewriting a README** - if it's there, carry it forward verbatim even if you're rewriting everything else.

## The core rule: don't re-document settings

Every setting already gets a name and description shown directly in the Settings UI, generated straight from `config.json`. A README that re-lists each setting with its key and default value duplicates that and drifts out of sync the moment `config.json` changes — the UI is the single source of truth for field-level docs, not the README.

Exception: call out a *specific* setting by name, in prose, only when its behavior is genuinely non-obvious - e.g. a setting whose name doesn't match what it actually holds (`_publisher_telegram`'s `HOST` setting is actually the chat ID, `URL` is the bot token), a recommended value or schedule, or an upstream bug tied to a specific value (see `unifi_import`'s `UNFIMP_version`/`UNFIMP_port` note). Don't turn this into a table of every field "just in case" - if you're listing more than one or two settings, ask whether that content belongs in the UI's per-field description instead.

## Verify against the actual code first

Read `config.json` (`unique_prefix`, `plugin_type`, `data_source`, `settings`) and the plugin's script before writing anything - don't guess at mechanism from the plugin's name alone. A README copied from a sibling plugin or left as the unedited `__template/README.md` describes the wrong plugin's behavior.

## Backfilling missing "Other info"

Before concluding a plugin has no attribution to record, grep its script for a credit comment (e.g. `grep -rn "Based on\|Author:" server/plugins/<code_name>/*.py`) - two plugins (`dhcp_servers`, `website_monitor`) had `# Based on the work of https://github.com/leiweibau/Pi.Alert` in the script that nothing in the README reflected. Do **not** use `git log --diff-filter=A` "who first added this file" as an attribution source - `server/plugins/` has at least one bulk restructuring commit, so several unrelated plugins share the same "first added" date/author despite having nothing to do with each other. If you can't verify authorship from an in-source comment or an existing (already-correct) README, leave the section out rather than guess - most first-party/core plugins (`maintenance`, `custom_props`, `db_cleanup`, `set_password`, etc.) simply don't have one, which is the correct, honest state.

## Cross-linking convention

- Link to a top-level docs page: `https://docs.netalertx.com/PAGE_NAME`. Never `/docs/PAGE_NAME.md` or a `github.com/.../tree/main/...` URL - both break once the README is rendered inside the docs site (`docs/gen_plugin_pages.py` generates it at a different path than the repo, so repo-relative and GitHub-tree links don't resolve there).
- Link to *another plugin's* README: `https://docs.netalertx.com/plugins/<code_name>` (matches the page `docs/gen_plugin_pages.py` generates for it). Never a GitHub tree URL.
- If a `docs/*.md` guide is dedicated to (or shared by) this plugin, link both directions - plugin → guide, and guide → plugin. Check the other side actually links back; it's easy to add one direction and forget the other (e.g. `PIHOLE_GUIDE.md` linked to four Pi-hole plugins, none of which linked back, until this was audited).
- If a sibling plugin is easily confused with this one (`unifi_import` vs `unifi_api_import`, `dig_scan` vs `nslookup_scan`, `adguard_export` vs `adguard_import`), say so in one sentence and link it - which one to prefer and why.

## Common defects to check for when auditing existing READMEs

- Template leftovers: grep for `Plugin name`, `<your github handle>`, `Some tip.`, `PREF_RUN` - a sign the README was never actually written. Diff against `server/plugins/__template/README.md` if unsure.
- Content copy-pasted from a sibling plugin without updating the tool/utility name.
- `TBC` or similarly empty content, especially for a prominent feature.
- Duplicate or orphaned sections (e.g. two `### Usage` headings) - usually a merge/edit artifact.
- Sibling non-README files (a provider-specific sub-guide, a translated `README_<LANG>.md`) that aren't linked from the plugin's own `README.md` - `docs/gen_plugin_pages.py` generates a page for every `*.md` in the plugin folder, but only reachable if something links to it.
- A table (or any multi-line block) indented under a bullet as that list item's continuation. GitHub's renderer tolerates loose (2-3 space) indentation; the docs site (`mkdocs`, Python-Markdown) only keeps the block nested inside that list item at a full 4-space indent - anything less and the block falls out as an orphaned, unindented paragraph/table right after the list closes. Separately, and regardless of indent width: a bullet that follows the block *without* a blank line in between merges into it as plain text instead of parsing as a new list item - confirmed this still breaks even at the correct 4-space indent, so fixing the indent alone isn't sufficient. Looks fine in the PR diff on GitHub, breaks only once published. Simplest, most portable fix (works regardless of either rule): de-nest it - end the bullet's text, blank line, then the table/block as top-level (unindented) content, blank line, then resume the list as a fresh block.

## Reference

- Repo-wide plugin catalog with icon/type legend: `docs/PLUGINS_OVERVIEW.md`
- Full plugin authoring reference (settings schema, execution phases, data contract): `docs/PLUGINS_DEV.md` and the `plugin-development` skill.
