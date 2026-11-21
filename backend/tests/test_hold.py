CLAIM = "CLM-1001"
APPROVAL = {
    "decision": "approve",
    "payout": "420.00",
    "reason": "Stubbed.",
    "policy_reference": "Section 3",
}
HOLD = {"reason": "gateway"}


def approve(client, claim_id=CLAIM):
    client.post(f"/api/claims/{claim_id}/decision", json=APPROVAL)


def hold(client, claim_id=CLAIM, body=HOLD):
    return client.post(f"/api/claims/{claim_id}/hold", json=body)


def test_an_approved_unpaid_claim_is_held_for_a_sign_off(agent):
    approve(agent)

    held = hold(agent)

    assert held.status_code == 200
    assert held.json()["status"] == "waiting for sign-off"
    assert held.json()["hold_reason"] == "gateway"
    assert held.json()["over_approval_limit"] == 1


def test_a_hold_repeated_is_done_not_an_error(agent):
    approve(agent)
    hold(agent)

    assert hold(agent).status_code == 200


def test_a_sign_off_pays_a_held_claim_once_with_the_handler_and_the_time(client):
    approve(client)
    hold(client)

    paid = client.post(f"/api/claims/{CLAIM}/sign-off").json()

    assert paid["status"] == "decided"
    assert paid["paid_amount"] == "420.00"
    assert paid["signed_off_by"] == "HND-01"
    assert paid["signed_off_on"]
    assert paid["paid_on"]
    assert client.post(f"/api/claims/{CLAIM}/sign-off").json() == paid


def test_the_agent_cannot_pay_a_held_claim(agent):
    approve(agent)
    hold(agent)

    refused = agent.post(f"/api/claims/{CLAIM}/payment", json={"amount": "420.00"})

    assert refused.status_code == 409
    assert "sign-off" in refused.json()["detail"]


def test_a_claim_not_yet_decided_is_not_held(agent):
    assert hold(agent).status_code == 409


def test_a_claim_that_is_not_an_approval_is_not_held(agent):
    refer = {**APPROVAL, "decision": "refer", "payout": "0.00"}
    agent.post(f"/api/claims/{CLAIM}/decision", json=refer)

    assert hold(agent).status_code == 409


def test_a_paid_claim_is_not_held(agent):
    approve(agent)
    agent.post(f"/api/claims/{CLAIM}/payment", json={"amount": "420.00"})

    assert hold(agent).status_code == 409


def test_the_only_reason_is_the_gateway(agent):
    approve(agent)

    assert hold(agent, body={"reason": "because"}).status_code == 422


def test_a_handlers_sign_in_cannot_hold_a_claim(anonymous, as_handler):
    response = anonymous.post(
        f"/api/claims/{CLAIM}/hold", json=HOLD, headers=as_handler()
    )

    assert response.status_code == 401


def test_the_hold_is_not_one_of_the_agents_tools(agent):
    document = agent.get("/api/agent/openapi.json").json()
    ids = {
        op["operationId"] for path in document["paths"].values() for op in path.values()
    }

    assert "hold_for_sign_off" not in ids
