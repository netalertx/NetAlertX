"""
Repo-wide check: a module-level constant assigned a bare literal, whose own
comment claims it matches/mirrors another constant elsewhere, must actually
be derived from that constant (an import + a reference), not a second
hand-copied literal with nothing enforcing the claim.

This is exactly how server/__main__.py's STARTUP_RETRY_ATTEMPTS = 3 drifted
from server/db/retry.py's MAX_ATTEMPTS: the comment said "matching db/retry.py's
own MAX_ATTEMPTS", but nothing but that comment kept them equal - a future
change to one would have silently broken the claim in the other. Fixed by
importing MAX_ATTEMPTS and assigning STARTUP_RETRY_ATTEMPTS = MAX_ATTEMPTS
directly, so the relationship is enforced by the language, not a promise.

    pytest test/server/test_constant_sync_comments.py -v
"""

import ast
import glob
import os
import re

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_SERVER_DIR = os.path.join(_ROOT, 'server')

# Phrases that assert an unenforced relationship to another value. Deliberately
# narrow and high-precision - this only fires where someone already wrote down
# "this should equal that", not on every coincidentally-matching number.
_SYNC_PHRASE_RE = re.compile(
    r'\b(matching|mirrors?|mirrored|same as|must match|keep[s]? in sync|kept in sync)\b',
    re.IGNORECASE,
)

# A sync-phrase alone isn't enough - "same as above" (a vague, same-file,
# non-identifying reference) is a real false positive this check hit in
# practice (server/initialise.py's conf.mySettingsSQLsafe reset comment).
# Require the comment to also name a specific CONSTANT_STYLE identifier -
# that's what distinguishes "this equals a named thing elsewhere" (the real
# bug shape) from "this does the same kind of thing as the line above".
# Requires an underscore, not just 3+ caps letters - this codebase's real
# constants are always UPPER_SNAKE_CASE (MAX_ATTEMPTS, RUN_TIMEOUT); a bare
# acronym like "SQL" or "API" in prose matched a looser version of this
# regex and was a second real false positive caught while writing this.
_CONSTANT_NAME_RE = re.compile(r'\b[A-Z][A-Z0-9]*_[A-Z0-9_]*\b')


def _server_py_files():
    return glob.glob(os.path.join(_SERVER_DIR, '**', '*.py'), recursive=True)


def _is_bare_literal(value_node):
    """True if value_node is a literal (or a tuple/list of literals) rather
    than a reference to another name - e.g. `3` or `(1, 2)`, not `OTHER_CONST`
    or `other_module.OTHER_CONST`. A bare literal with a "matches X" comment
    is the unenforced-duplication shape; a direct reference already enforces
    the relationship by construction and is exactly the fix for it."""
    if isinstance(value_node, ast.Constant):
        return True
    if isinstance(value_node, (ast.Tuple, ast.List)):
        return all(_is_bare_literal(elt) for elt in value_node.elts)
    return False


def _unenforced_sync_assignments(py_file):
    with open(py_file, encoding='utf-8') as f:
        source = f.read()
    lines = source.splitlines()

    try:
        tree = ast.parse(source, filename=py_file)
    except SyntaxError:
        return []  # a real syntax error is caught elsewhere (py_compile in CI)

    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not _is_bare_literal(node.value):
            continue

        line_text = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ''
        _, _, comment = line_text.partition('#')
        if comment and _SYNC_PHRASE_RE.search(comment) and _CONSTANT_NAME_RE.search(comment):
            issues.append(
                f"{os.path.basename(py_file)}:{node.lineno}: "
                f"unenforced sync claim in its own comment: {line_text.strip()!r}"
            )

    return issues


@pytest.mark.parametrize('py_file', _server_py_files(), ids=lambda p: os.path.relpath(p, _SERVER_DIR))
def test_no_unenforced_constant_sync_comments(py_file):
    issues = _unenforced_sync_assignments(py_file)
    assert not issues, (
        "Found a constant assigned a bare literal whose own comment claims it "
        "matches/mirrors another value, with nothing but the comment enforcing "
        "that claim - import and reference the other constant directly instead "
        "(e.g. `STARTUP_RETRY_ATTEMPTS = MAX_ATTEMPTS`, not a second literal `3` "
        "with a comment saying it matches MAX_ATTEMPTS). A future change to one "
        "side would silently break the other without this:\n" + "\n".join(issues)
    )
