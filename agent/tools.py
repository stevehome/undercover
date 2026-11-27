"""Everything the agents can do: one tool for each thing they may do.

Tools get their state from the run's context, never from closures or globals. The
claim agent's tools take no id from the model: they fill in the claim and who
makes the decision, so the model acts only on its own claim. They record nothing:
`step_recording.py` records what each tool call did.
"""

from decimal import Decimal
from typing import Any, Literal, cast

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool

from agent.api import Amount, Benefit, Decision, Line
from agent.claim_text import claim_text
from agent.contexts import ClaimContext
from agent.memory import CustomerMemory
from agent.tool_route import APP, CONTEXT

Document = Literal["policy_wording", "claims_manual"]
Record = Literal["claim", "policy", "previous_claim", "customer_appeal", "appeal"]
Plan = Literal["economy", "premium", "first"]

TARGETS = {
    "get_claim": APP,
    "calculate_payout": APP,
    "decide_claim": APP,
    "lookup_term": CONTEXT,
    "describe_fields": CONTEXT,
    "get_plan": CONTEXT,
    "get_claim_rules": CONTEXT,
    "search_reference_data": CONTEXT,
    "search_documents": CONTEXT,
    "read_section": CONTEXT,
}
"""The service each of the model's tools reaches; the memory search reaches neither."""


@tool
def get_claim(runtime: ToolRuntime[ClaimContext]) -> str:
    """Read the claim, its policy, and the customer's claim history."""
    context = runtime.context
    claim = context.route.call(APP, "get_claim", {"claim_id": context.claim_id})
    return claim_text(claim)


def _look_up(
    runtime: ToolRuntime[ClaimContext], operation: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Ask the context layer."""
    return runtime.context.route.call(CONTEXT, operation, arguments)


@tool
def lookup_term(term: str, runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Look up a term the policy wording defines, with the sections it comes from."""
    return _look_up(runtime, "lookup_term", {"term": term})


@tool
def describe_fields(
    record: Record, runtime: ToolRuntime[ClaimContext]
) -> dict[str, Any]:
    """Say what each field of a claim, a policy or a previous claim means."""
    return _look_up(runtime, "describe_fields", {"record": record})


@tool
def get_plan(plan: Plan, runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Get one plan's limits, waiting periods and deductible, and the add-ons."""
    return _look_up(runtime, "get_plan", {"plan": plan})


@tool
def get_claim_rules(runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Get the rules claims operations applies to every claim."""
    return _look_up(runtime, "get_claim_rules", {})


@tool
def search_reference_data(
    query: str, runtime: ToolRuntime[ClaimContext]
) -> dict[str, Any]:
    """Search outside facts, such as storms, strikes and prices, for every word."""
    return _look_up(runtime, "search_reference_data", {"query": query})


@tool
def search_documents(query: str, runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Search the policy wording and the claims manual for sections with every word."""
    return _look_up(runtime, "search_documents", {"query": query})


@tool
def read_section(
    document: Document, number: int, runtime: ToolRuntime[ClaimContext]
) -> dict[str, Any]:
    """Read one numbered section of the policy wording or the claims manual."""
    arguments = {"document": document, "number": number}
    return _look_up(runtime, "read_section", arguments)


@tool
def calculate_payout(
    benefit: Benefit,
    lines: list[Line],
    runtime: ToolRuntime[ClaimContext],
    paid_by_others: Amount = Decimal(0),
) -> dict[str, Any]:
    """Work out the payout on an approved claim with UnderCover's payout rules.

    lines: the covered items and expenses, one for each line of the claim, with
    any excluded ones left out. A pair or a set counts as one item.
    paid_by_others: anything a carrier, hotel or other party has paid or refunded
    for the same loss.
    Returns the calculation, the payout and whether it needs sign-off.
    """
    context = runtime.context
    arguments = {
        "claim_id": context.claim_id,
        "benefit": benefit,
        "lines": lines,
        "paid_by_others": paid_by_others,
    }
    return context.route.call(APP, "calculate_payout", arguments)


@tool
def decide_claim(
    decision: Decision,
    payout: Amount,
    reason: str,
    policy_reference: str,
    runtime: ToolRuntime[ClaimContext],
) -> str:
    """Decide the claim: approve, decline, or refer, with its payout and reason."""
    context = runtime.context
    arguments = {
        "claim_id": context.claim_id,
        "decision": decision,
        "payout": payout,
        "reason": reason,
        "policy_reference": policy_reference,
        "decided_by": context.decided_by,
    }
    context.route.call(APP, "decide_claim", arguments)
    return "Recorded"


@tool
def search_memory(query: str, runtime: ToolRuntime[ClaimContext]) -> list[str]:
    """Search what we remember about this claim's customer from their earlier claims."""
    context = runtime.context
    memory = cast(CustomerMemory, context.memory)  # only offered when memory is on
    return memory.search(context.customer_id, query, context.claim_id)


CLAIM_TOOLS = [
    get_claim,
    lookup_term,
    describe_fields,
    get_plan,
    get_claim_rules,
    search_reference_data,
    search_documents,
    read_section,
    calculate_payout,
    decide_claim,
]


def claim_tools(memory: bool) -> list[BaseTool]:
    """Return the claim agent's tools, with a memory search only when memory is on."""
    return [*CLAIM_TOOLS, search_memory] if memory else CLAIM_TOOLS
