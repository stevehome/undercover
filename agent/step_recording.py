"""Recording what the claim agent's tools do, as steps on the claim.

A tool a source refuses is recorded with who refused it, and the model gets the
refusal to read, so the claim's work goes on.
"""

from collections.abc import Callable
from typing import Any, cast

from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from agent import api
from agent.contexts import ClaimContext
from agent.refusals import Refusal


def record_tool_call(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
) -> ToolMessage | Command[Any]:
    """Run a tool; a refusal is recorded on the claim and handed to the model."""
    try:
        return execute(request)
    except Refusal as refusal:
        context = cast(ClaimContext, request.runtime.context)
        api.record_step(context.claim_id, refusal.message)
        return ToolMessage(
            content=refusal.message,
            name=request.tool_call["name"],
            tool_call_id=request.tool_call["id"],
            status="error",
        )
