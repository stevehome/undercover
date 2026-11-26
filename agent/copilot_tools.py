"""Everything the Copilot can do: one tool for each thing it may look at or do.

Tools get their state from the turn's context, never from closures or globals, and
call the app as the handler through `copilot_api`. The context layer's seven lookups
are the claim agent's own, by name and arguments, written again here because a
tool's runtime is typed to its context; they reach the context layer through the
context-only route. They record nothing: `copilot_recording.py` records what each
tool call did.
"""

from typing import Any

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool

from agent import copilot_api
from agent.copilot_api import CardKind, EvalSet
from agent.copilot_context import CopilotContext
from agent.tool_route import CONTEXT
from agent.tools import TARGETS as CONTEXT_TARGETS
from agent.tools import Document, Plan, Record

AGENTS_SETTING = "improver_agents_at_once"

KINDS: dict[str, CardKind] = {
    "list_claims": "claims",
    "get_claim": "claims",
    "get_claim_steps": "claims",
    "what_needs_a_handler": "claims",
    "find_customers": "customers",
    "get_customer": "customers",
    "get_policy": "customers",
    "get_latest_dispatch": "agent work",
    "list_evaluations": "agent work",
    "get_settings": "agent work",
    "start_dispatch": "action",
    "start_evaluation": "action",
    "send_back_claim": "action",
    **{
        name: "context" for name, target in CONTEXT_TARGETS.items() if target == CONTEXT
    },
}
"""The kind of card each tool gets in the sidebar."""


def _agents(runtime: ToolRuntime[CopilotContext], asked: int | None) -> int:
    """The number of claim agents asked for, else the one in our settings."""
    if asked is not None:
        return asked
    settings = copilot_api.settings(runtime.context.sign_in)
    return next(s["value"] for s in settings if s["key"] == AGENTS_SETTING)


@tool
def list_claims(runtime: ToolRuntime[CopilotContext]) -> list[dict[str, Any]]:
    """List every claim in the queue with where it stands, oldest submitted first."""
    return copilot_api.list_claims(runtime.context.sign_in)


@tool
def get_claim(claim_id: str, runtime: ToolRuntime[CopilotContext]) -> dict[str, Any]:
    """Read a claim in full: its decision, payout and reason, its policy, its
    customer's earlier claims and any decision sent back with its note."""
    return copilot_api.get_claim(runtime.context.sign_in, claim_id)


@tool
def get_claim_steps(
    claim_id: str, runtime: ToolRuntime[CopilotContext]
) -> list[dict[str, Any]]:
    """Read the steps the claim agent took on a claim, in order."""
    return copilot_api.claim_steps(runtime.context.sign_in, claim_id)


@tool
def what_needs_a_handler(runtime: ToolRuntime[CopilotContext]) -> dict[str, Any]:
    """List the payouts held for sign-off, the claims the agent referred or left for
    a handler, and the sent-back claims the agent hasn't worked yet."""
    return copilot_api.what_needs_a_handler(runtime.context.sign_in)


@tool
def find_customers(
    name: str, runtime: ToolRuntime[CopilotContext]
) -> list[dict[str, Any]]:
    """Find customers whose name holds this text, in any case."""
    return copilot_api.find_customers(runtime.context.sign_in, name)


@tool
def get_customer(
    customer_id: str, runtime: ToolRuntime[CopilotContext]
) -> dict[str, Any]:
    """Read a customer: their policies, earlier claims and claims in our queue."""
    return copilot_api.get_customer(runtime.context.sign_in, customer_id)


@tool
def get_policy(policy_id: str, runtime: ToolRuntime[CopilotContext]) -> dict[str, Any]:
    """Read a policy with the limits of its plan."""
    return copilot_api.get_policy(runtime.context.sign_in, policy_id)


@tool
def get_latest_dispatch(runtime: ToolRuntime[CopilotContext]) -> dict[str, Any] | None:
    """Read the most recently started run with its claims and its summary."""
    return copilot_api.latest_dispatch(runtime.context.sign_in)


