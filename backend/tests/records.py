"""Recording a decision as the agent does: its calculation on file first.

Claims manual section 14 wants every approval to rest on a calculation and to say
who made it, so a test that records one goes through here.
"""

from decimal import Decimal

PROBE = "1000.00"
MAKER = "A test agent"


def _calculation(amount):
    line = {
        "description": "Expense",
        "amount": str(amount),
        "quantity": 1,
        "kind": "expense",
        "nights": 0,
        "hours": 0,
    }
    return {"benefit": "emergency_medical", "lines": [line], "paid_by_others": "0.00"}


def calculate(client, claim_id, payout):
    """Put a calculation on file for a claim whose payout is `payout`.

    One expense line under emergency_medical for the payout plus the plan's
    deductible, which a first calculation of a larger amount shows.
    """
    url = f"/api/claims/{claim_id}/payout"
    probe = client.post(url, json=_calculation(PROBE)).json()
    deductible = Decimal(PROBE) - Decimal(probe["payout"])
    client.post(url, json=_calculation(Decimal(str(payout)) + deductible))


def decide(client, claim_id, body, decided_by=MAKER):
    """Record a decision: an approval's calculation first, then the decision."""
    if body["decision"] == "approve":
        calculate(client, claim_id, body["payout"])
    return client.post(
        f"/api/claims/{claim_id}/decision", json={"decided_by": decided_by, **body}
    )
