"""Everything the agents can do: one tool for each thing they may do.

Tools get their state from the run's context, never from closures or globals. The
claim agent's tools take no id from the model: they fill in the claim and who
makes the decision, so the model acts only on its own claim.
"""

from decimal import Decimal
from typing import Any, Literal

from langchain.tools import ToolRuntime, tool

from agent import api
from agent.api import Amount, Benefit, Decision, Line
from agent.claim_text import claim_text
from agent.contexts import ClaimContext
from agent.tool_route import APP, CONTEXT

Document = Literal["policy_wording", "claims_manual"]
Record = Literal["claim", "policy", "previous_claim"]
Plan = Literal["economy", "premium", "first"]


@tool
def get_claim(runtime: ToolRuntime[ClaimContext]) -> str:
    """Read the claim, its policy, and the customer's claim history."""
    context = runtime.context
    claim = context.route.call(APP, "get_claim", {"claim_id": context.claim_id})
    api.record_step(
        context.claim_id, "Read the claim, its policy and the customer's claim history"
    )
    return claim_text(claim)


def _look_up(
    runtime: ToolRuntime[ClaimContext],
    operation: str,
    arguments: dict[str, Any],
    step: str,
) -> dict[str, Any]:
    """Ask the context layer, and record on the claim what was looked up."""
    context = runtime.context
    answer = context.route.call(CONTEXT, operation, arguments)
    api.record_step(context.claim_id, step)
    return answer


@tool
def lookup_term(term: str, runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Look up a term the policy wording defines, with the sections it comes from."""
    return _look_up(
        runtime, "lookup_term", {"term": term}, f"Looked up the term {term}"
    )


@tool
def describe_fields(
    record: Record, runtime: ToolRuntime[ClaimContext]
) -> dict[str, Any]:
    """Say what each field of a claim, a policy or a previous claim means."""
    step = f"Looked up the fields of a {record.replace('_', ' ')}"
    return _look_up(runtime, "describe_fields", {"record": record}, step)


@tool
def get_plan(plan: Plan, runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Get one plan's limits, waiting periods and deductible, and the add-ons."""
    return _look_up(runtime, "get_plan", {"plan": plan}, f"Looked up the {plan} plan")


@tool
def get_claim_rules(runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Get the rules claims operations applies to every claim."""
    return _look_up(runtime, "get_claim_rules", {}, "Looked up the claim rules")


@tool
def search_reference_data(
    query: str, runtime: ToolRuntime[ClaimContext]
) -> dict[str, Any]:
    """Search outside facts, such as storms, strikes and prices, for every word."""
    step = f"Searched the reference data for {query}"
    return _look_up(runtime, "search_reference_data", {"query": query}, step)


@tool
def search_documents(query: str, runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Search the policy wording and the claims manual for sections with every word."""
    step = f"Searched the documents for {query}"
    return _look_up(runtime, "search_documents", {"query": query}, step)


@tool
def read_section(
    document: Document, number: int, runtime: ToolRuntime[ClaimContext]
) -> dict[str, Any]:
    """Read one numbered section of the policy wording or the claims manual."""
    arguments = {"document": document, "number": number}
    name = document.replace("_", " ")
    section = runtime.context.route.call(CONTEXT, "read_section", arguments)
    title = section["answer"]["title"]
    api.record_step(runtime.context.claim_id, f"Read {name} section {number}: {title}")
    return section


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
    detail = f" for ${payout:,.2f}" if decision == "approve" else ""
    api.record_step(context.claim_id, f"Decided: {decision}{detail}")
    return "Recorded"


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
