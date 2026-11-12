from fastapi.testclient import TestClient
from sqlalchemy import insert

from agent import agents, api, service
from agent.tests.conftest import STUB_MODEL, StubModel
from agent.tests.test_claim_graph import CLAIM, decision
from backend import db, tables


class Capturing(StubModel):
    """A stub model that keeps the messages it was asked to answer."""

    seen: list = []

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(messages)
        return super()._generate(messages, *args, **kwargs)


def add_kept_version(instructions, model="google/gemini-3.5-flash-lite"):
    with db.connection() as conn:
        conn.execute(
            insert(tables.configurations).values(
                version=2,
                instructions=instructions,
                model=model,
                reasoning_effort="low",
                reason="A test version",
                proposed_by="improver",
                created_on=db.now(),
                verdict="kept",
            )
        )


def worked_with(script, saver, run_id=None):
    llm = Capturing(messages=script(decision(), "Done.").messages, seen=[])
    agents.decide_claim(CLAIM, llm, saver, run_id)
    return llm.seen[0][0].content


def test_a_claim_with_no_run_uses_the_current_version(backend, script, saver):
    add_kept_version("Version two says hello.")

    assert worked_with(script, saver) == "Version two says hello."


def test_a_claim_in_a_run_uses_the_runs_version(backend, script, saver):
    run_id = api.create_dispatch(1, STUB_MODEL)
    add_kept_version("Version two says hello.")

    sent = worked_with(script, saver, run_id)

    assert "Version two says hello." not in sent
    assert "You are the UnderCover Agent" in sent


def test_a_run_starts_on_the_current_versions_model(backend, monkeypatch):
    monkeypatch.delenv("MODEL_NAME", raising=False)
    add_kept_version("Version two.")

    run_id = (
        TestClient(service.app)
        .post("/api/dispatches", json={"concurrency": 1})
        .json()["run_id"]
    )

    run = api.get_run(run_id)
    assert run["configuration_version"] == 2
    assert (run["model"], run["reasoning_effort"]) == (
        "google/gemini-3.5-flash-lite",
        "low",
    )


def test_model_name_still_wins(backend, monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    add_kept_version("Version two.")

    run_id = (
        TestClient(service.app)
        .post("/api/dispatches", json={"concurrency": 1})
        .json()["run_id"]
    )

    run = api.get_run(run_id)
    assert (run["model"], run["reasoning_effort"]) == ("openrouter/free", "default")
    assert run["configuration_version"] == 2
