from decimal import Decimal

from agent import agents, api
from agent.tests import records


def test_decide_claim_reads_then_decides(backend, script, saver):
    records.calculated("CLM-1001", "420.00")
    llm = script(
        ("get_claim", {}),
        ("search_documents", {"query": "trip delay"}),
        ("read_section", {"document": "policy_wording", "number": 3}),
        ("read_section", {"document": "claims_manual", "number": 9}),
        (
            "decide_claim",
            {
                "decision": "approve",
                "payout": "420.00",
                "reason": "Routine trip delay with receipts.",
                "policy_reference": "Section 3",
            },
        ),
        "Approved the claim for $420.00.",
    )

    assert (
        agents.decide_claim("CLM-1001", llm, saver) == "Approved the claim for $420.00."
    )

    claim = api.get_claim("CLM-1001")
    assert claim["status"] == "decided"
    assert claim["decision"] == "approve"
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [step["text"] for step in steps] == [
        "Security check: no instructions found",
        "Read the claim, its policy and the customer's claim history",
        "Searched the documents for trip delay",
        "Read policy wording section 3: Trip Delay",
        "Read claims manual section 9: Repeat claims",
        "Decided: approve for $420.00",
        "Paid $420.00",
    ]
    assert claim["paid_amount"] == "420.00"


def test_payout_comes_from_the_payout_tool(backend, script, saver):
    line = {"description": "Hotel", "amount": "900.00", "kind": "hotel", "nights": 2}
    llm = script(
        ("get_claim", {}),
        (
            "calculate_payout",
            {
                "benefit": "trip_delay",
                "lines": [line],
                "paid_by_others": "0.00",
            },
        ),
        (
            "decide_claim",
            {
                "decision": "approve",
                "payout": "700.00",
                "reason": "Hotel limited to two nights.",
                "policy_reference": "Section 10",
            },
        ),
        "Approved.",
    )

    agents.decide_claim("CLM-1001", llm, saver)

    assert api.get_claim("CLM-1001")["payout"] == "700.00"
    assert (
        api.calculate_payout("CLM-1001", "trip_delay", [api.Line(**line)], Decimal(0))[
            "payout"
        ]
        == "700.00"
    )
