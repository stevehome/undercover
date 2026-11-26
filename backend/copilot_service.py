"""Asking the Copilot to work a turn, and the one place that does.

The Copilot is an AgentCore app. A payload names an operation, and goes to the
Copilot on a host of its own (`UNDERCOVER_COPILOT`) or, when
`UNDERCOVER_COPILOT_RUNTIME` names a runtime's ARN, to that runtime in the
conversation's own session. It carries the handler's sign-in and never the agent's
key. A turn the Copilot didn't take is undone and the reason passed on; a timeout
leaves it going, since the Copilot may have it.
"""

import os
import time
from typing import Any

from backend import (
    agent_answer,
    agent_laptop,
    agent_runtime,
    copilot_turns,
    model_used,
)
from backend.errors import Conflict, ServiceUnavailable

DEFAULT_COPILOT_URL = "http://127.0.0.1:8081"
BUSY_TRIES = 4
BUSY_WAIT_SECONDS = 2


def _send(payload: dict[str, Any], conversation_id: str | None) -> dict[str, Any]:
    """Send one payload and return the Copilot's answer.

    On Runtime it goes to the conversation's session, again after a short wait while
    that session is busy.
    """
    arn = os.environ.get("UNDERCOVER_COPILOT_RUNTIME")
    if not arn:
        url = os.environ.get("UNDERCOVER_COPILOT", DEFAULT_COPILOT_URL)
        return agent_laptop.post(payload, url, with_key=False)
    for _ in range(BUSY_TRIES - 1):
        try:
            return agent_runtime.post(payload, arn, conversation_id)
        except agent_runtime.SessionBusy:
            time.sleep(BUSY_WAIT_SECONDS)
    return agent_runtime.post(payload, arn, conversation_id)


def _ask(conversation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a payload; return the Copilot's answer when it took the work."""
    return agent_answer.taken(_send(payload, conversation_id), "The Copilot")


def _turn_payload(
    operation: str, conversation_id: str, token: str, **inputs: Any
) -> dict[str, Any]:
    model, effort = model_used.for_copilot()
    return {
        "operation": operation,
        "conversation_id": conversation_id,
        "sign_in": token,
        "model": model,
        "reasoning_effort": effort,
        **inputs,
    }


def start_turn(conversation_id: str, handler_id: str, token: str, text: str) -> None:
    """Save a handler's message and ask the Copilot to answer it."""
    message_id = copilot_turns.begin(conversation_id, handler_id, text)
    try:
        _ask(
            conversation_id,
            _turn_payload("start_turn", conversation_id, token, message=text),
        )
    except (Conflict, ServiceUnavailable):
        copilot_turns.undo_begin(conversation_id, message_id)
        raise


def answer_confirmation(
    conversation_id: str, handler_id: str, token: str, confirmed: bool
) -> None:
    """Take a handler's answer to the waiting card and ask the Copilot to go on."""
    card = copilot_turns.answer_confirmation(conversation_id, handler_id)
    try:
        _ask(
            conversation_id,
            _turn_payload(
                "answer_confirmation", conversation_id, token, confirmed=confirmed
            ),
        )
    except (Conflict, ServiceUnavailable):
        copilot_turns.wait_for_confirmation(conversation_id, handler_id, card)
        raise


def health() -> bool:
    """Say whether the Copilot is running."""
    return bool(_send({"operation": "health"}, None).get("healthy"))