@tool
def list_evaluations(runtime: ToolRuntime[CopilotContext]) -> list[dict[str, Any]]:
    """List the evaluations, newest first, with their measures and cost."""
    return copilot_api.evaluations(runtime.context.sign_in)


@tool
def get_settings(runtime: ToolRuntime[CopilotContext]) -> list[dict[str, Any]]:
    """Read our settings: the approval limit, the objectives and the rest."""
    return copilot_api.settings(runtime.context.sign_in)


def _look_up(
    runtime: ToolRuntime[CopilotContext], operation: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Ask the context layer, on the context-only route."""
    return runtime.context.route.call(CONTEXT, operation, arguments)


@tool
def lookup_term(term: str, runtime: ToolRuntime[CopilotContext]) -> dict[str, Any]:
    """Look up a term the policy wording defines, with the sections it comes from."""
    return _look_up(runtime, "lookup_term", {"term": term})


@tool
def describe_fields(
    record: Record, runtime: ToolRuntime[CopilotContext]
) -> dict[str, Any]:
    """Say what each field of a claim, a policy or a previous claim means."""
    return _look_up(runtime, "describe_fields", {"record": record})


@tool
def get_plan(plan: Plan, runtime: ToolRuntime[CopilotContext]) -> dict[str, Any]:
    """Get one plan's limits, waiting periods and deductible, and the add-ons."""
    return _look_up(runtime, "get_plan", {"plan": plan})


@tool
def get_claim_rules(runtime: ToolRuntime[CopilotContext]) -> dict[str, Any]:
    """Get the rules claims operations applies to every claim."""
    return _look_up(runtime, "get_claim_rules", {})


@tool
def search_reference_data(
    query: str, runtime: ToolRuntime[CopilotContext]
) -> dict[str, Any]:
    """Search outside facts, such as storms, strikes and prices, for every word."""
    return _look_up(runtime, "search_reference_data", {"query": query})


@tool
def search_documents(
    query: str, runtime: ToolRuntime[CopilotContext]
) -> dict[str, Any]:
    """Search the policy wording and the claims manual for sections with every word."""
    return _look_up(runtime, "search_documents", {"query": query})


@tool
def read_section(
    document: Document, number: int, runtime: ToolRuntime[CopilotContext]
) -> dict[str, Any]:
    """Read one numbered section of the policy wording or the claims manual."""
    return _look_up(runtime, "read_section", {"document": document, "number": number})


@tool
def start_dispatch(
    runtime: ToolRuntime[CopilotContext], agents: int | None = None
) -> dict[str, Any]:
    """Start a dispatch of the whole queue.

    agents: how many claim agents work at once; leave it out for the number in our
    settings.
    """
    count = _agents(runtime, agents)
    started = copilot_api.start_dispatch(runtime.context.sign_in, count)
    return {**started, "agents": count}


@tool
def start_evaluation(
    eval_set: EvalSet,
    runtime: ToolRuntime[CopilotContext],
    tiny: bool = False,
    agents: int | None = None,
) -> dict[str, Any]:
    """Start an evaluation of the claim agent on a labeled set.

    eval_set: `evaluation` or `held_out`.
    tiny: only the set's five tiny claims, not the whole set.
    agents: how many claim agents work at once; leave it out for the number in our
    settings.
    """
    count = _agents(runtime, agents)
    started = copilot_api.start_evaluation(
        runtime.context.sign_in, count, eval_set, tiny
    )
    return {**started, "agents": count}


@tool
def send_back_claim(
    claim_id: str, note: str, runtime: ToolRuntime[CopilotContext]
) -> dict[str, Any]:
    """Send a claim waiting for sign-off back to the claim agent with a note."""
    return copilot_api.send_back_claim(runtime.context.sign_in, claim_id, note)


COPILOT_TOOLS: list[BaseTool] = [
    list_claims,
    get_claim,
    get_claim_steps,
    what_needs_a_handler,
    find_customers,
    get_customer,
    get_policy,
    get_latest_dispatch,
    list_evaluations,
    get_settings,
    lookup_term,
    describe_fields,
    get_plan,
    get_claim_rules,
    search_reference_data,
    search_documents,
    read_section,
    start_dispatch,
    start_evaluation,
    send_back_claim,
]
