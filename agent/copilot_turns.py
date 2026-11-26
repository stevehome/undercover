"""Working one Copilot turn: who is signed in, the graph, and telling the app.

A turn begins by asking the app who is signed in. If the app doesn't accept the
sign-in, the turn ends there, before any call to the model; the app can't be told, as
telling it takes the same sign-in, and its 20-minute rule shows the turn as stopped.
Otherwise the graph runs on the conversation's thread and the app is told the answer
with what the turn took, or why it failed.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from agent import copilot_api
from agent.copilot_context import CopilotContext
from agent.copilot_graph import build_copilot_graph
from agent.copilot_memory import HandlerMemory
from agent.copilot_route import context_route
from agent.copilot_state import new_turn
from agent.refusals import Refusal

UNFINISHED = "That step didn't finish."
LAST_NODE = "remember"
MS_PER_SECOND = 1_000
logger = logging.getLogger(__name__)


def _unanswered(messages: list[BaseMessage]) -> list[ToolMessage]:
    """Answer each tool call a stopped turn left with no answer.

    The model's API refuses a conversation whose tool call has no answer, so a turn
    carried on after one stopped partway answers it first.
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    return [
        ToolMessage(
            UNFINISHED, tool_call_id=call["id"], name=call["name"], status="error"
        )
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call["id"] not in answered
    ]


def _failure(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


@dataclass
class Turn:
    """What one turn works with: the conversation, the handler's sign-in, the model,
    the saved state and the handler's memory if there is one."""

    conversation_id: str
    sign_in: str = field(repr=False)
    model: BaseChatModel
    checkpointer: BaseCheckpointSaver
    memory: HandlerMemory | None


def _context(turn: Turn, handler: dict[str, Any]) -> CopilotContext:
    return CopilotContext(
        handler_id=handler["handler_id"],
        handler_name=handler["name"],
        can_approve_over_limit=handler["can_approve_over_limit"],
        conversation_id=turn.conversation_id,
        sign_in=turn.sign_in,
        route=context_route(),
        memory=turn.memory,
    )


def _run(turn: Turn, start: Any, resume_with: Any = None) -> None:
    """Run the graph on the conversation's thread and tell the app how it went.

    A graph that returns with an interrupt is waiting for the handler: the app is
    told, with the card. Otherwise the turn is over, with its answer or its failure.
    """
    began = time.monotonic()
    try:
        handler = copilot_api.who_is_signed_in(turn.sign_in)
    except Refusal:
        logger.warning("The app didn't accept a turn's sign-in; it ends here")
        return
    graph = build_copilot_graph(turn.checkpointer, turn.model)
    config: Any = {"configurable": {"thread_id": turn.conversation_id}}
    try:
        if resume_with is None:
            saved = graph.get_state(config).values.get("messages", [])
            if unfinished := _unanswered(saved):
                # Written as the last node, as if that turn had ended there, so no
                # node of it is left to run before the new message's turn.
                graph.update_state(config, {"messages": unfinished}, as_node=LAST_NODE)
            state = graph.invoke(
                new_turn(start), config, context=_context(turn, handler)
            )
        else:
            state = graph.invoke(
                Command(resume=resume_with), config, context=_context(turn, handler)
            )
        waiting = graph.get_state(config).interrupts
    except Exception as error:
        copilot_api.turn_failed(turn.sign_in, turn.conversation_id, _failure(error))
        return
    if waiting:
        copilot_api.turn_waiting(turn.sign_in, turn.conversation_id, waiting[0].value)
        return
    copilot_api.turn_done(
        turn.sign_in,
        turn.conversation_id,
        {
            "text": str(state["messages"][-1].content),
            "model_calls": state["model_calls"],
            "cost_nanos": state["cost_nanos"],
            "work_ms": int((time.monotonic() - began) * MS_PER_SECOND),
        },
    )


def work_turn(turn: Turn, message: str) -> None:
    """Answer a handler's message and tell the app how it went."""
    _run(turn, message)


def answer_confirmation(turn: Turn, confirmed: bool, card: dict[str, Any]) -> None:
    """Carry a paused turn on with the handler's answer to the card they were shown."""
    _run(turn, None, {"confirmed": confirmed, "card": card})
