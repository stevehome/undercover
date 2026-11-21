"""Every answer names the files it came from, each with its source."""

from typing import Any, NamedTuple


class Sourced(NamedTuple):
    """A file and the system, owner and review date it names."""

    file: str
    source: dict[str, str]


def answer(payload: Any, *files: Sourced) -> dict[str, Any]:
    """Return an answer with the source of each file it drew from."""
    return {"sources": {f.file: f.source for f in files}, "answer": payload}
