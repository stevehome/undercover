"""Recording what the claim agent's tools do, as steps on the claim.

Each tool call is a step, named as the route names the tool: the Gateway's name
(`undercover-context___lookup_term`) on the Gateway route and the tool's own name
otherwise. A lookup in the context layer, a search of the memory and a refusal each
get a step of their own kind, so the claim page can show what the agent looked up,
where it came from and what was refused. The model gets a refusal to read, so the
claim's work goes on.
"""

import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any, cast

from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from agent import api
from agent.contexts import ClaimContext
from agent.refusals import Refusal
from agent.tools import TARGETS

Arguments = dict[str, Any]

LOOKUPS: dict[str, Callable[[Arguments], str]] = {
    "lookup_term": lambda a: f"Looked up the term {a['term']}",
    "describe_fields": lambda a: (
        f"Looked up the fields of a {a['record'].replace('_', ' ')}"
    ),
    "get_plan": lambda a: f"Looked up the {a['plan']} plan",
    "get_claim_rules": lambda _: "Looked up the claim rules",
    "search_reference_data": lambda a: f"Searched the reference data for {a['query']}",
    "search_documents": lambda a: f"Searched the documents for {a['query']}",
}


def _record_result(
    claim_id: str, tool: str, arguments: Arguments, message: ToolMessage
) -> None:
    """Record what a tool that answered did: a lookup, a memory search or a note."""
    content = str(message.content)
    if tool in LOOKUPS:
        files = json.loads(content)["sources"]
        api.record_step(claim_id, LOOKUPS[tool](arguments), "lookup", files=files)
    elif tool == "read_section":
        section = json.loads(content)
        name = arguments["document"].replace("_", " ")
        title = section["answer"]["title"]
        text = f"Read {name} section {arguments['number']}: {title}"
        api.record_step(claim_id, text, "lookup", files=section["sources"])
    elif tool == "search_memory":
        text = f"Searched the customer's memory for {arguments['query']}"
        api.record_step(claim_id, text, "memory_search", found=json.loads(content))
    elif tool == "get_claim":
        text = "Read the claim, its policy and the customer's claim history"
        api.record_step(claim_id, text)
    elif tool == "decide_claim":
        paid = (
            f" for ${Decimal(arguments['payout']):,.2f}"
            if arguments["decision"] == "approve"
            else ""
        )
        api.record_step(claim_id, f"Decided: {arguments['decision']}{paid}")


def record_tool_call(
    request: ToolCallRequest,
    execute: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
) -> ToolMessage | Command[Any]:
    """Run a tool and record it; a refusal is recorded and handed to the model."""
    context = cast(ClaimContext, request.runtime.context)
    tool = request.tool_call["name"]
    arguments = request.tool_call["args"]
    name = context.route.tool_name(TARGETS[tool], tool) if tool in TARGETS else tool
    api.record_step(context.claim_id, f"Called {name}", "tool_call", tool=name)
    try:
        message = execute(request)
    except Refusal as refusal:
        api.record_step(
            context.claim_id,
            refusal.message,
            "refusal",
            source=refusal.source,
            detail=refusal.detail,
        )
        return ToolMessage(
            content=refusal.message,
            name=tool,
            tool_call_id=request.tool_call["id"],
            status="error",
        )
    _record_result(context.claim_id, tool, arguments, cast(ToolMessage, message))
    return message
