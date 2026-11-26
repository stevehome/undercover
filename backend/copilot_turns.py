"""A Copilot conversation's turns: one at a time, as a sign-off is.

A turn begins only when the conversation isn't working, so two messages can't start
two turns. A turn working for over 20 minutes is stopped: it reads as stopped and the
handler may send another message. A turn waiting for a handler's confirmation is never
stopped.
"""

from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_, insert, or_, select, update

from backend import copilot_conversations, db, tables
from backend.errors import Conflict
from backend.statuses import TurnStatus

TURN_SECONDS = 20 * 60
TITLE_LENGTH = 60
FAILED_MESSAGE = "I couldn't finish that: {reason}"


class Answer(BaseModel):
    """The Copilot's answer, with the model calls, cost and time it took."""

    text: str
    model_calls: int
    cost_nanos: int
    work_ms: int


def _cutoff() -> str:
    return db.now(-TURN_SECONDS)


def status_of(row: dict[str, Any]) -> TurnStatus:
    """A conversation's turn status, `stopped` for a turn that has worked too long."""
    if row["turn_status"] == TurnStatus.WORKING and row["turn_started_on"] < _cutoff():
        return TurnStatus.STOPPED
    return TurnStatus(row["turn_status"])


def _title(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= TITLE_LENGTH else f"{line[: TITLE_LENGTH - 1]}…"


def begin(conversation_id: str, handler_id: str, text: str) -> int:
    """Save a handler's message and begin the turn it asks for; return its id.

    The conversation's first question becomes its title. A conversation that is
    working or waiting for a confirmation is a Conflict.
    """
    copilot_conversations.require_own(conversation_id, handler_id)
    columns = tables.copilot_conversations.c
    now = db.now()
    with db.connection() as conn:
        begun = conn.execute(
            update(tables.copilot_conversations)
            .where(
                columns.conversation_id == conversation_id,
                or_(
                    columns.turn_status.in_([TurnStatus.DONE, TurnStatus.FAILED]),
                    and_(
                        columns.turn_status == TurnStatus.WORKING,
                        columns.turn_started_on < _cutoff(),
                    ),
                ),
            )
            .values(
                turn_status=TurnStatus.WORKING,
                turn_started_on=now,
                card=None,
                failure=None,
            )
        )
        if begun.rowcount == 0:
            waiting = (
                conn.execute(
                    select(columns.turn_status).where(
                        columns.conversation_id == conversation_id
                    )
                ).scalar_one()
                == TurnStatus.WAITING
            )
            raise Conflict(
                "Answer the confirmation first"
                if waiting
                else "The Copilot is still working on your last message"
            )
        message_id = conn.execute(
            insert(tables.copilot_messages)
            .values(
                conversation_id=conversation_id,
                role="handler",
                text=text,
                created_on=now,
            )
            .returning(tables.copilot_messages.c.id)
        ).scalar_one()
        conn.execute(
            update(tables.copilot_conversations)
            .where(columns.conversation_id == conversation_id, columns.title.is_(None))
            .values(title=_title(text))
        )
    return message_id


def undo_begin(conversation_id: str, message_id: int) -> None:
    """Undo a turn the Copilot didn't take: its message goes and they can ask again."""
    columns = tables.copilot_conversations.c
    messages = tables.copilot_messages.c
    with db.connection() as conn:
        conn.execute(tables.copilot_messages.delete().where(messages.id == message_id))
        left = conn.execute(
            select(messages.id).where(messages.conversation_id == conversation_id)
        ).first()
        conn.execute(
            update(tables.copilot_conversations)
            .where(columns.conversation_id == conversation_id)
            .values(
                turn_status=TurnStatus.DONE,
                turn_started_on=None,
                **({} if left else {"title": None}),
            )
        )


def _change(conversation_id: str, was: TurnStatus, **values: Any) -> None:
    """Move a conversation from one turn status to another, or raise Conflict."""
    columns = tables.copilot_conversations.c
    with db.connection() as conn:
        moved = conn.execute(
            update(tables.copilot_conversations)
            .where(
                columns.conversation_id == conversation_id,
                columns.turn_status == was,
            )
            .values(**values)
        )
    if moved.rowcount == 0:
        raise Conflict(f"The conversation isn't {was}")


def wait_for_confirmation(
    conversation_id: str, handler_id: str, card: dict[str, Any]
) -> None:
    """Note that the turn is waiting for the handler's answer to a card."""
    copilot_conversations.require_own(conversation_id, handler_id)
    _change(
        conversation_id,
        TurnStatus.WORKING,
        turn_status=TurnStatus.WAITING,
        card=card,
    )


def answer_confirmation(conversation_id: str, handler_id: str) -> dict[str, Any]:
    """Take the handler's answer to the waiting card and start the turn again.

    Returns the card that was answered. The turn counts from now.
    """
    row = copilot_conversations.require_own(conversation_id, handler_id)
    _change(
        conversation_id,
        TurnStatus.WAITING,
        turn_status=TurnStatus.WORKING,
        turn_started_on=db.now(),
        card=None,
    )
    return row["card"]


def _end(
    conversation_id: str,
    status: TurnStatus,
    text: str,
    failure: str | None,
    usage: tuple[int, int, int] | tuple[None, None, None],
) -> None:
    """End the turn and save the Copilot's message in one transaction."""
    columns = tables.copilot_conversations.c
    model_calls, cost_nanos, work_ms = usage
    with db.connection() as conn:
        ended = conn.execute(
            update(tables.copilot_conversations)
            .where(
                columns.conversation_id == conversation_id,
                columns.turn_status == TurnStatus.WORKING,
            )
            .values(turn_status=status, failure=failure, card=None)
        )
        if ended.rowcount == 0:
            raise Conflict("The conversation isn't working")
        conn.execute(
            insert(tables.copilot_messages).values(
                conversation_id=conversation_id,
                role="copilot",
                text=text,
                created_on=db.now(),
                model_calls=model_calls,
                cost_nanos=cost_nanos,
                work_ms=work_ms,
            )
        )


def finish(conversation_id: str, handler_id: str, answer: Answer) -> None:
    """End the turn with the Copilot's answer and what it took."""
    copilot_conversations.require_own(conversation_id, handler_id)
    _end(
        conversation_id,
        TurnStatus.DONE,
        answer.text,
        None,
        (answer.model_calls, answer.cost_nanos, answer.work_ms),
    )


def fail(conversation_id: str, handler_id: str, reason: str) -> None:
    """End the turn with a short message and the reason; the handler can ask again."""
    copilot_conversations.require_own(conversation_id, handler_id)
    _end(
        conversation_id,
        TurnStatus.FAILED,
        FAILED_MESSAGE.format(reason=reason),
        reason,
        (None, None, None),
    )


def list_messages(conversation_id: str) -> list[dict[str, Any]]:
    """List a conversation's messages in the order they were sent."""
    columns = tables.copilot_messages.c
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.copilot_messages)
            .where(columns.conversation_id == conversation_id)
            .order_by(columns.id)
        )
        return [dict(row._mapping) for row in rows]


def last_handler_message(conversation_id: str) -> int:
    """Return the id of the handler's latest message: the one the turn answers."""
    columns = tables.copilot_messages.c
    with db.connection() as conn:
        return conn.execute(
            select(columns.id)
            .where(
                columns.conversation_id == conversation_id, columns.role == "handler"
            )
            .order_by(columns.id.desc())
            .limit(1)
        ).scalar_one()
