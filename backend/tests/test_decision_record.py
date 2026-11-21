from decimal import Decimal

import pytest

from backend.tests import records

CLAIM = "CLM-1001"
DECISION = {
    "decision": "approve",
    "payout": "420.00",
    "reason": "A covered trip delay with receipts.",
    "policy_reference": "Section 3",
    "decided_by": "The test agent",
}


def post(client, claim_id=CLAIM, **changes):
    return client.post(f"/api/claims/{claim_id}/decision", json={**DECISION, **changes})


def message(response):
    assert response.status_code == 422
    return str(response.json()["detail"])


@pytest.mark.parametrize(
    ("changes", "missing"),
    [
        ({"reason": "  "}, "a reason in plain language"),
        ({"policy_reference": ""}, "the section relied on"),
        ({"decided_by": " "}, "who or what made the decision"),
    ],
)
def test_a_blank_part_is_refused_naming_section_14_and_what_is_missing(
    client, changes, missing
):
    detail = message(post(client, **changes))

    assert "Claims manual section 14" in detail
    assert missing in detail


@pytest.mark.parametrize(
    ("changes", "says"),
    [
        ({"payout": "0.00"}, "an approval needs a payout above zero"),
        ({"decision": "decline"}, "a decline or a referral pays nothing"),
        ({"decision": "refer"}, "a decline or a referral pays nothing"),
    ],
)
def test_a_payout_that_does_not_fit_the_decision_is_refused(client, changes, says):
    detail = message(post(client, **changes))

    assert "Claims manual section 14" in detail
    assert says in detail


def test_these_refusals_are_the_same_on_any_claim_including_one_that_is_not_there(
    client,
):
    on_a_claim = message(post(client, reason=""))
    on_no_claim = message(post(client, "CLM-9999", reason=""))

    assert on_a_claim == on_no_claim


def test_an_approval_with_no_calculation_on_file_is_refused(client):
    detail = message(post(client))

    assert "Claims manual section 14" in detail
    assert "calculation" in detail


def test_a_payout_that_is_not_the_calculations_is_refused(client):
    records.calculate(client, CLAIM, "300.00")

    detail = message(post(client, payout="420.00"))

    assert "Claims manual section 14" in detail
    assert "300.00" in detail


def test_the_latest_calculation_is_the_one_a_decision_rests_on(client):
    records.calculate(client, CLAIM, "300.00")
    records.calculate(client, CLAIM, "420.00")

    assert post(client).status_code == 200


def test_a_calculation_does_not_carry_to_a_claim_worked_afresh(client):
    records.calculate(client, CLAIM, "420.00")
    client.post(f"/api/claims/{CLAIM}/requeue")

    assert "calculation" in message(post(client))

    records.calculate(client, CLAIM, "420.00")
    assert post(client).status_code == 200


def test_a_complete_approval_holds_its_calculation_maker_time_and_manual_version(
    client,
):
    records.calculate(client, CLAIM, "420.00")
    post(client)

    claim = client.get(f"/api/claims/{CLAIM}").json()

    assert claim["decided_by"] == "The test agent"
    assert claim["decided_on"]
    assert claim["manual_version"] == "2026.2"
    steps = claim["calculation"]
    assert steps
    assert all(set(step) == {"step", "amount"} for step in steps)
    assert sum((Decimal(s["amount"]) for s in steps), Decimal(0)) == Decimal("420.00")
    assert claim["payout"] == "420.00"


def test_a_decline_holds_its_maker_and_manual_version_but_no_calculation(client):
    post(client, decision="decline", payout="0.00")

    claim = client.get(f"/api/claims/{CLAIM}").json()

    assert claim["calculation"] is None
    assert claim["decided_by"] == "The test agent"
    assert claim["manual_version"] == "2026.2"


def test_a_signed_off_payout_adds_who_signed_off_and_when(client):
    records.calculate(client, CLAIM, "1200.00")
    post(client, payout="1200.00")

    client.post(f"/api/claims/{CLAIM}/sign-off")

    claim = client.get(f"/api/claims/{CLAIM}").json()
    assert claim["signed_off_by"] == "HND-01"
    assert claim["signed_off_on"]
    assert claim["decided_by"] == "The test agent"


def test_a_calculation_is_worked_out_for_the_claim_it_is_asked_on(client):
    request = {
        "benefit": "emergency_medical",
        "lines": [
            {
                "description": "Bill",
                "amount": "1000.00",
                "quantity": 1,
                "kind": "expense",
                "nights": 0,
                "hours": 0,
            }
        ],
        "paid_by_others": "0.00",
    }

    worked = client.post(f"/api/claims/{CLAIM}/payout", json=request)

    assert worked.status_code == 200
    assert worked.json()["payout"] == "950.00"
    missing = client.post("/api/claims/CLM-9999/payout", json=request)
    assert missing.status_code == 404
