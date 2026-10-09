#!/usr/bin/env python3
"""
Flag PRs that touch some but not all files in a group of mirrored skill
files (`.gemini/skills/`, `.github/skills/`, `.claude/skills/`) without
touching the others, and - for the groups documented in
`.gemini/skills/skills-index/SKILL.md` as covering identical content -
flag when their bodies have actually drifted apart, not just whether a
change touched one side.

Two independent checks:

1. Presence drift (every group): a PR touched some files in a group but
   not the others. Still only a hint ("did you forget the other file?"),
   not proof either way - a genuinely tool-specific change can legitimately
   touch just one side.
2. Content drift (CONTENT_MATCH_GROUPS only): the groups the skills index
   explicitly documents as "All three cover [the same things]" should have
   byte-identical bodies (frontmatter excluded - `name`/`description` are
   allowed to differ per assistant). `settings`/`settings-management`,
   `mcp-activation`, `project-navigation`, and the three devcontainer-
   management targets are deliberately NOT in this list - the skills index
   documents them as intentionally different in depth/scope, not drifted.

Exit non-zero (but the CI step calling this is non-blocking) when either
check finds something.

    python3 scripts/check_skill_pairs.py origin/main
"""

import subprocess
import sys

# Kept in sync with the tables in .gemini/skills/skills-index/SKILL.md and
# .github/skills/skills-overview/SKILL.md. Most groups are 2 files (Gemini +
# Copilot); a few skills are also mirrored to .claude/skills/ as a 3rd member.
GROUPS = [
    [".gemini/skills/plugin-development/plugin-skill.md", ".github/skills/plugin-run-development/SKILL.md", ".claude/skills/plugin-development/SKILL.md"],
    [".gemini/skills/plugin-readme/plugin-readme-skill.md", ".github/skills/plugin-readme/SKILL.md", ".claude/skills/plugin-readme/SKILL.md"],
    [".gemini/skills/testing-workflow/SKILL.md", ".github/skills/testing-workflow/SKILL.md", ".claude/skills/testing-workflow/SKILL.md"],
    [".gemini/skills/pr-analysis/SKILL.md", ".github/skills/pr-analysis/SKILL.md", ".claude/skills/pr-analysis/SKILL.md"],
    [".gemini/skills/scan-pipeline/SKILL.md", ".github/skills/scan-pipeline/SKILL.md", ".claude/skills/scan-pipeline/SKILL.md"],
    [".gemini/skills/database-patterns/SKILL.md", ".github/skills/database-patterns/SKILL.md", ".claude/skills/database-patterns/SKILL.md"],
    [".gemini/skills/prd-writing/SKILL.md", ".github/skills/prd-writing/SKILL.md", ".claude/skills/prd-writing/SKILL.md"],
    [".gemini/skills/ux-design-patterns/SKILL.md", ".github/skills/ux-design-patterns/SKILL.md", ".claude/skills/ux-design-patterns/SKILL.md"],
    [".gemini/skills/skill-hygiene/SKILL.md", ".github/skills/skill-hygiene/SKILL.md", ".claude/skills/skill-hygiene/SKILL.md"],
    [".gemini/skills/plugin-review/SKILL.md", ".github/skills/plugin-review/SKILL.md", ".claude/skills/plugin-review/SKILL.md"],
    [".gemini/skills/install-scripts/SKILL.md", ".github/skills/install-scripts/SKILL.md", ".claude/skills/install-scripts/SKILL.md"],
    [".gemini/skills/settings/SKILL.md", ".github/skills/settings-management/SKILL.md"],
    [".gemini/skills/mcp-activation/SKILL.md", ".github/skills/mcp-activation/SKILL.md"],
    [".gemini/skills/project-navigation/SKILL.md", ".github/skills/project-navigation/SKILL.md"],
    [".gemini/skills/logging-standards/SKILL.md", ".github/skills/logging-standards/SKILL.md"],
    [".gemini/skills/devcontainer-management/SKILL.md", ".github/skills/devcontainer-services/SKILL.md"],
    [".gemini/skills/devcontainer-management/SKILL.md", ".github/skills/devcontainer-setup/SKILL.md"],
    [".gemini/skills/devcontainer-management/SKILL.md", ".github/skills/devcontainer-configs/SKILL.md"],
]

