"""A handler's Copilot conversations: making, listing and reading their own.

The one place that says whose a conversation is: every other Copilot module asks
here first, and another handler's conversation is a 403.
"""

import uuid
from typing import Any

from sqlalchemy import insert, select

from backend import db, tables
from backend.errors import Forbidden, NotFound
from backend.statuses import TurnStatus

ID_PREFIX = "copilot-"


def make(handler_id: str) -> str:
    """Make an empty conversation for a handler; return its id.

    The id is the Copilot's thread and its Runtime session, so it is made of letters,
    digits and hyphens, and is long enough for Runtime.
    """
    conversation_id = f"{ID_PREFIX}{uuid.uuid4()}"
    with db.connection() as conn:
        conn.execute(
            insert(tables.copilot_conversations).values(
                conversation_id=conversation_id,
                handler_id=handler_id,
                created_on=db.now(),
                turn_status=TurnStatus.DONE,
            )
        )
    return conversation_id


def require_own(conversation_id: str, handler_id: str) -> dict[str, Any]:
    """Return a handler's own conversation's row, or raise NotFound or Forbidden."""
    columns = tables.copilot_conversations.c
    with db.connection() as conn:
        row = conn.execute(
            select(tables.copilot_conversations).where(
                columns.conversation_id == conversation_id
            )
        ).one_or_none()
    if row is None:
        raise NotFound(f"No conversation {conversation_id}")
    if row.handler_id != handler_id:
        raise Forbidden("This conversation belongs to another handler")
    return dict(row._mapping)


def list_for(handler_id: str) -> list[dict[str, Any]]:
    """List a handler's own conversations, newest first."""
    columns = tables.copilot_conversations.c
    with db.connection() as conn:
        rows = conn.execute(
            select(columns.conversation_id, columns.title, columns.created_on)
            .where(columns.handler_id == handler_id)
            .order_by(columns.created_on.desc(), columns.conversation_id)
        )
        return [dict(row._mapping) for row in rows]
