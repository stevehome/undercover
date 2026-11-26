"""The Copilot's operations: what a payload asks for, checked, then done.

A payload names an operation and carries its inputs: `start_turn` with a handler's
message, `answer_confirmation` with their answer to a card, or `health`. Each turn
takes the handler's sign-in, which the app checked and which goes no further than the
turn's context and its calls to the app. It is answered `{"accepted": true}` at once
and the turn goes on in the background, or `{"healthy": true}`, or a 400 that says
what is wrong. The Copilot asks for no key: the sign-in is what it works with, and on
Runtime AWS checks the caller.
"""

from collections.abc import Callable
from typing import Any, NamedTuple

from pydantic import Field

from agent import (
    checkpoint,
    copilot_memory,
    copilot_readiness,
    copilot_turns,
    harness,
    payloads,
)
from agent.background_work import BackgroundWork
from agent.payloads import OK, Answer, Inputs, NoInputs

HEALTH = "health"
ACCEPTED = {"accepted": True}


class TurnInputs(Inputs):
    """What every turn needs: the conversation, the handler's sign-in and the model."""

    conversation_id: str
    sign_in: str = Field(repr=False)
    model: str
    reasoning_effort: str


class StartTurn(TurnInputs):
    message: str


class AnswerConfirmation(TurnInputs):
    confirmed: bool
    card: dict[str, Any]


class Operation(NamedTuple):
    """An operation: its inputs, and what it does with them and the background."""

    inputs: type[Inputs]
    run: Callable[[Any, BackgroundWork], dict[str, Any]]


def _turn(inputs: TurnInputs) -> copilot_turns.Turn:
    return copilot_turns.Turn(
        inputs.conversation_id,
        inputs.sign_in,
        harness.copilot_model(inputs.model, inputs.reasoning_effort),
        checkpoint.saver(),
        copilot_memory.open_for_handlers(),
    )


def _start_turn(inputs: StartTurn, background: BackgroundWork) -> dict[str, Any]:
    background.start("turn", copilot_turns.work_turn, _turn(inputs), inputs.message)
    return ACCEPTED


def _answer_confirmation(
    inputs: AnswerConfirmation, background: BackgroundWork
) -> dict[str, Any]:
    background.start(
        "answer",
        copilot_turns.answer_confirmation,
        _turn(inputs),
        inputs.confirmed,
        inputs.card,
    )
    return ACCEPTED


OPERATIONS = {
    "start_turn": Operation(StartTurn, _start_turn),
    "answer_confirmation": Operation(AnswerConfirmation, _answer_confirmation),
    HEALTH: Operation(NoInputs, lambda inputs, background: {"healthy": True}),
}


def handle(payload: Any, background: BackgroundWork) -> Answer:
    """Check a payload, get the Copilot ready and do what it asks."""
    read = payloads.read(payload, {name: o.inputs for name, o in OPERATIONS.items()})
    if isinstance(read, Answer):
        return read
    name, inputs = read
    copilot_readiness.ensure()
    return Answer(OK, OPERATIONS[name].run(inputs, background))
