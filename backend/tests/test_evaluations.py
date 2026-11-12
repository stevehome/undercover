from collections import Counter

import pytest
from sqlalchemy import select

from backend import db, tables

EVALUATION = {
    "concurrency": 5,
    "eval_set": "held_out",
    "tiny": True,
    "model": "stub/model",
    "reasoning_effort": "low",
    "configuration_version": 1,
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
        json={
            "concurrency": 1,
            "model": "m",
            "reasoning_effort": "low",
            "configuration_version": 1,
        },
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

    response = client.post(f"/api/claims/{copy}/sign-off")

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


def answer_like_the_handlers(client, claim_id):
    """Decide a copy as the handlers decided its source, read from the key."""
    key = tables.answer_key.c
    with db.connection() as conn:
        row = conn.execute(
            select(key.decision, key.payout_cents).where(
                key.eval_set == "held_out", key.claim_id == claim_id.split("-", 2)[2]
            )
        ).one()
    body = {
        "decision": row.decision,
        "payout": f"{row.payout_cents // 100}.{row.payout_cents % 100:02d}",
        "reason": "Stubbed.",
        "policy_reference": "S1",
    }
    client.post(f"/api/claims/{claim_id}/decision", json=body)


def test_an_evaluation_is_scored_from_its_records(client):
    run = start(client).json()
    for claim in run["claims"]:
        answer_like_the_handlers(client, claim["claim_id"])
    first = run["claims"][0]["claim_id"]
    client.post(
        f"/api/claims/{first}/model-calls",
        json={
            "run_id": run["run_id"],
            "model": "m",
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
            "cost": "0.005",
        },
    )
    client.post(
        f"/api/claims/{first}/work-segments",
        json={
            "run_id": run["run_id"],
            "started_on": "2026-01-01T00:00:00+00:00",
            "finished_on": "2026-01-01T00:00:10+00:00",
        },
    )
    client.post(f"/api/runs/{run['run_id']}/finish")

    evaluation = client.get(f"/api/evaluations/{run['run_id']}").json()

    measures = evaluation["measures"]
    assert measures["decision_accuracy"] == "1.0000"
    assert measures["accuracy"] == "1.0000"
    assert measures["cost_of_mistakes"] == "0.00"
    assert measures["model_cost_per_claim"] == "0.001000000"
    assert measures["seconds_per_claim"] == "2.000"
    assert measures["run_seconds"] is not None
    claim = evaluation["claims"][0]
    assert claim["claim_id"] == first
    assert claim["handler_decision"] == claim["agent_decision"]
    assert claim["handler_payout"] == claim["agent_payout"]
    assert claim["right"] is True
    assert (claim["cost"], claim["work_ms"]) == ("0.005000000", 10000)


def test_the_evaluations_list_newest_first(client):
    first = start(client).json()
    client.post(f"/api/runs/{first['run_id']}/finish")
    second = start(client, tiny=False).json()

    listed = client.get("/api/evaluations").json()

    assert [e["run_id"] for e in listed] == [second["run_id"], first["run_id"]]
    assert listed[0]["status"] == "running"
    assert listed[0]["measures"]["run_seconds"] is None


def test_a_dispatch_is_not_an_evaluation(client):
    run = client.post(
        "/api/runs/dispatch",
        json={
            "concurrency": 1,
            "model": "m",
            "reasoning_effort": "low",
            "configuration_version": 1,
        },
    ).json()

    assert client.get(f"/api/evaluations/{run['run_id']}").status_code == 404
    assert client.get("/api/evaluations").json() == []
