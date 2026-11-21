"""A claim's calculation on file, as the agent's payout tool leaves it.

Claims manual section 14 wants every approval to rest on a calculation, so a test
that approves a claim without running the payout tool puts one on file first.
"""

from decimal import Decimal
from typing import Any

from agent import api
from backend import calculations, claims

MAKER = "A test agent"


def calculated(claim_id: str, payout: str | Decimal) -> None:
    """Keep a calculation for the claim's current attempt whose payout is `payout`."""
    thread = claims.get_row(claim_id)["thread"]
    amount = Decimal(payout)
    calculation = {
        "calculation": [{"step": "An expense", "amount": amount}],
        "payout": amount,
    }
    calculations.keep(claim_id, thread, calculation)


def decide(claim_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Record a decision through the agent's client, with its calculation and maker."""
    if fields["decision"] == "approve":
        calculated(claim_id, fields["payout"])
    return api.decide_claim(claim_id, decided_by=MAKER, **fields)


def step_texts(backend: Any, claim_id: str, *, calls: bool = False) -> list[str]:
    """The texts of a claim's steps, without its tool calls unless `calls` is set."""
    steps = backend.get(f"/api/claims/{claim_id}/steps").json()
    return [s["text"] for s in steps if calls or s["kind"] != "tool_call"]
