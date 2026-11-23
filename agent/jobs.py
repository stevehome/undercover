"""What background work does besides the work: it is heard, and it fails alone.

While it works it tells the app every minute that it is alive, and when it fails it
stops only its own run, or its round's stretch, by id, with the reason.
"""

from typing import Any

from agent import api, dispatcher, heartbeat, rounds


def work_run(run_id: int, concurrency: int) -> None:
    """Work a dispatch's or an evaluation's claims, `concurrency` at a time."""
    with heartbeat.beating(lambda: api.hear_run(run_id)):
        try:
            dispatcher.run_dispatch(run_id, concurrency)
        except Exception as error:
            api.stop_run(run_id, _why(error))
            raise


def work_stretch(round_id: int, run_id: int, resume: dict[str, Any] | None) -> None:
    """Work a round's stretch; the round's word covers the evaluation it works."""
    with heartbeat.beating(lambda: api.hear_run(run_id)):
        rounds.work_stretch(round_id, run_id, resume)


def _why(error: Exception) -> str:
    return f"The agent's work failed: {type(error).__name__}"
