"""Diffs: two texts as lines marked added, removed or unchanged, from `difflib`."""

import difflib

KINDS = {"+": "added", "-": "removed", " ": "context", "@": "hunk"}


def diff_lines(old: str, new: str) -> list[dict[str, str]]:
    """Return what changed from `old` to `new` as lines with a kind and text."""
    lines = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=3)
    return [
        {"kind": KINDS[line[0]], "text": line if line[0] == "@" else line[1:]}
        for line in list(lines)[2:]
    ]
