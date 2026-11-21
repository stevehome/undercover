"""Everything the agents can do: one tool for each thing they may do.

Tools get their state from the run's context, never from closures or globals. The
claim agent's tools take no id from the model: they fill in the claim and its
policy, so the model acts only on its own claim.
"""

from decimal import Decimal
from typing import Any

from langchain.tools import ToolRuntime, tool

from agent import api
from agent.api import Amount, Benefit, Decision, Document, Line
from agent.claim_text import claim_text
from agent.contexts import ClaimContext
from agent.tool_route import APP


@tool
def get_claim(runtime: ToolRuntime[ClaimContext]) -> str:
    """Read the claim, its policy, and the customer's claim history."""
    context = runtime.context
    claim = context.route.call(APP, "get_claim", {"claim_id": context.claim_id})
    api.record_step(
        context.claim_id, "Read the claim, its policy and the customer's claim history"
    )
    return claim_text(claim)


@tool
def list_sections(document: Document, runtime: ToolRuntime[ClaimContext]) -> list[str]:
    """List the section headings of the policy wording or the claims manual."""
    return runtime.context.route.call(APP, "list_sections", {"document": document})


@tool
def read_section(
    document: Document, heading: str, runtime: ToolRuntime[ClaimContext]
) -> str:
    """Read one section of the policy wording or the claims manual."""
    context = runtime.context
    section = context.route.call(
        APP, "get_section", {"document": document, "heading": heading}
    )
    name = document.replace("_", " ")
    api.record_step(context.claim_id, f"Read {name} section: {heading}")
    return section["text"]


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
        "policy_id": context.policy_id,
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
    }
    context.route.call(APP, "decide_claim", arguments)
    detail = f" for ${payout:,.2f}" if decision == "approve" else ""
    api.record_step(context.claim_id, f"Decided: {decision}{detail}")
    return "Recorded"


CLAIM_TOOLS = [get_claim, list_sections, read_section, calculate_payout, decide_claim]
