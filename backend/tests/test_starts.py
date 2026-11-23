import threading
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import insert, update

from backend import db, tables
from backend.tests.test_decisions import decide
from backend.tests.test_rounds import Flow


@pytest.fixture
def flow(client):
    return Flow(client)


EVALUATION = {"concurrency": 5, "eval_set": "held_out", "tiny": True}
MINUTES = 6


def dispatch(client, concurrency=3):
    return client.post("/api/dispatches", json={"concurrency": concurrency})


def evaluate(client, **changes):
    return client.post("/api/evaluations", json={**EVALUATION, **changes})


def run_of(client, run_id):
    return client.get(f"/api/runs/{run_id}").json()


def long_ago(minutes=MINUTES):
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def age_runs(minutes=MINUTES, **columns):
    """Make every run's start and last word as old as `minutes` ago."""
    with db.connection() as conn:
        conn.execute(
            update(tables.runs).values(
                started_on=long_ago(minutes), heard_from_on=None, **columns
            )
        )


def test_a_dispatch_is_created_by_the_app_and_the_agent_asked_to_work_it(
    client, agent_stub
):
    response = dispatch(client, 7)

    run_id = response.json()["run_id"]
    assert (response.status_code, agent_stub.calls) == (202, ["work_run"])
    assert agent_stub.bodies == [{"run_id": run_id}]
    run = run_of(client, run_id)
    assert (run["kind"], run["status"], run["concurrency"]) == (
        "dispatch",
        "running",
        7,
    )
    assert (run["model"], run["configuration_version"]) == (
        "openai/gpt-6-luna",
        1,
    )


def test_an_evaluation_is_created_with_its_set_and_the_agent_asked_to_work_it(
    client, agent_stub
):
    response = evaluate(client)

    run = run_of(client, response.json()["run_id"])
    assert agent_stub.calls == ["work_run"]
    assert (run["kind"], run["eval_set"], run["tiny"], len(run["claims"])) == (
        "evaluation",
        "held_out",
        True,
        5,
    )


def test_a_start_records_the_current_versions_model_and_effort(client, agent_stub):
    with db.connection() as conn:
        conn.execute(
            insert(tables.configurations).values(
                version=2,
                instructions="Version two.",
                model="google/gemini-3.5-flash-lite",
                reasoning_effort="low",
                reason="A test version",
                proposed_by="improver",
                created_on=db.now(),
                verdict="kept",
            )
        )

    run = run_of(client, dispatch(client).json()["run_id"])

    assert run["configuration_version"] == 2
    assert (run["model"], run["reasoning_effort"]) == (
        "google/gemini-3.5-flash-lite",
        "low",
    )


def test_a_round_records_model_name_for_the_improver_when_it_is_set(
    client, agent_stub, monkeypatch
):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    round_id = client.post("/api/rounds").json()["round_id"]

    stretch = client.get(f"/api/improver/rounds/{round_id}/stretch").json()

    run = run_of(client, stretch["run_id"])
    assert (run["model"], run["reasoning_effort"]) == ("openrouter/free", "default")


def test_a_start_records_model_name_with_no_effort_when_it_is_set(
    client, agent_stub, monkeypatch
):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")

    run = run_of(client, dispatch(client).json()["run_id"])

    assert (run["model"], run["reasoning_effort"]) == ("openrouter/free", "default")


@pytest.mark.parametrize("concurrency", [0, 26])
def test_n_is_one_to_twenty_five(client, agent_stub, concurrency):
    assert dispatch(client, concurrency).status_code == 422
    assert agent_stub.calls == []


def test_a_second_start_is_refused_naming_what_is_going(client, agent_stub):
    dispatch(client)

    second = dispatch(client)

    assert second.status_code == 409
    assert second.json()["detail"] == "A dispatch is already running"
    assert evaluate(client).json()["detail"] == "A dispatch is already running"
    assert agent_stub.calls == ["work_run"]


def test_an_evaluation_going_is_named(client, agent_stub):
    evaluate(client)

    assert dispatch(client).json()["detail"] == "An evaluation is already running"


def test_a_working_round_is_named_and_refuses_every_start(client, agent_stub):
    assert client.post("/api/rounds").status_code == 202

    assert (
        dispatch(client).json()["detail"] == "An improvement round is already running"
    )
    assert client.post("/api/rounds").status_code == 409


def test_a_round_waiting_for_a_review_does_not_hold_a_dispatch(client, agent_stub):
    flow = Flow(client)
    flow.first_evaluations()
    flow.propose()
    flow.end_stretch()

    assert dispatch(client).status_code == 202


