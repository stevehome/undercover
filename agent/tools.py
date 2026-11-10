"""Everything the agents can do: one tool for each thing they may do.

Tools get their state from the run's context, never from closures or globals.
"""

from decimal import Decimal
from typing import Any

from langchain.tools import ToolRuntime, tool

from agent import api
from agent.api import Amount, Benefit, Decision, Document, Line
from agent.contexts import ClaimContext


@tool
def get_claim(runtime: ToolRuntime[ClaimContext]) -> dict[str, Any]:
    """Read the claim, its policy, and the customer's claim history."""
    claim_id = runtime.context.claim_id
    claim = api.get_claim(claim_id)
    api.record_step(
        claim_id, "Read the claim, its policy and the customer's claim history"
    )
    return claim


@tool
def list_sections(document: Document) -> list[str]:
    """List the section headings of the policy wording or the claims manual."""
    return api.list_sections(document)


@tool
def read_section(
    document: Document, heading: str, runtime: ToolRuntime[ClaimContext]
) -> str:
    """Read one section of the policy wording or the claims manual."""
    text = api.get_section(document, heading)
    name = document.replace("_", " ")
    api.record_step(runtime.context.claim_id, f"Read {name} section: {heading}")
    return text


@tool
def calculate_payout(
    policy_id: str,
    benefit: Benefit,
    lines: list[Line],
    paid_by_others: Amount = Decimal(0),
) -> dict[str, Any]:
    """Work out the payout on an approved claim with UnderCover's payout rules.

    lines: the covered items and expenses, one for each line of the claim, with
    any excluded ones left out. A pair or a set counts as one item.
    paid_by_others: anything a carrier, hotel or other party has paid or refunded
    for the same loss.
    Returns the calculation, the payout and whether it needs sign-off.
    """
    return api.calculate_payout(policy_id, benefit, lines, paid_by_others)


@tool
def decide_claim(
    decision: Decision,
    payout: Amount,
    reason: str,
    policy_reference: str,
    runtime: ToolRuntime[ClaimContext],
) -> str:
    """Decide the claim: approve, decline, or refer, with its payout and reason."""
    claim_id = runtime.context.claim_id
    api.decide_claim(claim_id, decision, payout, reason, policy_reference)
    detail = f" for ${payout:,.2f}" if decision == "approve" else ""
    api.record_step(claim_id, f"Decided: {decision}{detail}")
    return "Recorded"


CLAIM_TOOLS = [get_claim, list_sections, read_section, calculate_payout, decide_claim]
