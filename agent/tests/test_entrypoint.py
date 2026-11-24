import importlib
import os
import threading

import pytest

from agent import background_work, checkpoint, credentials, entrypoint, readiness
from agent.tests.invocations import invoke, ping, wait_until_idle

HEALTH = {"operation": "health"}


def test_importing_the_agent_opens_nothing_and_fetches_nothing(monkeypatch):
    def refuse(*_):
        raise AssertionError("opened at import")

    monkeypatch.setattr(checkpoint, "saver", refuse)
    monkeypatch.setattr(credentials, "fetch", refuse)
    monkeypatch.setattr(readiness, "ensure", refuse)

    importlib.reload(entrypoint)

    assert not readiness._ready  # noqa: SLF001 - the state the import must not change


@pytest.fixture
def on_runtime(monkeypatch):
    """Runtime's settings for two credentials, and a stand-in for Identity."""
    monkeypatch.setenv("AGENTCORE_CREDENTIAL_OPENROUTER_API_KEY_NAME", "or-provider")
    monkeypatch.setenv("AGENTCORE_CREDENTIAL_SECOND_KEY_NAME", "db-provider")
    for setting in ("OPENROUTER_API_KEY", "SECOND_KEY"):
        monkeypatch.setenv(setting, "")
    fetched = []

    def from_identity(provider):
        fetched.append(provider)
        return f"value-of-{provider}"

    monkeypatch.setattr(credentials, "from_identity", from_identity)
    return fetched


def test_on_runtime_the_first_request_fetches_each_credential_once(
    agentcore, on_runtime
):
    first = invoke(agentcore, HEALTH, key=None)
    second = invoke(agentcore, HEALTH, key=None)

    assert first.json() == second.json() == {"healthy": True}
    assert sorted(on_runtime) == ["db-provider", "or-provider"]
    assert os.environ["OPENROUTER_API_KEY"] == "value-of-or-provider"
    assert os.environ["SECOND_KEY"] == "value-of-db-provider"


def test_on_runtime_a_request_without_the_key_is_let_through(
    backend, agentcore, on_runtime
):
    response = invoke(
        agentcore, {"operation": "resume_claim", "claim_id": "CLM-9999"}, key=None
    )

    assert response.status_code == 200
    credentials.os.environ.pop("OPENROUTER_API_KEY", None)
    credentials.os.environ.pop("DATABASE_URL", None)


def test_off_runtime_a_request_without_the_key_is_refused(backend, agentcore):
    start = {"operation": "work_run", "run_id": 1}

    missing = invoke(agentcore, start, key=None)
    wrong = invoke(agentcore, start, key="not-the-key")

    assert (missing.status_code, wrong.status_code) == (401, 401)
    assert "needs the agent's key" in missing.json()["error"]


def test_the_health_check_needs_no_key(backend, agentcore):
    response = invoke(agentcore, HEALTH, key=None)

    assert response.json() == {"healthy": True}


def test_a_failed_getting_ready_answers_the_error_and_the_next_request_tries_again(
    backend, agentcore, monkeypatch
):
    def fails():
        raise RuntimeError("The pool is down")

    monkeypatch.setattr(checkpoint, "saver", fails)
    first = invoke(agentcore, HEALTH)
    monkeypatch.setattr(checkpoint, "saver", lambda: None)

    second = invoke(agentcore, HEALTH)

    assert first.status_code == 500
    assert "The pool is down" in first.json()["error"]
    assert second.json() == {"healthy": True}


@pytest.mark.parametrize(
    ("payload", "said"),
    [
        ({"operation": "work_run"}, "run_id: Field required"),
        (
            {"operation": "work_run", "run_id": "many"},
            "run_id:",
        ),
        ({"operation": "work_run", "run_id": 1, "agents": 3}, "agents:"),
        ({"operation": "start_dispatch"}, "Unknown operation 'start_dispatch'"),
        ({"concurrency": 3}, '"operation"'),
        ("start", '"operation"'),
    ],
)
def test_a_wrong_payload_is_a_400_that_says_what_is_wrong(
    backend, agentcore, payload, said
):
    response = invoke(agentcore, payload)

    assert response.status_code == 400
    assert said in response.json()["error"]


def test_the_ping_is_busy_while_work_is_going_and_healthy_after_it_ends_or_fails(
    agentcore,
):
    running, release = threading.Event(), threading.Event()

    def work(fail):
        running.set()
        release.wait()
        if fail:
            raise RuntimeError("The work failed")

    work_in_background = entrypoint.background
    assert ping(agentcore) == "Healthy"

    for fail in (False, True):
        running.clear()
        release.clear()
        work_in_background.start("work", work, fail)
        running.wait()
        assert ping(agentcore) == "HealthyBusy"
        release.set()
        wait_until_idle(agentcore)
        assert ping(agentcore) == "Healthy"


def test_the_work_is_registered_before_it_runs_and_completed_when_it_ends():
    events = []
    work = background_work.BackgroundWork(
        lambda name: events.append(("added", name)) or 1,
        lambda task_id: events.append(("completed", task_id)),
    )
    ended = threading.Event()

    work.start("a task", lambda: (events.append(("ran",)), ended.set()))
    ended.wait()
    threading.Event().wait(0.05)

    assert events == [("added", "a task"), ("ran",), ("completed", 1)]


@pytest.mark.parametrize("prefix", ["AGENTCORE_CREDENTIAL_", "CREDENTIAL_"])
def test_a_credentials_setting_is_read_with_either_prefix(monkeypatch, prefix):
    monkeypatch.setenv(f"{prefix}UNDERCOVER_API_KEY_NAME", "key-provider")

    assert credentials.providers() == {"UNDERCOVER_API_KEY": "key-provider"}
    assert credentials.on_runtime()
