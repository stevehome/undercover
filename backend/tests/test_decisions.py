import pytest

from backend import claims
from backend.errors import Conflict
from backend.tests import records


def decide(client, payout, decision="approve"):
    return decide_other(client, "CLM-1001", payout, decision)


def decide_other(client, claim_id, payout, decision="approve"):
    body = {
        "decision": decision,
        "payout": payout,
        "reason": "Stubbed.",
        "policy_reference": "Section 3",
    }
    return records.decide(client, claim_id, body)


def pay(client, amount):
    return client.post("/api/claims/CLM-1001/payment", json={"amount": amount})


def test_approve_within_limit_is_decided(client):
    response = records.decide(
        client,
        "CLM-1001",
        {
            "decision": "approve",
            "payout": "420.00",
            "reason": "Routine trip delay with receipts.",
            "policy_reference": "Section 3",
        },
    )
    assert response.status_code == 200
    claim = response.json()
    assert claim["status"] == "decided"
    assert claim["over_approval_limit"] == 0


def test_approve_over_limit_waits_for_sign_off(client):
    claim = decide(client, "1200.00").json()
    assert claim["status"] == "waiting for sign-off"
    assert claim["over_approval_limit"] == 1

    assert pay(client, "1200.00").status_code == 403


def test_a_sign_off_pays_the_claim_in_one_request(client):
    decide(client, "1200.00")

    signed = client.post("/api/claims/CLM-1001/sign-off")

    assert signed.status_code == 200
    claim = signed.json()
    assert claim["status"] == "decided"
    assert claim["signed_off_by"] == "HND-01"
    assert claim["paid_amount"] == "1200.00"
    assert claim["paid_on"] == claim["signed_off_on"]


def test_signing_off_again_pays_nothing_twice(client):
    decide(client, "1200.00")
    first = client.post("/api/claims/CLM-1001/sign-off").json()

    again = client.post("/api/claims/CLM-1001/sign-off")

    assert again.status_code == 200
    assert again.json()["paid_on"] == first["paid_on"]
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [step["text"] for step in steps].count("Paid $1200.00") == 1


def test_another_handler_cannot_sign_off_a_claim_already_paid(client):
    decide(client, "1200.00")
    client.post("/api/claims/CLM-1001/sign-off")

    with pytest.raises(Conflict):
        claims.sign_off("CLM-1001", "HND-02")


def test_a_payment_over_the_limit_is_refused_before_the_claim_is_looked_at(client):
    refused = pay(client, "1000.01")

    assert refused.status_code == 403
    assert "1000.00" in refused.json()["detail"]


def test_a_payment_at_the_limit_gets_the_claims_own_answer(client):
    assert pay(client, "1000.00").status_code == 409


def test_the_limit_is_the_current_setting(client):
    client.post("/api/settings/payout_approval_limit", json={"value": "300"})

    assert pay(client, "400.00").status_code == 403


def test_sign_off_when_not_waiting_is_blocked(client):
    response = client.post("/api/claims/CLM-1001/sign-off")
    assert response.status_code == 409


def test_pay_without_decision_is_blocked(client):
    response = client.post("/api/claims/CLM-1001/payment", json={"amount": "100.00"})
    assert response.status_code == 409


def test_decline_is_decided_and_unpayable(client):
    records.decide(
        client,
        "CLM-1001",
        {
            "decision": "decline",
            "payout": "0.00",
            "reason": "Not a covered reason.",
            "policy_reference": "Section 2",
        },
    )
    payment = client.post("/api/claims/CLM-1001/payment", json={"amount": "100.00"})
    assert payment.status_code == 409


def test_a_decided_claim_cannot_be_decided_again(client):
    decide(client, "420.00")

    response = decide(client, "999.00")

    assert response.status_code == 409
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["payout"] == "420.00"


def test_the_same_payment_twice_is_done_once(client):
    decide(client, "420.00")
    first = pay(client, "420.00").json()

    second = pay(client, "420.00")

    assert second.status_code == 200
    assert second.json()["paid_on"] == first["paid_on"]


def test_a_different_payment_on_a_paid_claim_is_refused(client):
    decide(client, "420.00")
    pay(client, "420.00")

    response = pay(client, "421.00")

    assert response.status_code == 409
    assert "already been paid" in response.json()["detail"]


def test_the_same_decision_twice_is_done_once(client):
    first = decide(client, "420.00").json()

    second = decide(client, "420.00")

    assert second.status_code == 200
    assert second.json()["decided_on"] == first["decided_on"]


def test_a_signed_off_claim_cannot_be_decided_differently(client):
    decide(client, "1200.00")
    client.post("/api/claims/CLM-1001/sign-off")

    assert decide(client, "1100.00").status_code == 409
    assert decide(client, "0.00", decision="decline").status_code == 409


def test_the_same_sign_off_twice_is_done_once(client):
    decide(client, "1200.00")
    first = client.post("/api/claims/CLM-1001/sign-off").json()

    second = client.post("/api/claims/CLM-1001/sign-off")

    assert second.status_code == 200
    assert second.json()["signed_off_on"] == first["signed_off_on"]


def test_payment_must_equal_the_approved_payout(client):
    decide(client, "420.00")

    response = pay(client, "421.00")

    assert response.status_code == 409
    assert client.get("/api/claims/CLM-1001").json()["paid_amount"] is None


def test_amounts_are_exact_to_the_cent(client):
    claim = decide(client, "0.10").json()
    assert claim["payout"] == "0.10"
    assert pay(client, "0.10").json()["paid_amount"] == "0.10"


@pytest.mark.parametrize("amount", ["-1.00", "1.005", "abc"])
def test_malformed_amounts_are_rejected(client, amount):
    body = {
        "decision": "approve",
        "payout": amount,
        "reason": "Stubbed.",
        "policy_reference": "Section 3",
        "decided_by": "A test agent",
    }

    assert client.post("/api/claims/CLM-1001/decision", json=body).status_code == 422


def test_record_step_moves_claim_in_progress_and_lists_in_order(client):
    client.post(
        "/api/claims/CLM-1001/steps",
        json={"kind": "note", "text": "Read the claim and policy", "details": {}},
    )
    client.post(
        "/api/claims/CLM-1001/steps",
        json={"kind": "note", "text": "Read the policy wording", "details": {}},
    )

    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "in progress"

    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [step["text"] for step in steps] == [
        "Read the claim and policy",
        "Read the policy wording",
    ]


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_only_an_approval_has_a_payout(client, decision):
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": decision,
            "payout": "50.00",
            "reason": "r",
            "policy_reference": "s",
            "decided_by": "A test agent",
        },
    )

    assert response.status_code == 422
