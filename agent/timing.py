"""How long the agent works on a claim, recorded as stretches of work.

A stretch ends when the claim pauses for a sign-off, so a wait for a handler
is never counted.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from agent import api


def _now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def segment(claim_id: str, run_id: int | None) -> Iterator[None]:
    """Record the work inside the block as one stretch, even if it fails."""
    started_on = _now()
    try:
        yield
    finally:
        api.record_work_segment(claim_id, run_id, started_on, _now())
