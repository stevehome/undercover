import pytest

DISPATCH = {"concurrency": 3, "model": "stub/model", "reasoning_effort": "low"}


def dispatch(client, **changes):
    return client.post("/api/runs/dispatch", json={**DISPATCH, **changes})


def decide(client, claim_id, payout):
    body = {
        "decision": "approve",
        "payout": payout,
        "reason": "Stubbed.",
        "policy_reference": "S1",
    }
    client.post(f"/api/claims/{claim_id}/decision", json=body)


def test_a_dispatch_takes_waiting_and_in_progress_claims_oldest_first(client):
    queue = [c["claim_id"] for c in client.get("/api/claims").json()]
    client.post(f"/api/claims/{queue[3]}/steps", json={"text": "started"})
    decide(client, queue[1], "420.00")
    client.post(f"/api/claims/{queue[1]}/payment", json={"amount": "420.00"})

    run = dispatch(client).json()

    assert [c["claim_id"] for c in run["claims"]] == [c for c in queue if c != queue[1]]
    assert {c["status"] for c in run["claims"]} == {"to do"}
    assert (run["kind"], run["status"], run["concurrency"]) == (
        "dispatch",
        "running",
        3,
    )
    assert (run["model"], run["reasoning_effort"]) == ("stub/model", "low")


def test_a_dispatch_takes_an_approval_a_restart_left_unpaid(client):
    decide(client, "CLM-1001", "420.00")
    decide(client, "CLM-1002", "1200.00")
    decide(client, "CLM-1003", "1200.00")
    client.post("/api/claims/CLM-1003/sign-off", json={"handler_id": "HND-01"})

    claims = [c["claim_id"] for c in dispatch(client).json()["claims"]]

    assert "CLM-1001" in claims
    assert "CLM-1002" not in claims
    assert "CLM-1003" in claims


def test_a_second_dispatch_is_refused_while_one_is_running(client):
    assert dispatch(client).status_code == 200

    second = dispatch(client)

    assert second.status_code == 409
    assert "already running" in second.json()["detail"]


def test_a_finished_or_stopped_run_lets_the_next_start(client):
    first = dispatch(client).json()
    client.post(f"/api/runs/{first['run_id']}/finish")
    second = dispatch(client).json()
    assert second["run_id"] != first["run_id"]

    assert client.post("/api/runs/stop-unfinished").json() == {"stopped": 1}

    assert client.get(f"/api/runs/{second['run_id']}").json()["status"] == "stopped"
    assert client.get(f"/api/runs/{first['run_id']}").json()["status"] == "finished"
    assert dispatch(client).status_code == 200


@pytest.mark.parametrize("concurrency", [0, 26])
def test_concurrency_is_one_to_twenty_five(client, concurrency):
    assert dispatch(client, concurrency=concurrency).status_code == 422


def test_update_run_claim_tracks_attempts(client):
    run = dispatch(client).json()
    url = f"/api/runs/{run['run_id']}/claims/CLM-1001"

    started = client.post(url, json={"status": "in progress", "note": ""}).json()
    done = client.post(url, json={"status": "done", "note": "Declined"}).json()

    assert started["attempts"] == 1
    assert (done["status"], done["attempts"], done["note"]) == ("done", 1, "Declined")
    assert (
        client.post(
            f"/api/runs/{run['run_id']}/claims/CLM-9999",
            json={"status": "done", "note": ""},
        ).status_code
        == 404
    )


def test_a_run_carries_its_own_cost_and_time(client):
    run = dispatch(client).json()
    claim = "/api/claims/CLM-1001"
    client.post(
        f"{claim}/model-calls",
        json={
            "run_id": run["run_id"],
            "model": "stub/model",
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "cost": "0.000138675",
        },
    )
    client.post(
        f"{claim}/work-segments",
        json={
            "run_id": run["run_id"],
            "started_on": "2026-01-01T00:00:00+00:00",
            "finished_on": "2026-01-01T00:00:02+00:00",
        },
    )

    current = client.get("/api/runs/current").json()

    assert (current["model_calls"], current["total_tokens"]) == (1, 15)
    assert current["cost"] == "0.000138675"
    assert current["work_ms"] == 2000


def test_the_summary_is_built_from_the_records(client):
    run = dispatch(client).json()
    for claim_id, kind, payout in [
        ("CLM-1001", "approve", "420.00"),
        ("CLM-1002", "approve", "1200.00"),
        ("CLM-1003", "decline", "0.00"),
        ("CLM-1004", "refer", "0.00"),
    ]:
        body = {
            "decision": kind,
            "payout": payout,
            "reason": "Stubbed.",
            "policy_reference": "S1",
        }
        client.post(f"/api/claims/{claim_id}/decision", json=body)
    url = f"/api/runs/{run['run_id']}/claims"
    client.post(f"{url}/CLM-1004", json={"status": "left for a handler", "note": ""})
    client.post(f"{url}/CLM-1005", json={"status": "left for a handler", "note": ""})
    client.post(f"{url}/CLM-1006", json={"status": "still in progress", "note": ""})

    summary = client.get(f"/api/runs/{run['run_id']}").json()["summary"]

    assert summary["approved"] == 2
    assert summary["declined"] == 1
    assert summary["referred"] == 1
    assert summary["waiting_for_sign_off"] == [
        {"claim_id": "CLM-1002", "payout": "1200.00"}
    ]
    assert summary["left_for_a_handler"] == ["CLM-1004", "CLM-1005"]
    assert summary["still_in_progress"] == ["CLM-1006"]


def test_get_current_run_is_null_when_none_started(client):
    assert client.get("/api/runs/current").json() is None


def test_an_unknown_run_is_404(client):
    assert client.get("/api/runs/99").status_code == 404


def test_requeue_claim(client):
    client.post("/api/claims/CLM-1001/steps", json={"text": "started"})
    assert client.get("/api/claims/CLM-1001").json()["status"] == "in progress"

    response = client.post("/api/claims/CLM-1001/requeue")
    assert response.status_code == 200
    assert response.json()["status"] == "waiting"


def test_requeue_starts_a_new_thread(client):
    assert client.get("/api/claims/CLM-1001").json()["thread"] == 1
    client.post("/api/claims/CLM-1001/requeue")
    assert client.get("/api/claims/CLM-1001").json()["thread"] == 2


def test_requeue_decided_claim_is_blocked(client):
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 420.0,
            "reason": "Routine trip delay with receipts.",
            "policy_reference": "Section 3",
        },
    )
    response = client.post("/api/claims/CLM-1001/requeue")
    assert response.status_code == 409
