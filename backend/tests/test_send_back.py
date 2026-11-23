import threading

import pytest

from backend.tests.test_decisions import decide

CLAIM = "CLM-1001"
SEND = f"/api/claims/{CLAIM}/send-back"
NOTE = {"note": "The receipts don't match the dates."}
MARCUS = "marcus.oyelaran@undercover.example"
SETTINGS = {
    "model": "stub/model",
    "reasoning_effort": "low",
    "configuration_version": 1,
}


def waiting(client, payout="1200.00"):
    decide(client, payout)


def test_a_senior_handler_sends_an_approval_back_with_a_note(client):
    waiting(client)

    sent = client.post(SEND, json=NOTE)

    assert sent.status_code == 200
    claim = client.get(f"/api/claims/{CLAIM}").json()
    assert claim["status"] == "sent back"
    assert claim["decision"] is None
    assert claim["payout"] is None
    assert claim["calculation"] is None
    assert claim["over_approval_limit"] is None
    (kept,) = claim["sent_back_decisions"]
    assert (kept["decision"], kept["payout"], kept["note"]) == (
        "approve",
        "1200.00",
        NOTE["note"],
    )
    assert kept["sent_back_by"] == "HND-01"
    assert kept["sent_back_on"]
    assert kept["calculation"]
    assert kept["manual_version"]
    steps = client.get(f"/api/claims/{CLAIM}/steps").json()
    assert steps[-1]["text"] == f"Sent back by Dana Whitfield: {NOTE['note']}"


def test_a_handler_who_cannot_sign_off_cannot_send_back(client, as_handler):
    waiting(client)

    response = client.post(SEND, json=NOTE, headers=as_handler(MARCUS))

    assert response.status_code == 403


@pytest.mark.parametrize("note", ["", "   ", "x" * 1001])
def test_a_blank_or_long_note_is_refused(client, note):
    waiting(client)

    assert client.post(SEND, json={"note": note}).status_code == 422


def test_a_claim_not_waiting_for_sign_off_is_refused(client):
    assert client.post(SEND, json=NOTE).status_code == 409


def test_a_claim_already_sent_back_is_refused(client):
    waiting(client)
    client.post(SEND, json=NOTE)

    assert client.post(SEND, json=NOTE).status_code == 409


def test_an_evaluations_claim_cannot_be_sent_back(client):
    run = client.post(
        "/api/runs/evaluation",
        json={
            "concurrency": 1,
            "eval_set": "held_out",
            "tiny": True,
            **SETTINGS,
        },
    ).json()
    copy = run["claims"][0]["claim_id"]

    assert client.post(f"/api/claims/{copy}/send-back", json=NOTE).status_code == 409


def test_a_sign_off_and_a_send_back_at_once_let_exactly_one_through(client):
    waiting(client)
    statuses = []

    def post(path, **body):
        statuses.append(client.post(path, **body).status_code)

    threads = [
        threading.Thread(target=post, args=(SEND,), kwargs={"json": NOTE}),
        threading.Thread(target=post, args=(f"/api/claims/{CLAIM}/sign-off",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [200, 409]


def test_the_agent_takes_a_sent_back_claim_once(agent, client):
    waiting(client)
    client.post(SEND, json=NOTE)

    first = agent.post(f"/api/claims/{CLAIM}/take")
    second = agent.post(f"/api/claims/{CLAIM}/take")

    assert first.status_code == 200
    assert first.json()["status"] == "in progress"
    assert second.status_code == 409


def test_the_agent_cannot_send_back_and_a_handler_cannot_take(agent, client):
    waiting(client)

    assert agent.post(SEND, json=NOTE).status_code in (401, 403)
    client.post(SEND, json=NOTE)
    assert client.post(
        f"/api/claims/{CLAIM}/take", headers={"X-API-Key": "no"}
    ).status_code in (401, 403)


def test_a_new_decision_after_a_send_back_needs_a_new_calculation(client):
    waiting(client)
    client.post(SEND, json=NOTE)
    body = {
        "decision": "approve",
        "payout": "1200.00",
        "reason": "Again.",
        "policy_reference": "Section 3",
        "decided_by": "A test agent",
    }

    refused = client.post(f"/api/claims/{CLAIM}/decision", json=body)

    assert refused.status_code == 422
    assert "section 14" in refused.json()["detail"]


def test_a_new_decision_is_paid_within_the_limit_and_waits_over_it(client):
    waiting(client)
    client.post(SEND, json=NOTE)

    within = decide(client, "420.00").json()
    paid = client.post(f"/api/claims/{CLAIM}/payment", json={"amount": "420.00"})

    assert within["status"] == "decided"
    assert paid.json()["paid_amount"] == "420.00"


def test_a_new_decision_over_the_limit_waits_for_sign_off_again(client):
    waiting(client)
    client.post(SEND, json=NOTE)

    again = decide(client, "1300.00").json()

    assert again["status"] == "waiting for sign-off"


def test_a_claim_can_be_sent_back_twice(client):
    waiting(client)
    client.post(SEND, json=NOTE)
    waiting(client, "1300.00")

    client.post(SEND, json={"note": "Still too high."})

    claim = client.get(f"/api/claims/{CLAIM}").json()
    assert [d["payout"] for d in claim["sent_back_decisions"]] == ["1200.00", "1300.00"]


def test_a_dispatch_takes_a_sent_back_claim_and_leaves_one_being_resumed(client, agent):
    waiting(client)
    client.post(SEND, json=NOTE)
    run = agent.post("/api/runs/dispatch", json={"concurrency": 1, **SETTINGS}).json()
    assert CLAIM in [c["claim_id"] for c in run["claims"]]
    agent.post(f"/api/runs/{run['run_id']}/finish")

    agent.post(f"/api/claims/{CLAIM}/take")
    agent.post(f"/api/claims/{CLAIM}/resume-heard")
    run = agent.post("/api/runs/dispatch", json={"concurrency": 1, **SETTINGS}).json()

    assert CLAIM not in [c["claim_id"] for c in run["claims"]]
