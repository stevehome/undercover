"""The agent's operations: what a payload asks for, checked, then done.

A payload names an operation and carries its inputs. It is answered with a status
and a body: `{"accepted": true}` when the work is taken, `{"refused": reason}` when
it can't be, and a 400 that says what is wrong with a payload that is not right.
"""

from collections.abc import Callable
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, ValidationError

from agent import key_check, readiness, work_requests
from agent.background_work import BackgroundWork

HEALTH = "health"
BAD_REQUEST = 400
UNAUTHORIZED = 401
OK = 200


class Inputs(BaseModel):
    """An operation's inputs; any input it doesn't name is wrong."""

    model_config = ConfigDict(extra="forbid")


class NoInputs(Inputs):
    pass


class StartDispatch(Inputs):
    concurrency: int


class StartEvaluation(Inputs):
    concurrency: int
    eval_set: str
    tiny: bool


class StartRound(Inputs):
    handler_id: str


class DecideProposal(Inputs):
    proposal_id: int
    decision: str
    handler_id: str
    reason: str


class ResumeClaim(Inputs):
    claim_id: str


class Answer(NamedTuple):
    """What a payload is answered with."""

    status: int
    body: dict[str, Any]


class Operation(NamedTuple):
    """An operation: its inputs, and what it does with them and the background."""

    inputs: type[Inputs]
    run: Callable[[Any, BackgroundWork], dict[str, Any]]


OPERATIONS = {
    "start_dispatch": Operation(
        StartDispatch,
        lambda i, background: work_requests.start_dispatch(i.concurrency, background),
    ),
    "start_evaluation": Operation(
        StartEvaluation,
        lambda i, background: work_requests.start_evaluation(
            i.concurrency, i.eval_set, i.tiny, background
        ),
    ),
    "start_round": Operation(
        StartRound,
        lambda i, background: work_requests.start_round(i.handler_id, background),
    ),
    "decide_proposal": Operation(
        DecideProposal,
        lambda i, background: work_requests.decide_proposal(
            i.proposal_id, i.decision, i.handler_id, i.reason, background
        ),
    ),
    "resume_claim": Operation(
        ResumeClaim,
        lambda i, background: work_requests.resume_claim(i.claim_id, background),
    ),
    HEALTH: Operation(NoInputs, lambda i, background: work_requests.health()),
}


def _wrong(message: str) -> Answer:
    return Answer(BAD_REQUEST, {"error": message})


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
        for problem in error.errors()
    )


def handle(
    payload: Any, authorization: str | None, background: BackgroundWork
) -> Answer:
    """Check a payload and its key, get the agent ready and do what it asks."""
    if not isinstance(payload, dict) or "operation" not in payload:
        return _wrong('Send an object with an "operation" and its inputs')
    name = payload["operation"]
    operation = OPERATIONS.get(name)
    if operation is None:
        known = ", ".join(OPERATIONS)
        return _wrong(f"Unknown operation {name!r}; the operations are {known}")
    given = {key: value for key, value in payload.items() if key != "operation"}
    try:
        inputs = operation.inputs.model_validate(given)
    except ValidationError as error:
        return _wrong(f"{name}: {_describe(error)}")
    if name != HEALTH and (reason := key_check.refusal(authorization)):
        return Answer(UNAUTHORIZED, {"error": reason})
    readiness.ensure()
    return Answer(OK, operation.run(inputs, background))
