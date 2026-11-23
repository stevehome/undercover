"""Starting the agent's work: a dispatch, an evaluation, a round or a handler's review.

The app keeps one piece of work going at a time and does the first part itself: it
stops work that has gone quiet, creates the run, the round or the review in a short
transaction it commits, and then asks the agent to work it by its id. When the agent
didn't take the work, the app undoes what it created. A timeout leaves it going: the
agent may have it.
"""

from collections.abc import Callable
from typing import Any

from backend import (
    agent_service,
    evaluations,
    model_used,
    proposals,
    rounds,
    runs,
)
from backend.errors import Conflict, ServiceUnavailable


def _begin[T](create: Callable[[], T]) -> T:
    """Stop quiet work, refuse while something is going, then create what is asked."""
    runs.stop_quiet_runs()
    if (going := runs.running_work()) is not None:
        raise Conflict(f"{going} is already running")
    try:
        return create()
    except runs.RunAlreadyGoing as error:
        raise Conflict(
            f"{runs.running_work() or 'Something'} is already running"
        ) from error


def _hand_over(ask: Callable[[], None], undo: Callable[[], None]) -> None:
    """Ask the agent; undo what was created when it didn't take the work."""
    try:
        ask()
    except (Conflict, ServiceUnavailable):
        undo()
        raise


def start_dispatch(concurrency: int) -> int:
    """Create a dispatch and ask the agent to work it; return its run's id."""
    run_id = _begin(
        lambda: runs.create_dispatch(concurrency, model_used.for_claim_agent())[
            "run_id"
        ]
    )
    _hand_over(
        lambda: agent_service.work_run(run_id),
        lambda: runs.stop_run(run_id, runs.NOT_TAKEN_REASON),
    )
    return run_id


def start_evaluation(concurrency: int, eval_set: str, tiny: bool) -> int:
    """Create an evaluation on a labelled set and ask the agent to work it."""
    run_id = _begin(
        lambda: evaluations.start_evaluation(
            eval_set, tiny, concurrency, model_used.for_claim_agent()
        )["run_id"]
    )
    _hand_over(
        lambda: agent_service.work_run(run_id),
        lambda: runs.stop_run(run_id, runs.NOT_TAKEN_REASON),
    )
    return run_id


def start_round(handler_id: str) -> int:
    """Create a round and ask the agent to work it; return the round's id."""
    created = _begin(
        lambda: rounds.create_round(handler_id, *model_used.for_improver())
    )
    _hand_over(
        lambda: agent_service.work_round(created["round_id"]),
        lambda: runs.stop_run(created["run_id"], runs.NOT_TAKEN_REASON),
    )
    return created["round_id"]


def decide_proposal(
    proposal_id: int, decision: str, handler_id: str, reason: str
) -> None:
    """Record a handler's review and ask the agent to carry the round on with it."""
    round_before = rounds.get_row(proposals.get_proposal(proposal_id)["round_id"])
    recorded: dict[str, Any] = _begin(
        lambda: proposals.record_decision(
            proposal_id,
            decision == "approve",
            handler_id,
            reason,
            model_used.for_improver(),
        )
    )
    _hand_over(
        lambda: agent_service.carry_round_on(recorded["round_id"], proposal_id),
        lambda: proposals.clear_decision(proposal_id, recorded, round_before),
    )
