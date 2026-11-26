"""The Copilot's routes: a handler's conversations, and the Copilot's calls back.

Every route takes a signed-in handler. The Copilot calls the app back as the handler
it works for, with the handler's own sign-in, so it can only touch that handler's
conversations.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend import (
    copilot_conversations,
    copilot_service,
    copilot_steps,
    copilot_turns,
    copilot_view,
)
from backend.auth import signed_in_handler, signed_in_token
from backend.statuses import CardKind

router = APIRouter(prefix="/api/copilot")

SignedIn = Annotated[dict[str, Any], Depends(signed_in_handler)]
Token = Annotated[str, Depends(signed_in_token)]
MAX_MESSAGE_LENGTH = 4000


class NewMessage(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class Confirmation(BaseModel):
    confirmed: bool


class NewStep(BaseModel):
    tool: str
    kind: CardKind
    input: str


class WaitingCard(BaseModel):
    card: dict[str, Any]


class Failure(BaseModel):
    reason: str


@router.get("/health", operation_id="copilot_health")
def health(_: SignedIn) -> dict[str, bool]:
    """Say whether the Copilot is running."""
    return {"healthy": copilot_service.health()}


@router.post("/conversations", operation_id="make_conversation", status_code=201)
def make_conversation(handler: SignedIn) -> dict[str, str]:
    """Make an empty conversation for the signed-in handler."""
    return {"conversation_id": copilot_conversations.make(handler["handler_id"])}


@router.get("/conversations", operation_id="list_conversations")
def list_conversations(handler: SignedIn) -> list[dict[str, Any]]:
    """List the signed-in handler's conversations, newest first."""
    return copilot_conversations.list_for(handler["handler_id"])


@router.get("/conversations/{conversation_id}", operation_id="get_conversation")
def get_conversation(conversation_id: str, handler: SignedIn) -> dict[str, Any]:
    """Return a conversation with its messages, steps and waiting card."""
    return copilot_view.conversation(conversation_id, handler["handler_id"])


@router.post(
    "/conversations/{conversation_id}/messages",
    operation_id="send_message",
    status_code=202,
)
def send_message(
    conversation_id: str, message: NewMessage, handler: SignedIn, token: Token
) -> dict[str, str]:
    """Send a message and have the Copilot answer it, one turn at a time."""
    copilot_service.start_turn(
        conversation_id, handler["handler_id"], token, message.text
    )
    return {"conversation_id": conversation_id}


@router.post(
    "/conversations/{conversation_id}/confirmation",
    operation_id="answer_confirmation",
    status_code=202,
)
def answer_confirmation(
    conversation_id: str, answer: Confirmation, handler: SignedIn, token: Token
) -> dict[str, str]:
    """Answer the confirmation a turn is waiting for, and have the Copilot go on."""
    copilot_service.answer_confirmation(
        conversation_id, handler["handler_id"], token, answer.confirmed
    )
    return {"conversation_id": conversation_id}


@router.post("/conversations/{conversation_id}/steps", operation_id="start_step")
def start_step(
    conversation_id: str, step: NewStep, handler: SignedIn
) -> dict[str, int]:
    """Record a step of the turn as working; the Copilot calls this."""
    return {
        "step_id": copilot_steps.start(
            conversation_id, handler["handler_id"], step.tool, step.kind, step.input
        )
    }


@router.post("/steps/{step_id}/finish", operation_id="finish_step")
def finish_step(
    step_id: int, outcome: copilot_steps.Outcome, handler: SignedIn
) -> dict[str, int]:
    """Finish a step as done, refused or failed; the Copilot calls this."""
    copilot_steps.finish(step_id, handler["handler_id"], outcome)
    return {"step_id": step_id}


@router.post("/conversations/{conversation_id}/waiting", operation_id="turn_waiting")
def turn_waiting(
    conversation_id: str, waiting: WaitingCard, handler: SignedIn
) -> dict[str, str]:
    """Say the turn is waiting for the handler to answer; the Copilot calls this."""
    copilot_turns.wait_for_confirmation(
        conversation_id, handler["handler_id"], waiting.card
    )
    return {"conversation_id": conversation_id}


@router.post("/conversations/{conversation_id}/done", operation_id="turn_done")
def turn_done(
    conversation_id: str, answer: copilot_turns.Answer, handler: SignedIn
) -> dict[str, str]:
    """End the turn with the Copilot's answer; the Copilot calls this."""
    copilot_turns.finish(conversation_id, handler["handler_id"], answer)
    return {"conversation_id": conversation_id}


@router.post("/conversations/{conversation_id}/failed", operation_id="turn_failed")
def turn_failed(
    conversation_id: str, failure: Failure, handler: SignedIn
) -> dict[str, str]:
    """End the turn as failed, with the reason; the Copilot calls this."""
    copilot_turns.fail(conversation_id, handler["handler_id"], failure.reason)
    return {"conversation_id": conversation_id}


@router.get("/evaluations", operation_id="copilot_evaluations")
def copilot_evaluations(_: SignedIn) -> list[dict[str, Any]]:
    """List the evaluations with their measures, and no claim's handler decision."""
    return copilot_view.evaluation_measures()
