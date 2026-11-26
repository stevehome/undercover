"""The agent's operations: what a payload asks for, checked, then done.

A payload names an operation and carries its inputs. It is answered with a status
and a body: `{"accepted": true}` when the work is taken, `{"refused": reason}` when
it can't be, and a 400 that says what is wrong with a payload that is not right.
"""

from collections.abc import Callable
from typing import Any, NamedTuple

from agent import key_check, payloads, readiness, work_requests
from agent.background_work import BackgroundWork
from agent.payloads import OK, UNAUTHORIZED, Answer, Inputs, NoInputs

HEALTH = "health"


class WorkRun(Inputs):
    run_id: int


class WorkRound(Inputs):
    round_id: int


class CarryRoundOn(Inputs):
    round_id: int
    proposal_id: int


class ResumeClaim(Inputs):
    claim_id: str


class Operation(NamedTuple):
    """An operation: its inputs, and what it does with them and the background."""

    inputs: type[Inputs]
    run: Callable[[Any, BackgroundWork], dict[str, Any]]


OPERATIONS = {
    "work_run": Operation(
        WorkRun, lambda i, background: work_requests.work_run(i.run_id, background)
    ),
    "work_round": Operation(
        WorkRound,
        lambda i, background: work_requests.work_round(i.round_id, background),
    ),
    "carry_round_on": Operation(
        CarryRoundOn,
        lambda i, background: work_requests.carry_round_on(
            i.round_id, i.proposal_id, background
        ),
    ),
    "resume_claim": Operation(
        ResumeClaim,
        lambda i, background: work_requests.resume_claim(i.claim_id, background),
    ),
    HEALTH: Operation(NoInputs, lambda i, background: work_requests.health()),
}


def handle(
    payload: Any, authorization: str | None, background: BackgroundWork
) -> Answer:
    """Check a payload and its key, get the agent ready and do what it asks."""
    read = payloads.read(payload, {name: o.inputs for name, o in OPERATIONS.items()})
    if isinstance(read, Answer):
        return read
    name, inputs = read
    if name != HEALTH and (reason := key_check.refusal(authorization)):
        return Answer(UNAUTHORIZED, {"error": reason})
    readiness.ensure()
    return Answer(OK, OPERATIONS[name].run(inputs, background))