# Subset of GROUPS (by first-member path) the skills index documents as
# covering identical content across every member - everything else in
# GROUPS is documented there as intentionally different in depth/scope
# (settings, mcp-activation, project-navigation) or intentionally partial
# (the three devcontainer-management targets, each covering only part of
# the Gemini file).
CONTENT_MATCH_GROUP_KEYS = {
    ".gemini/skills/plugin-development/plugin-skill.md",
    ".gemini/skills/plugin-readme/plugin-readme-skill.md",
    ".gemini/skills/testing-workflow/SKILL.md",
    ".gemini/skills/pr-analysis/SKILL.md",
    ".gemini/skills/scan-pipeline/SKILL.md",
    ".gemini/skills/database-patterns/SKILL.md",
    ".gemini/skills/prd-writing/SKILL.md",
    ".gemini/skills/ux-design-patterns/SKILL.md",
    ".gemini/skills/skill-hygiene/SKILL.md",
    ".gemini/skills/plugin-review/SKILL.md",
    ".gemini/skills/install-scripts/SKILL.md",
    ".gemini/skills/logging-standards/SKILL.md",
}


def changed_files(base_ref):
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        capture_output=True, text=True, check=True,
    )
    return set(result.stdout.splitlines())


def strip_frontmatter(text):
    """Drop a leading YAML frontmatter block (--- ... ---) so name/
    description, which are allowed to differ per assistant, don't count as
    content drift. Returns the stripped-and-trimmed body, or the original
    text trimmed if there's no frontmatter block."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def read_body(path):
    try:
        with open(path, encoding="utf-8") as f:
            return strip_frontmatter(f.read())
    except FileNotFoundError:
        return None


def check_presence_drift(changed):
    problems = []
    for group in GROUPS:
        touched = [path for path in group if path in changed]
        untouched = [path for path in group if path not in changed]
        if touched and untouched:
            problems.append(
                f"- touched {', '.join(touched)} but not {', '.join(untouched)}."
            )
    return problems


def check_content_drift():
    problems = []
    for group in GROUPS:
        if group[0] not in CONTENT_MATCH_GROUP_KEYS:
            continue
        bodies = {path: read_body(path) for path in group}

        missing = [path for path, body in bodies.items() if body is None]
        if missing:
            for path in missing:
                problems.append(f"- {path} is missing (part of a content-match group).")
            continue

        reference_path, reference_body = group[0], bodies[group[0]]
        for path, body in bodies.items():
            if path == reference_path:
                continue
            if body != reference_body:
                problems.append(
                    f"- {path} and {reference_path} are documented as covering "
                    f"identical content but their bodies differ."
                )
    return problems


def main():
    if len(sys.argv) != 2:
        print("usage: check_skill_pairs.py <base-ref>", file=sys.stderr)
        return 2

    changed = changed_files(sys.argv[1])
    presence_problems = check_presence_drift(changed)
    content_problems = check_content_drift()

    if presence_problems:
        print("Possible skill-group drift (only some mirrored files were touched):")
        print("\n".join(presence_problems))
        print("\nIf the change is genuinely tool-specific, ignore this. "
              "Otherwise update the other file(s) too - see .gemini/skills/skills-index/SKILL.md.")

    if content_problems:
        if presence_problems:
            print()
        print("Skill-pair content drift (bodies documented as identical, but aren't):")
        print("\n".join(content_problems))
        print("\nDiff the files directly to see what changed - "
              "see .gemini/skills/skills-index/SKILL.md for which groups this applies to.")

    if presence_problems or content_problems:
        return 1

    print("No skill-group drift detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
