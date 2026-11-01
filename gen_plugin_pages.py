"""Generate docs pages for each plugin from its own README.md (and extras).

Runs at `mkdocs build`/`mkdocs serve` time via the `gen-files` plugin
(see mkdocs.yml). Every server/plugins/<name>/README.md becomes a virtual
page at plugins/<name>.md, so the docs site always mirrors the current
README instead of the two drifting out of sync or docs linking out to
GitHub. A plugins/SUMMARY.md is generated alongside them for the
`literate-nav` plugin, which turns it into the "Plugins reference" nav
section referenced from mkdocs.yml (`plugins/`).

Two things beyond the README text itself get carried over, since a plugin
folder can contain more than just README.md:
  - Sibling images (screenshots) are copied to plugins/<slug>/<file>, and
    any reference to them in the README - absolute repo path, `./relative`,
    or bare filename - is rewritten to point at the copied location.
  - Any other *.md file in the same folder (e.g. a provider-specific
    sub-guide) gets its own generated page at plugins/<slug>/<file>.md,
    added to the nav under its own first H1 heading (or the filename if it
    has none).

To exclude a plugin from the generated reference (e.g. a dev scaffold,
not a real plugin), prefix its folder name with double underscores -
see the __template skip below.
"""

import json
import re
from pathlib import Path

import mkdocs_gen_files

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / "server" / "plugins"
GITHUB_BLOB_BASE = "https://github.com/netalertx/NetAlertX/blob/main"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

nav = mkdocs_gen_files.Nav()
index_entries = []


def generated_note(source_rel_to_repo):
    return (
        "!!! note \"Generated page\"\n"
        f"    This page mirrors [`{source_rel_to_repo}`]"
        f"({GITHUB_BLOB_BASE}/{source_rel_to_repo}) and is regenerated on every docs build.\n\n"
    )


for readme_path in sorted(PLUGINS_DIR.glob("*/README.md")):
    plugin_dir = readme_path.parent
    slug = plugin_dir.name

    if slug.startswith("__"):
        continue  # dev scaffolding (e.g. __template), not a real plugin

    config_path = plugin_dir / "config.json"
    display_name = slug
    unique_prefix = None
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            config = {}
        names = config.get("display_name") or []
        for entry in names:
            if entry.get("language_code") == "en_us" and entry.get("string"):
                display_name = entry["string"]
                break
        unique_prefix = config.get("unique_prefix")

    title = f"{display_name} ({unique_prefix})" if unique_prefix else display_name

    doc_path = f"{slug}.md"  # relative to plugins/SUMMARY.md
    full_doc_path = f"plugins/{doc_path}"
    source_rel_to_repo = readme_path.relative_to(REPO_ROOT).as_posix()

    nav[title] = doc_path
    index_entries.append((title, doc_path))

    readme_text = readme_path.read_text(encoding="utf-8")

    # Copy sibling image assets and rewrite whatever form the README uses to
    # reference them (absolute repo path, ./relative, or bare filename) to
    # the copied location - only the README's *text* is otherwise pulled
    # into the site, so a plugin's local screenshots would 404 silently.
    for asset_path in sorted(plugin_dir.iterdir()):
        if asset_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        asset_name = asset_path.name
        with mkdocs_gen_files.open(f"plugins/{slug}/{asset_name}", "wb") as out:
            out.write(asset_path.read_bytes())
        readme_text = re.sub(
            rf'\]\((?:\./|/server/plugins/{re.escape(slug)}/)?{re.escape(asset_name)}\)',
            f']({slug}/{asset_name})',
            readme_text,
        )

    with mkdocs_gen_files.open(full_doc_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(generated_note(source_rel_to_repo))
        f.write(readme_text)

    # Point the theme's "edit this page" button at the real source file
    # instead of the virtual doc path, which doesn't exist in the repo.
    mkdocs_gen_files.set_edit_path(full_doc_path, f"../{source_rel_to_repo}")

    # Any other markdown file alongside the README is a plugin-specific
    # sub-guide (e.g. dhcp_leases/ASUS_ROUTERS.md) - give it its own page
    # too, rather than leaving it undiscoverable outside GitHub.
    for extra_md in sorted(plugin_dir.glob("*.md")):
        if extra_md.name == "README.md":
            continue

        extra_text = extra_md.read_text(encoding="utf-8")
        lines = extra_text.lstrip("\n").split("\n", 1)
        first_line = lines[0]
        if first_line.startswith("# "):
            extra_title = first_line[2:].strip()
            body = lines[1].lstrip("\n") if len(lines) > 1 else ""
        else:
            extra_title = extra_md.stem.replace("_", " ").title()
            body = extra_text

        extra_doc_path = f"{slug}/{extra_md.stem}.md"
        extra_full_doc_path = f"plugins/{extra_doc_path}"
        extra_source_rel = extra_md.relative_to(REPO_ROOT).as_posix()

        nav[extra_title] = extra_doc_path

        with mkdocs_gen_files.open(extra_full_doc_path, "w") as f:
            f.write(f"# {extra_title}\n\n")
            f.write(generated_note(extra_source_rel))
            f.write(body)

        # edit_path is concatenated directly after the fixed `edit_uri: blob/main/docs/`
        # prefix (it is NOT relative to this generated file's own directory), so it
        # always needs exactly one `../` to escape "docs/" regardless of how deeply
        # nested the virtual page itself is - same as the top-level README case above.
        mkdocs_gen_files.set_edit_path(extra_full_doc_path, f"../{extra_source_rel}")

with mkdocs_gen_files.open("plugins/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())

with mkdocs_gen_files.open("plugins/index.md", "w") as index_file:
    index_file.write("# Plugins reference\n\n")
    index_file.write(
        "Generated automatically from each plugin's `README.md`. "
        "See [Plugins](../PLUGINS_OVERVIEW.md) for the type/feature legend.\n\n"
    )
    for title, doc_path in index_entries:
        index_file.write(f"- [{title}]({doc_path})\n")
