"""How long work may go unheard from before the app counts it as gone quiet."""

from backend import db

QUIET_SECONDS = 300


def cutoff() -> str:
    """The time before which a last word means the work has gone quiet."""
    return db.now(-QUIET_SECONDS)
