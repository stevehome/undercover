"""Accepting the agent's work: a run, a round, a round's review or a claim.

The app creates what the work needs and asks the agent for it by id. Each request
checks that the work is what the app says it is, answers at once and hands the work
to the background.
"""

from typing import Any

from agent import api, backend_http, improver_api, jobs, resumption, rounds
from agent.background_work import BackgroundWork

ACCEPTED = {"accepted": True}
WORKED_RUNS = ("dispatch", "evaluation")


def _refused(reason: str) -> dict[str, Any]:
    return {"refused": reason}


def work_run(run_id: int, background: BackgroundWork) -> dict[str, Any]:
    """Work a dispatch or an evaluation that is running."""
    try:
        run = api.get_run(run_id)
    except backend_http.ApiRefusal as refusal:
        return _refused(refusal.detail)
    if run["kind"] not in WORKED_RUNS or run["status"] != "running":
        return _refused(f"Run {run_id} is not a run that is going")
    background.start("run", jobs.work_run, run_id, run["concurrency"])
    return ACCEPTED


def work_round(round_id: int, background: BackgroundWork) -> dict[str, Any]:
    """Work a round that is open, from its first evaluations."""
    try:
        run_id = improver_api.get_stretch(round_id)
    except backend_http.ApiRefusal as refusal:
        return _refused(refusal.detail)
    background.start("round", jobs.work_stretch, round_id, run_id, None)
    return ACCEPTED


def carry_round_on(
    round_id: int, proposal_id: int, background: BackgroundWork
) -> dict[str, Any]:
    """Carry a round on after a handler's review, which the agent reads from the app."""
    try:
        run_id = improver_api.get_stretch(round_id)
        proposal = improver_api.get_proposal(proposal_id)
    except backend_http.ApiRefusal as refusal:
        return _refused(refusal.detail)
    if proposal["round_id"] != round_id or proposal["status"] == "pending":
        return _refused(f"Proposal {proposal_id} has no review for round {round_id}")
    resume = rounds.decision(
        proposal["status"] == "approved", proposal["rejection_reason"] or ""
    )
    background.start("improver", jobs.work_stretch, round_id, run_id, resume)
    return ACCEPTED


def resume_claim(claim_id: str, background: BackgroundWork) -> dict[str, Any]:
    """Carry on with a claim whose pause has been answered; refused if it hasn't."""
    reason = resumption.refusal(claim_id)
    if reason is not None:
        return _refused(reason)
    background.start(f"claim {claim_id}", resumption.work, claim_id)
    return ACCEPTED


def health() -> dict[str, bool]:
    """Say the agent is running, once it is ready."""
    return {"healthy": True}
