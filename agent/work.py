"""How a dispatch works one claim: attempts, retries and giving up.

This is plain code, not left to the model: a claim is never decided twice,
a failed claim starts afresh, and it is left for a handler after two failures.
A referred claim is left for a handler too.
A claim that was stopped, not failed, carries on and it is not a new attempt.
A rate limit or a timeout is neither: it is let through for the dispatcher to
wait and try again, as the same attempt.
A claim is not started once its run's round has spent its limit or stopped; it
stays to do, and its evaluation ends stopped.
"""

from decimal import Decimal
from typing import Protocol

from langchain_core.exceptions import ModelRateLimitError, ModelTimeoutError

from agent import api
from agent.api import WAITING_FOR_SIGN_OFF

MAX_ATTEMPTS = 2
BUSY_NOTE = "Being worked by another agent"
NOT_STARTED = "Not started: the round has spent its limit or is stopped"
WAIT_AND_RETRY = (ModelRateLimitError, ModelTimeoutError)


class Decide(Protocol):
    """What works a claim in a run: the claim agent, or a stand-in for it."""

    def __call__(self, claim_id: str, *, run_id: int | None) -> str: ...


def _attempt(
    run_id: int, claim_id: str, decide: Decide, carrying_on: bool
) -> str | None:
    """Try to decide a claim once: None if it is decided, else the error.

    A claim being carried on after a stop is the attempt already counted.
    """
    if not carrying_on:
        api.update_run_claim(run_id, claim_id, "in progress", "")
    try:
        decide(claim_id, run_id=run_id)
    except WAIT_AND_RETRY:
        raise
    except Exception as error:  # noqa: BLE001 - any failure sends the claim back
        if api.get_claim(claim_id)["decision"] is not None:
            return None
        reason = " ".join(str(error).split())
        api.record_step(claim_id, f"The attempt failed: {reason}")
        api.requeue_claim(claim_id)
        return reason
    return None


def _settle(run_id: int, claim_id: str) -> str:
    """Close a decided claim's row in the run with a one-line outcome.

    A referral needs a handler's judgment, so it is left for one.
    """
    claim = api.get_claim(claim_id)
    if claim["decision"] is None:
        api.update_run_claim(run_id, claim_id, "done", BUSY_NOTE)
        return BUSY_NOTE
    match claim["decision"]:
        case "approve":
            note = f"Approved ${Decimal(claim['payout']):,.2f}"
            if claim["status"] == WAITING_FOR_SIGN_OFF:
                note += ", waiting for sign-off"
        case "decline":
            note = "Declined"
        case _:
            note = "Referred"
    status = "left for a handler" if claim["decision"] == "refer" else "done"
    api.update_run_claim(run_id, claim_id, status, note)
    return note


def work_claim(run_id: int, claim_id: str, decide: Decide) -> str:
    """Decide one claim, keeping its row in the run current, and say what happened."""
    row = next(c for c in api.get_run(run_id)["claims"] if c["claim_id"] == claim_id)
    carrying_on = row["status"] == "in progress"
    if not carrying_on and not api.may_start_claim(run_id):
        return NOT_STARTED
    attempts_made = row["attempts"] - carrying_on
    error = row["note"] or ""
    for attempt in range(attempts_made + 1, MAX_ATTEMPTS + 1):
        failure = _attempt(
            run_id, claim_id, decide, carrying_on and attempt == attempts_made + 1
        )
        if failure is None:
            return _settle(run_id, claim_id)
        error = failure
        if attempt < MAX_ATTEMPTS:
            failed = f"Attempt {attempt} failed: {error}"
            api.update_run_claim(run_id, claim_id, "to do", failed)
    note = f"Left for a handler after {MAX_ATTEMPTS} failed attempts: {error}"
    api.update_run_claim(run_id, claim_id, "left for a handler", note)
    return note


def give_up(run_id: int, claim_id: str, error: BaseException) -> str:
    """Leave a claim in progress for the next dispatch, and say why."""
    note = f"Left in progress for the next dispatch: {type(error).__name__}"
    api.update_run_claim(run_id, claim_id, "still in progress", note)
    return note
