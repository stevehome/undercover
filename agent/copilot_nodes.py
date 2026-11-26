"""The nodes of the Copilot's graph: each takes the state and returns changes."""

import json
from decimal import Decimal
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.runtime import Runtime

from agent import copilot_recording
from agent.copilot_context import CopilotContext
from agent.copilot_instructions import instructions
from agent.copilot_state import CopilotState
from agent.refusals import Refusal

MAX_MODEL_CALLS = 25
NANOS_PER_DOLLAR = 10**9
MEMORY_TOOL = "search_memory"


class ModelCallLimit(Exception):  # noqa: N818 - a failure of the turn
    """The model was called more times than a turn should ever need."""


def _last_handler_message(state: CopilotState) -> str:
    return next(
        str(m.content)
        for m in reversed(state["messages"])
        if isinstance(m, HumanMessage)
    )


def recall(state: CopilotState, runtime: Runtime[CopilotContext]) -> dict[str, Any]:
    """Look up what the memory holds about the handler that bears on their message.

    The lookup is a card like any other. With no memory there is nothing to do, and a
    lookup the memory refuses leaves the turn to go on without it.
    """
    context = runtime.context
    if context.memory is None:
        return {}
    query = _last_handler_message(state)
    step_id = copilot_recording.begin(context, MEMORY_TOOL, "memory", query)
    try:
        found = context.memory.search(context.handler_id, query)
    except Refusal as refusal:
        copilot_recording.end(
            context, step_id, copilot_recording.refused(refusal.message)
        )
        return {}
    copilot_recording.end(context, step_id, copilot_recording.done(json.dumps(found)))
    return {"remembered": found}


def agent(
    state: CopilotState,
    runtime: Runtime[CopilotContext],
    *,
    model: Runnable[LanguageModelInput, AIMessage],
) -> dict[str, Any]:
    """Call the model with the conversation so far, and add up what it cost."""
    if state["model_calls"] >= MAX_MODEL_CALLS:
        raise ModelCallLimit(f"More than {MAX_MODEL_CALLS} model calls in one turn")
    context = runtime.context
    system = instructions(
        context.handler_name, context.can_approve_over_limit, state["remembered"]
    )
    reply = model.invoke([SystemMessage(system), *state["messages"]])
    cost = Decimal(str(reply.response_metadata["token_usage"]["cost"]))
    return {
        "messages": [reply],
        "model_calls": state["model_calls"] + 1,
        "cost_nanos": state["cost_nanos"] + int(cost * NANOS_PER_DOLLAR),
    }


def remember(state: CopilotState, runtime: Runtime[CopilotContext]) -> dict[str, Any]:
    """Save the handler's message and the answer to the handler's memory, and nothing
    else: no tool calls, no tool results and never the sign-in. With no memory there
    is nothing to do."""
    context = runtime.context
    if context.memory is not None:
        context.memory.save_turn(
            context.handler_id,
            context.conversation_id,
            _last_handler_message(state),
            str(state["messages"][-1].content),
        )
    return {}
