"""Recording what the Copilot does as steps of its turn, one card for each.

A tool call is a card, working while it runs and done, refused or failed when it ends.
Its name is the one the route gives a context-layer tool (the Gateway's
`undercover-context___lookup_term`) and the tool's own otherwise. A context-layer
answer carries its files and their owners. A refusal is handed to the model to read,
so the turn goes on; any other failure ends the turn.
"""

import json
from collections.abc import Callable
from typing import Any, cast

from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from agent import copilot_api
from agent.copilot_api import CardKind
from agent.copilot_context import CopilotContext
from agent.copilot_tools import KINDS
from agent.refusals import Refusal
from agent.tool_route import CONTEXT
from agent.tools import TARGETS


def begin(context: CopilotContext, tool: str, kind: CardKind, input_text: str) -> int:
    """Record a step as working; return its id."""
    return copilot_api.start_step(
        context.sign_in, context.conversation_id, tool, kind, input_text
    )


Outcome = dict[str, Any]


def done(result: str, files: dict[str, Any] | None = None) -> Outcome:
    """A step that finished: what came back, and the files it came from."""
    return {"state": "done", "result": result, "files": files, "reason": None}


def refused(reason: str) -> Outcome:
    """A step something refused, with the reason."""
    return {"state": "refused", "result": "", "files": None, "reason": reason}


def failed(reason: str) -> Outcome:
    """A step that failed, with the reason."""
    return {"state": "failed", "result": "", "files": None, "reason": reason}


def end(context: CopilotContext, step_id: int, outcome: Outcome) -> None:
    """Finish a step as done, refused or failed."""
    copilot_api.finish_step(context.sign_in, step_id, outcome)


def _main_input(arguments: dict[str, Any]) -> str:
    return ", ".join(f"{name}: {value}" for name, value in arguments.items())


def _files(tool: str, content: str) -> dict[str, Any] | None:
    """The files and owners a context-layer answer came from."""
    if TARGETS.get(tool) != CONTEXT:
        return None
    return json.loads(content)["sources"]


def record_tool_call(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
) -> ToolMessage | Command[Any]:
    """Run a tool and record it; a refusal is recorded and handed to the model."""
    context = cast(CopilotContext, request.runtime.context)
    tool = request.tool_call["name"]
    arguments = request.tool_call["args"]
    name = context.route.tool_name(TARGETS[tool], tool) if tool in TARGETS else tool
    step_id = begin(context, name, KINDS[tool], _main_input(arguments))
    try:
        message = execute(request)
    except Refusal as refusal:
        end(context, step_id, refused(refusal.message))
        return ToolMessage(
            content=refusal.message,
            name=tool,
            tool_call_id=request.tool_call["id"],
            status="error",
        )
    except Exception as error:
        end(context, step_id, failed(f"{type(error).__name__}: {error}"))
        raise
    content = str(cast(ToolMessage, message).content)
    end(context, step_id, done(content, _files(tool, content)))
    return message
