import pytest


def start(client, concurrency=3):
    return client.post("/api/dispatches", json={"concurrency": concurrency})


def test_a_start_asks_the_agent_with_n(client, agent_stub):
    response = start(client, 7)

    assert response.status_code == 202
    assert response.json() == {"run_id": 5}
    assert agent_stub.calls == ["/api/dispatches"]
    assert agent_stub.bodies == [{"concurrency": 7}]


def test_a_start_writes_nothing_itself(client, agent_stub):
    start(client)

    assert client.get("/api/runs/current").json() is None


def test_a_start_is_refused_while_the_agent_has_a_run_going(client, agent_stub):
    agent_stub.refuse = True

    response = start(client)

    assert response.status_code == 409
    assert response.json()["detail"] == "A run is already going"


def test_a_start_says_so_when_the_agent_is_not_running(client, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_AGENT", "http://127.0.0.1:9")

    response = start(client)

    assert response.status_code == 503
    assert response.json()["detail"] == "The agent's service isn't running"


@pytest.mark.parametrize("concurrency", [0, 26])
def test_n_is_one_to_twenty_five(client, agent_stub, concurrency):
    assert start(client, concurrency).status_code == 422
    assert agent_stub.calls == []


def test_an_evaluation_start_asks_the_agent_with_n_the_set_and_tiny(client, agent_stub):
    response = client.post(
        "/api/evaluations",
        json={"concurrency": 5, "eval_set": "held_out", "tiny": True},
    )

    assert response.status_code == 202
    assert agent_stub.calls == ["/api/evaluations"]
    assert agent_stub.bodies == [
        {"concurrency": 5, "eval_set": "held_out", "tiny": True}
    ]
