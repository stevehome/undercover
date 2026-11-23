"""Starting the agent's work: a dispatch, an evaluation, a round or a decision.

Each creates what the work needs through the backend, which refuses a second run
while one is going, and hands the work to the background. It answers at once.
"""

from typing import Any

from agent import (
    api,
    backend_http,
    dispatcher,
    harness,
    improver_api,
    resumption,
    rounds,
    stopwatch,
)
from agent.background_work import BackgroundWork

ACCEPTED = {"accepted": True}


def _refused(refusal: backend_http.ApiRefusal) -> dict[str, Any]:
    return {"refused": refusal.detail}


def _current_model() -> api.ModelUsed:
    """The model, effort and version a run on the current configuration uses."""
    configuration = api.current_configuration()
    settings = harness.model_settings(configuration)
    return api.ModelUsed(
        model=settings.name,
        reasoning_effort=settings.reasoning_effort,
        configuration_version=configuration["version"],
    )


def start_dispatch(concurrency: int, background: BackgroundWork) -> dict[str, Any]:
    """Start a dispatch with N claim agents at once; refused while a run is going."""
    try:
        run_id = api.create_dispatch(concurrency, _current_model())
    except backend_http.ApiRefusal as refusal:
        return _refused(refusal)
    background.start("dispatch", dispatcher.run_dispatch, run_id, concurrency)
    return {**ACCEPTED, "run_id": run_id}


def start_evaluation(
    concurrency: int, eval_set: str, tiny: bool, background: BackgroundWork
) -> dict[str, Any]:
    """Start an evaluation on a labelled set; refused while a run is going."""
    try:
        run_id = api.create_evaluation(concurrency, eval_set, tiny, _current_model())
    except backend_http.ApiRefusal as refusal:
        return _refused(refusal)
    background.start("evaluation", dispatcher.run_dispatch, run_id, concurrency)
    return {**ACCEPTED, "run_id": run_id}


def start_round(handler_id: str, background: BackgroundWork) -> dict[str, Any]:
    """Start an improvement round; refused while a run is going."""
    try:
        created = rounds.new_round(handler_id)
    except backend_http.ApiRefusal as refusal:
        return _refused(refusal)
    background.start(
        "round", rounds.work_stretch, created["round_id"], created["run_id"], None
    )
    return {**ACCEPTED, "round_id": created["round_id"]}


def decide_proposal(
    proposal_id: int,
    decision: str,
    handler_id: str,
    reason: str,
    background: BackgroundWork,
) -> dict[str, Any]:
    """Record a handler's decision, then resume the improver with it."""
    approved = decision == "approve"
    settings = harness.improver_settings()
    watch = stopwatch.Stopwatch(f"Recording the decision on proposal {proposal_id}")
    try:
        recorded = improver_api.record_proposal_decision(
            proposal_id,
            approved,
            handler_id,
            reason,
            (settings.name, settings.reasoning_effort),
        )
    except backend_http.ApiRefusal as refusal:
        return _refused(refusal)
    finally:
        watch.lap("the backend's answer")
        watch.log()
    background.start(
        "improver",
        rounds.work_stretch,
        recorded["round_id"],
        recorded["run_id"],
        rounds.decision(approved, reason),
    )
    return {**ACCEPTED, "proposal_id": proposal_id}


def resume_claim(claim_id: str, background: BackgroundWork) -> dict[str, Any]:
    """Carry on with a claim whose pause has been answered; refused if it hasn't."""
    reason = resumption.refusal(claim_id)
    if reason is not None:
        return {"refused": reason}
    background.start(f"claim {claim_id}", resumption.work, claim_id)
    return ACCEPTED


def health() -> dict[str, bool]:
    """Say the agent is running, once it is ready."""
    return {"healthy": True}
