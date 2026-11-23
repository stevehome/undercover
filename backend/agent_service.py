"""Asking the agent to work what the app has created: a run, a round or a review.

The agent is an AgentCore app. A payload names an operation and its inputs, and goes
to the agent on a host of its own (`UNDERCOVER_AGENT`) or, when
`UNDERCOVER_AGENT_RUNTIME` names a runtime's ARN, to that runtime. Each answer says
what happened in one of four ways: taken, refused (a Conflict with the agent's
reason), not taken (ServiceUnavailable) or unknown (Unconfirmed: nothing changes and
the handler is told to reload).
"""

import logging
import os
from typing import Any

from backend import agent_laptop, agent_runtime, stopwatch
from backend.errors import Conflict, ServiceUnavailable, Unconfirmed

logger = logging.getLogger(__name__)


def _ask(operation: str, **inputs: Any) -> dict[str, Any]:
    """Send one operation; return the agent's answer when it took the work."""
    route = (
        agent_runtime if os.environ.get("UNDERCOVER_AGENT_RUNTIME") else agent_laptop
    )
    watch = stopwatch.Stopwatch(f"The agent's answer to {operation}")
    try:
        answer = route.post({"operation": operation, **inputs})
    finally:
        watch.lap("the agent's answer")
        watch.log()
    if "refused" in answer:
        raise Conflict(answer["refused"])
    if not answer.get("accepted"):
        raise ServiceUnavailable(f"The agent didn't take it: {answer}")
    return answer


def work_run(run_id: int) -> None:
    """Ask the agent to work a dispatch or an evaluation the app has created."""
    _ask("work_run", run_id=run_id)


def work_round(round_id: int) -> None:
    """Ask the agent to work a round the app has created."""
    _ask("work_round", round_id=round_id)


def carry_round_on(round_id: int, proposal_id: int) -> None:
    """Ask the agent to carry a round on after a handler's review of a proposal."""
    _ask("carry_round_on", round_id=round_id, proposal_id=proposal_id)


def resume_claim(claim_id: str) -> None:
    """Ask the agent to carry on with a claim a handler has answered.

    The answer is saved before this is asked, so a failure is a warning: the agent
    carries the claim on when it next works it.
    """
    try:
        _ask("resume_claim", claim_id=claim_id)
    except (Conflict, ServiceUnavailable, Unconfirmed):
        logger.warning("The agent could not be asked to resume %s", claim_id)
