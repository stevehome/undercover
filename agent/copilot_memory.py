"""The Copilot's memory of each handler, in AgentCore Memory.

After a turn the Copilot saves the handler's message and its answer as two events,
with the handler as the actor and the conversation as the session, and AgentCore
turns them into preferences and facts in the background. It searches only under the
handler's own id, which the app's answer to "who is signed in" gives and never the
model or the message, so one handler's memories never reach another's turn.
"""

import logging
from collections.abc import Mapping
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from agent import endpoints
from agent.memory import AWS_ERRORS, MemoryStore, open_store
from agent.refusals import BY_MEMORY, Refusal

HANDLERS = "handlers"
SEARCH_LIMIT = 5
logger = logging.getLogger(__name__)


class HandlerMemory:
    """Saves a turn to a handler's memory and searches it."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def save_turn(
        self, handler_id: str, conversation_id: str, message: str, answer: str
    ) -> list[str]:
        """Save the handler's message and the answer; return what was saved.

        A turn keeps its answer when AgentCore can't be reached: the memory only adds
        to what the Copilot knows, so a failed save is logged and the work goes on.
        """
        namespace = (handler_id, conversation_id)
        events: Mapping[str, Mapping[str, Any]] = {
            "message": {"message": HumanMessage(message)},
            "answer": {"message": AIMessage(answer)},
        }
        try:
            for key, value in events.items():
                self.store.put(namespace, key, value)
        except AWS_ERRORS:
            logger.warning("Could not save a turn to the memory", exc_info=True)
            return []
        return [message, answer]

    def search(self, handler_id: str, query: str) -> list[str]:
        """Return what we remember about the handler that bears on the query."""
        try:
            found = self.store.search(
                (HANDLERS, handler_id), query=query, limit=SEARCH_LIMIT
            )
        except AWS_ERRORS as error:
            raise Refusal(BY_MEMORY, str(error)) from error
        return [item.value["content"] for item in found]


def open_for_handlers() -> HandlerMemory | None:
    """Return the Copilot's memory, or None when no memory is set."""
    memory_id = endpoints.copilot_memory_id()
    return None if memory_id is None else HandlerMemory(open_store(memory_id))
