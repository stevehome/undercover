"""Waiting for the agent's work in code, never by calling the model again and again.

A handler who starts a dispatch or an evaluation and wants to know how it went has the
Copilot wait for that run: it asks our app every few seconds, through a read a handler
may use, until the run is no longer running, and stops after 15 minutes.
"""

import time
from collections.abc import Callable
from typing import Any

from agent import copilot_api

POLL_SECONDS = 5
GIVE_UP_SECONDS = 15 * 60
NANOS_PER_SECOND = 10**9
SUMMARY_FIELDS = (
    "run_id",
    "kind",
    "status",
    "stopped_reason",
    "started_on",
    "finished_on",
    "model_calls",
    "cost",
    "work_ms",
    "summary",
)


def wait_for_run(
    sign_in: str,
    run_id: int,
    *,
    follow_on: str,
    now: Callable[[], int] = time.monotonic_ns,
    sleep: Callable[[int], None] = time.sleep,
) -> dict[str, Any]:
    """Wait for a run to end; return how it ended, or that it is still going.

    `follow_on` says where on the dashboard to follow the work after we stop waiting.
    """
    started = now()
    while True:
        run = copilot_api.get_run(sign_in, run_id)
        ended = run["status"] != "running"
        if ended or (now() - started) // NANOS_PER_SECOND >= GIVE_UP_SECONDS:
            break
        sleep(POLL_SECONDS)
    seen = {field: run[field] for field in SUMMARY_FIELDS}
    if ended:
        return {"ended": True, **seen}
    minutes = GIVE_UP_SECONDS // 60
    still_going = f"Still going after {minutes} minutes; follow it on {follow_on}."
    return {"ended": False, "message": still_going, **seen}
