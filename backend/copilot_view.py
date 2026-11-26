"""What the Copilot's sidebar and the Copilot itself read.

The sidebar reads a conversation; the Copilot reads the evaluations' measures and
costs and never a claim's handler decision, as the improver's view of a held-out set.
"""

from typing import Any

from backend import (
    copilot_conversations,
    copilot_steps,
    copilot_turns,
    evaluations,
    money,
)

EVALUATION_FIELDS = (
    "run_id",
    "eval_set",
    "tiny",
    "status",
    "started_on",
    "finished_on",
    "model",
    "reasoning_effort",
    "model_calls",
    "cost",
    "measures",
    "summary",
)


def _message(message: dict[str, Any]) -> dict[str, Any]:
    cost = message["cost_nanos"]
    work = message["work_ms"]
    return {
        "id": message["id"],
        "role": message["role"],
        "text": message["text"],
        "created_on": message["created_on"],
        "model_calls": message["model_calls"],
        "cost": None if cost is None else money.from_nanos(cost),
        "seconds": None if work is None else work / 1000,
    }


def conversation(conversation_id: str, handler_id: str) -> dict[str, Any]:
    """Return a handler's conversation as the sidebar reads it."""
    row = copilot_conversations.require_own(conversation_id, handler_id)
    return {
        "conversation_id": conversation_id,
        "title": row["title"],
        "status": copilot_turns.status_of(row),
        "card": row["card"],
        "failure": row["failure"],
        "messages": [_message(m) for m in copilot_turns.list_messages(conversation_id)],
        "steps": copilot_steps.list_steps(conversation_id),
    }


def evaluation_measures() -> list[dict[str, Any]]:
    """List the evaluations, newest first, with their measures and no claims."""
    return [
        {field: found[field] for field in EVALUATION_FIELDS}
        for found in evaluations.list_evaluations()
    ]
