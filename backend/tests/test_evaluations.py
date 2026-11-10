from collections import Counter

import pytest

EVALUATION = {
    "concurrency": 5,
    "eval_set": "held_out",
    "tiny": True,
    "model": "stub/model",
    "reasoning_effort": "low",
}


def start(client, **changes):
    return client.post("/api/runs/evaluation", json={**EVALUATION, **changes})


def queue(client):
    return client.get("/api/claims").json()


@pytest.mark.parametrize(
    ("eval_set", "tiny", "count"),
    [
        ("held_out", True, 5),
        ("held_out", False, 25),
        ("evaluation", True, 5),
        ("evaluation", False, 25),
    ],
)
def test_an_evaluation_copies_the_claims_of_its_set(client, eval_set, tiny, count):
    run = start(client, eval_set=eval_set, tiny=tiny).json()

    assert len(run["claims"]) == count
    assert run["kind"] == "evaluation"
    assert (run["eval_set"], run["tiny"], run["concurrency"]) == (eval_set, tiny, 5)
    assert (run["model"], run["reasoning_effort"]) == ("stub/model", "low")
    for claim in run["claims"]:
        assert claim["claim_id"].startswith(f"EVAL-{run['run_id']}-CLM-")
        copy = client.get(f"/api/claims/{claim['claim_id']}").json()
        assert copy["claim_id"] == claim["claim_id"]
        assert copy["evaluation_run_id"] == run["run_id"]
        assert copy["status"] == "waiting"


def test_an_evaluation_leaves_the_queue_as_it_was(client):
    before = queue(client)
    counts = Counter(c["status"] for c in before)

    run = start(client, eval_set="evaluation", tiny=False).json()
    client.post(f"/api/runs/{run['run_id']}/finish")

    after = queue(client)
    assert after == before
    assert Counter(c["status"] for c in after) == counts


def test_a_dispatch_never_carries_on_a_copy(client):
    run = start(client).json()
    copy = run["claims"][0]["claim_id"]
    client.post(f"/api/claims/{copy}/steps", json={"text": "started"})
    client.post("/api/runs/stop-unfinished")

    dispatch = client.post(
        "/api/runs/dispatch",
        json={"concurrency": 1, "model": "m", "reasoning_effort": "low"},
    ).json()

    assert all(not c["claim_id"].startswith("EVAL-") for c in dispatch["claims"])
    assert client.get(f"/api/runs/{run['run_id']}").json()["status"] == "stopped"


def test_a_copy_cannot_be_signed_off(client):
    copy = start(client).json()["claims"][0]["claim_id"]
    body = {
        "decision": "approve",
        "payout": "1200.00",
        "reason": "Stubbed.",
        "policy_reference": "S1",
    }
    client.post(f"/api/claims/{copy}/decision", json=body)

    response = client.post(
        f"/api/claims/{copy}/sign-off", json={"handler_id": "HND-01"}
    )

    assert response.status_code == 409


def test_a_copy_holds_nothing_from_the_handlers_decisions(client):
    run = start(client, eval_set="evaluation", tiny=False).json()

    for claim in run["claims"]:
        copy = client.get(f"/api/claims/{claim['claim_id']}").json()
        for field in ("decision", "payout", "reason", "policy_reference", "decided_on"):
            assert copy[field] is None, field


def test_a_second_evaluation_is_refused_while_one_is_running(client):
    start(client)

    assert start(client).status_code == 409


def test_an_evaluation_needs_a_known_set(client):
    assert start(client, eval_set="other").status_code == 422
