"""The steps of a Copilot turn, one card each: started, then finished."""

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import insert, select, update

from backend import copilot_conversations, copilot_turns, db, tables
from backend.errors import Conflict, NotFound
from backend.statuses import CardKind, StepState

RESULT_LENGTH = 1500


class Outcome(BaseModel):
    """How a step went: its result, the files a lookup read and why it was refused."""

    state: StepState
    result: str
    files: dict[str, dict[str, str]] | None = None
    reason: str | None = None


def trim(text: str) -> str:
    """Cut a result to a length a card can show."""
    return text if len(text) <= RESULT_LENGTH else f"{text[: RESULT_LENGTH - 1]}…"


def start(
    conversation_id: str, handler_id: str, tool: str, kind: CardKind, input_text: str
) -> int:
    """Record a step as working, in the turn the handler's last message began."""
    copilot_conversations.require_own(conversation_id, handler_id)
    message_id = copilot_turns.last_handler_message(conversation_id)
    with db.connection() as conn:
        return conn.execute(
            insert(tables.copilot_steps)
            .values(
                conversation_id=conversation_id,
                message_id=message_id,
                tool=tool,
                kind=kind,
                input=trim(input_text),
                state=StepState.WORKING,
                started_on=db.now(),
            )
            .returning(tables.copilot_steps.c.id)
        ).scalar_one()


def conversation_of(step_id: int) -> str:
    """Return the conversation a step belongs to, or raise NotFound."""
    columns = tables.copilot_steps.c
    with db.connection() as conn:
        found = conn.execute(
            select(columns.conversation_id).where(columns.id == step_id)
        ).scalar_one_or_none()
    if found is None:
        raise NotFound(f"No step {step_id}")
    return found


def finish(step_id: int, handler_id: str, outcome: Outcome) -> None:
    """Finish a working step of the handler's own conversation."""
    copilot_conversations.require_own(conversation_of(step_id), handler_id)
    if outcome.state == StepState.WORKING:
        raise Conflict("A step finishes as done, refused or failed")
    columns = tables.copilot_steps.c
    with db.connection() as conn:
        finished = conn.execute(
            update(tables.copilot_steps)
            .where(columns.id == step_id, columns.state == StepState.WORKING)
            .values(
                state=outcome.state,
                finished_on=db.now(),
                result=trim(outcome.result),
                files=outcome.files,
                reason=outcome.reason,
            )
        )
    if finished.rowcount == 0:
        raise Conflict("The step has already finished")


def list_steps(conversation_id: str) -> list[dict[str, Any]]:
    """List a conversation's steps in order, with the seconds each took."""
    columns = tables.copilot_steps.c
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.copilot_steps)
            .where(columns.conversation_id == conversation_id)
            .order_by(columns.id)
        )
        return [_with_seconds(dict(row._mapping)) for row in rows]


def _with_seconds(step: dict[str, Any]) -> dict[str, Any]:
    finished = step.pop("finished_on")
    step["seconds"] = (
        None
        if finished is None
        else (
            datetime.fromisoformat(finished)
            - datetime.fromisoformat(step["started_on"])
        )
        / timedelta(seconds=1)
    )
    return step
