---
name: skills-index
description: Index of all available skills across Gemini CLI (.gemini/skills/), GitHub Copilot (.github/skills/), and Claude Code (.claude/skills/). Load this to find the right skill for a task, or to locate the counterpart skill in another assistant's tree.
---

# Skills Index — Cross-Reference

Three AI assistants are configured for this project, each with their own skill directory:

- **Gemini CLI** → `.gemini/skills/`
- **GitHub Copilot** → `.github/skills/`
- **Claude Code** → `.claude/skills/` (mirrors most, not all, of the shared skills below — see the table's Claude Skill column for which)

Skills with the same purpose exist in more than one, sometimes under different names and with different depth. This index maps them so you can find the richer version when needed. A CI check (`scripts/check_skill_pairs.py`, run as `check-skill-pairs` in `.github/workflows/code-checks.yml`) flags PRs that touch some but not all files in a mirrored group - non-blocking, since some divergence is intentional.

---

## Shared Skills (exist in more than one tree)

| Topic | Gemini Skill | Copilot Skill | Claude Skill | Notes |
|-------|-------------|--------------|--------------|-------|
| Testing | `testing-workflow` | `testing-workflow` | `testing-workflow` | All three cover the full-suite-by-default rule, PYTHONPATH, auth/token retrieval, and the `sys.modules` stubbing pitfall |
| Settings & config | `settings` | `settings-management` | — | Gemini version is more comprehensive (22-point guide + PR checklist); Copilot version covers `ccd()` and `get_setting_value()` usage |
| MCP activation | `mcp-activation` | `mcp-activation` | — | Gemini version covers Gemini CLI session restart; Copilot version covers VS Code window reload |
| Project navigation | `project-navigation` | `project-navigation` | — | Copilot version has full path tables and env vars; Gemini version is a brief reference |
| Plugin dev | `plugin-development` | `plugin-run-development` | `plugin-development` | All three cover data contract, phases, formats, the `RUN_TIMEOUT` kill-timer gotcha (`timeoutMultiplier`/`per_item_timeout()`), and a pre-PR pointer to the Conventions Checklist in `docs/PLUGINS_DEV.md` |
| Plugin README docs | `plugin-readme` | `plugin-readme` | `plugin-readme` | All three cover README structure, the "don't re-document settings" rule, the `docs.netalertx.com` cross-linking convention, and common defects (template leftovers, copy-paste errors) found during a full-repo audit |
| Devcontainer | `devcontainer-management` | `devcontainer-services` + `devcontainer-setup` + `devcontainer-configs` | — | Gemini combines into one (uses `docker exec`); Copilot splits into 3 focused skills. `devcontainer-configs` also covers Dockerfile generation (root `Dockerfile` → `generate-dockerfile.sh` → `.devcontainer/Dockerfile`, source files not present at build time) - mined from real review comments on PR #1184/#1230. |
| Install scripts | `install-scripts` | `install-scripts` | `install-scripts` | `install/*` conventions mined from real review comments (#1214/#1230/#1235): uninstall must only remove NetAlertX's own files, never system packages; `check-*.sh` scripts intentionally differ on fail-fast vs. warning-only; `/back` is legacy, not the active code path. |
| PR review | `pr-analysis` | `pr-analysis` | `pr-analysis` | How to classify and respond to PR comments; pre-flight skill loading checklist; the standing rule that a repeated review comment becomes a skill update (sourced from jokob's own real PR comments, #1739/#1744); a readability-over-cleverness code-style note from the same source. |
| Logging | `logging-standards` | `logging-standards` | — | `mylog` levels, message format, what not to log; `app.log` as a shared untagged sink across processes; the `print()`/`BrokenPipeError` guard in `file_print()` |
| Incident debugging | `incident-debugging` | `incident-debugging` | — | Diagnosing a recurring crash with no direct evidence: get a traceback via the cheapest reliable mechanism before theorizing from log correlation; prefer a plain try/except over a global hook for crash capture; verify which process produced a log line before trusting it; diagnostic writes must be synchronous and not purgeable through routine log-clearing |
| Scan pipeline internals | `scan-pipeline` | `scan-pipeline` | `scan-pipeline` | `process_scan()` call order and why it's load-bearing, `CurrentScan`/`Events`/`Sessions`/`DevicesView` relationships, how a session actually closes (no `close_session()` exists), and the `FIELD_SPECS` field-write authority mechanism. Complements `database-patterns` (Devices write-path/`*Source` attribution) rather than duplicating it. |
| Database patterns | `database-patterns` | `database-patterns` | `database-patterns` | Devices table write-path inventory, the `FIELD_SOURCE_MAP`/`*Source` attribution system in `server/db/authoritative_handler.py`, SQLite trigger vs. Python-hook tradeoffs, and event-sourced vs. snapshot audit logging. |
| PRD writing | `prd-writing` | `prd-writing` | `prd-writing` | Methodology for writing a design doc: challenge the idea, verify every claim against actual code, trace every downstream consumer of a new mechanism, evaluate performance impact against the real schema/indexes, record rejected alternatives and open-issue decisions explicitly, final-check pass before done. |
| UX/frontend design | `ux-design-patterns` | `ux-design-patterns` | `ux-design-patterns` | Don't invent new UX behavior/visual patterns unless a PRD calls for it - search `front/` for an existing pattern first and reuse it. Priority order for design tradeoffs when several options are reasonable: existing behavior > intuitiveness > information density > usability > utility > uniqueness > industry practices > generic UI. |
| Skill hygiene | `skill-hygiene` | `skill-hygiene` | `skill-hygiene` | Read before writing/editing any SKILL.md, or any research/audit doc in `.gemini/internal-docs/research/`. Two standing rules: state current behavior only (no "Correction:", no "as of <date>", no "caught in review" narration - that trail belongs in PRDs), and prefer plain, short wording. Includes the grep sweep to run before calling a doc clean. |
| Plugin review | `plugin-review` | `plugin-review` | `plugin-review` | Reviewer-facing complement to Plugin dev above: no raw SQL in a plugin script - use an existing/new `server/models/*.py` method, not GraphQL (which no plugin reaches). Named exception list for 5 pre-existing core/infra plugins with legitimate direct DB access, a collation-checking step, and a worked example from a real PR (#1788, DOCKERDISC). |

---

## Copilot-Only Skills

No Gemini equivalent yet:

| Copilot Skill | Purpose |
|--------------|---------|
| `api-development` | Creating REST API endpoints |
| `authentication` | API tokens and 401/403 debugging |
| `code-standards` | Coding conventions and style rules |
| `database-reset` | Wipe and regenerate the database and config |
| `docker-build` | Build Docker images for testing or production |
| `docker-prune` | Clean unused Docker resources (destructive — requires confirmation) |
| `sample-data` | Load synthetic device data into the devcontainer |

---

## Gemini-Only Skills

No Copilot equivalent yet:

| Gemini Skill | Purpose |
|-------------|---------|
| `initiative-start` | Research methodology and structured approach for new tasks |

---

## Adding a New Skill

When adding a skill, create it in **both** directories to keep both AI systems current:

- `.gemini/skills/<name>/SKILL.md` — auto-discovered by Gemini CLI via YAML frontmatter
- `.github/skills/<name>/SKILL.md` — add an entry to the skills table in `.github/copilot-instructions.md`

Keep the body content identical between both files. Only the frontmatter `name`/`description` may differ slightly to match each system's discovery heuristics.

If the skill is high-value enough to also mirror to Claude Code, add `.claude/skills/<name>/SKILL.md` too, and add the group to `GROUPS` in `scripts/check_skill_pairs.py` so drift gets flagged. Claude Code has no `activate_skill()`/`testFailure`/`runTests`/`report_progress` equivalents - adapt any such tool references to plain `Bash` commands instead of copying them verbatim.