def test_two_starts_at_the_same_moment_let_exactly_one_through(client, agent_stub):
    statuses = []

    def start():
        statuses.append(dispatch(client).status_code)

    threads = [threading.Thread(target=start) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [202, 409, 409, 409]
    assert agent_stub.calls == ["work_run"]


def test_a_start_after_five_quiet_minutes_stops_the_old_work_and_goes_ahead(
    client, agent_stub
):
    first = dispatch(client).json()["run_id"]
    age_runs()

    second = dispatch(client)

    assert second.status_code == 202
    stopped = run_of(client, first)
    assert (stopped["status"], stopped["stopped_reason"]) == (
        "stopped",
        "The agent stopped answering",
    )


def test_work_heard_from_a_minute_ago_is_left_alone(client, agent_stub):
    first = dispatch(client).json()["run_id"]
    age_runs()
    client.post(f"/api/runs/{first}/heard")

    second = dispatch(client)

    assert second.status_code == 409
    assert run_of(client, first)["status"] == "running"


def test_a_round_gone_quiet_stops_with_its_evaluation(client, agent_stub):
    flow = Flow(client)
    evaluation = client.post(
        flow.url("evaluations"),
        json={
            "concurrency": 2,
            "model": "m",
            "reasoning_effort": "low",
            "configuration_version": 1,
            "parent_run_id": flow.stretch,
            "eval_set": "evaluation",
            "check_spending": False,
        },
    ).json()
    age_runs()

    assert dispatch(client).status_code == 202

    round_ = client.get(f"/api/rounds/{flow.round_id}").json()
    assert (round_["stage"], round_["stopped_reason"]) == (
        "stopped",
        "The agent stopped answering",
    )
    assert run_of(client, evaluation["run_id"])["status"] == "stopped"


def test_the_app_never_stops_a_rounds_evaluation_on_its_own(client, agent_stub):
    flow = Flow(client)
    evaluation = client.post(
        flow.url("evaluations"),
        json={
            "concurrency": 2,
            "model": "m",
            "reasoning_effort": "low",
            "configuration_version": 1,
            "parent_run_id": flow.stretch,
            "eval_set": "evaluation",
            "check_spending": False,
        },
    ).json()
    with db.connection() as conn:
        conn.execute(
            update(tables.runs)
            .where(tables.runs.c.run_id == evaluation["run_id"])
            .values(started_on=long_ago(), heard_from_on=None)
        )
    client.post(f"/api/runs/{flow.stretch}/heard")

    assert dispatch(client).status_code == 409
    assert run_of(client, evaluation["run_id"])["status"] == "running"


def test_a_failed_run_stops_only_itself(client, agent_stub):
    first = dispatch(client).json()["run_id"]
    client.post(f"/api/runs/{first}/stop", json={"reason": "The work failed"})

    second = dispatch(client)

    assert second.status_code == 202
    assert run_of(client, first)["stopped_reason"] == "The work failed"
    assert run_of(client, second.json()["run_id"])["status"] == "running"
    client.post(f"/api/runs/{first}/stop", json={"reason": "Again"})
    assert run_of(client, second.json()["run_id"])["status"] == "running"


def test_a_resume_runs_beside_a_dispatch(client, agent_stub):
    run_id = dispatch(client).json()["run_id"]
    decide(client, "1200.00")

    signed = client.post("/api/claims/CLM-1001/sign-off")

    assert signed.status_code == 200
    assert agent_stub.calls == ["work_run", "resume_claim"]
    assert run_of(client, run_id)["status"] == "running"


def test_a_start_the_agent_refused_is_undone_and_passed_on(client, agent_stub):
    agent_stub.refuse = True

    response = dispatch(client)

    assert (response.status_code, response.json()["detail"]) == (
        409,
        "A run is already going",
    )
    run = run_of(client, 1)
    assert (run["status"], run["stopped_reason"]) == (
        "stopped",
        "The agent did not take the work",
    )
    agent_stub.refuse = False
    assert dispatch(client).status_code == 202


def test_a_start_that_never_connected_is_undone(client, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_AGENT", "http://127.0.0.1:9")

    response = dispatch(client)

    assert (response.status_code, response.json()["detail"]) == (
        503,
        "The agent isn't running",
    )
    assert run_of(client, 1)["status"] == "stopped"
    assert client.get("/api/runs/current").json()["status"] == "stopped"


def test_an_error_answer_undoes_an_evaluation(client, monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *_, **__: httpx.Response(500, json={"error": "boom"})
    )

    response = evaluate(client)

    assert response.status_code == 503
    assert run_of(client, 1)["status"] == "stopped"


def test_a_round_the_agent_did_not_take_is_stopped(client, monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *_, **__: httpx.Response(500, json={"error": "boom"})
    )

    assert client.post("/api/rounds").status_code == 503

    round_ = client.get("/api/rounds/1").json()
    assert round_["stage"] == "stopped"
    assert round_["stopped_reason"] == "The agent did not take the work"


def test_a_timeout_leaves_the_work_going_and_tells_the_handler_to_reload(
    client, monkeypatch
):
    def slow(*_, **__):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "post", slow)

    response = dispatch(client)

    assert response.status_code == 504
    assert run_of(client, 1)["status"] == "running"


def test_a_review_the_agent_did_not_take_is_cleared(client, flow, monkeypatch):
    flow.first_evaluations()
    proposal = flow.propose().json()
    flow.end_stretch()
    before = client.get(f"/api/rounds/{flow.round_id}").json()
    versions_before = len(client.get("/api/configurations").json())
    monkeypatch.setattr(
        httpx, "post", lambda *_, **__: httpx.Response(500, json={"error": "boom"})
    )

    response = client.post(
        f"/api/proposals/{proposal['proposal_id']}/decision",
        json={"decision": "approve", "reason": ""},
    )

    assert response.status_code == 503
    after = client.get(f"/api/rounds/{flow.round_id}").json()
    assert (after["stage"], after["configuration_version"]) == (
        before["stage"],
        before["configuration_version"],
    )
    cleared = client.get(f"/api/proposals/{proposal['proposal_id']}").json()
    assert (cleared["status"], cleared["decided_by"]) == ("pending", None)
    assert len(client.get("/api/configurations").json()) == versions_before
    assert client.get("/api/runs/current").json()["status"] == "stopped"
