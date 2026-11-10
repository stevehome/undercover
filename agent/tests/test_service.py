import pytest
from fastapi.testclient import TestClient

from agent import agents, api, checkpoint, service
from agent.tests.test_claim_graph import CLAIM, decision, sign_off


def test_the_service_carries_on_with_a_signed_off_claim(backend, script, saver):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Done."), saver)
    sign_off(backend)
    service.app.dependency_overrides[service.claim_worker] = lambda: (
        lambda claim_id: agents.decide_claim(claim_id, script(), saver)
    )
    try:
        response = TestClient(service.app).post(f"/api/claims/{CLAIM}/resume")
    finally:
        service.app.dependency_overrides.clear()

    assert response.status_code == 202
    assert api.get_claim(CLAIM)["paid_amount"] == "1200.00"


@pytest.fixture
def started():
    """Replace the dispatch with a stand-in that records the runs it is given."""
    runs = []
    service.app.dependency_overrides[service.dispatch_worker] = lambda: (
        lambda run_id, concurrency: runs.append((run_id, concurrency))
    )
    yield runs
    service.app.dependency_overrides.clear()


def test_a_start_answers_at_once_and_works_the_run_in_the_background(backend, started):
    response = TestClient(service.app).post("/api/dispatches", json={"concurrency": 4})

    assert response.status_code == 202
    run = api.get_run(response.json()["run_id"])
    assert (run["status"], run["concurrency"], run["kind"]) == (
        "running",
        4,
        "dispatch",
    )
    assert started == [(run["run_id"], 4)]


def test_the_run_records_the_model_and_effort(backend, started, monkeypatch):
    monkeypatch.delenv("MODEL_NAME", raising=False)

    run_id = (
        TestClient(service.app)
        .post("/api/dispatches", json={"concurrency": 1})
        .json()["run_id"]
    )

    run = api.get_run(run_id)
    assert (run["model"], run["reasoning_effort"]) == ("openai/gpt-6-luna", "low")


def test_a_second_start_is_refused_while_a_run_is_going(backend, started):
    client = TestClient(service.app)
    client.post("/api/dispatches", json={"concurrency": 1})

    second = client.post("/api/dispatches", json={"concurrency": 1})

    assert second.status_code == 409
    assert len(started) == 1


def test_starting_the_service_stops_runs_that_were_going(backend, started, monkeypatch):
    monkeypatch.setattr(checkpoint, "saver", lambda: None)
    run_id = api.create_dispatch(1, "stub/model", "low")

    with TestClient(service.app):
        pass

    assert api.get_run(run_id)["status"] == "stopped"


def test_an_evaluation_starts_on_its_set_and_is_refused_while_a_run_is_going(
    backend, started
):
    client = TestClient(service.app)
    body = {"concurrency": 5, "eval_set": "held_out", "tiny": True}

    first = client.post("/api/evaluations", json=body)

    run = api.get_run(first.json()["run_id"])
    assert (run["kind"], run["eval_set"], run["tiny"], len(run["claims"])) == (
        "evaluation",
        "held_out",
        True,
        5,
    )
    assert started == [(run["run_id"], 5)]
    assert client.post("/api/evaluations", json=body).status_code == 409
