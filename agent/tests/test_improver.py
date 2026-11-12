from decimal import Decimal

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.runnables.config import var_child_runnable_config
from sqlalchemy import select

from agent import api, dispatcher, harness, improver_api, rounds
from agent.backend_http import ApiRefusal
from agent.tests.conftest import StubModel
from backend import db, tables

NEW_INSTRUCTIONS = "Decide the claim carefully, and never approve a late claim.\n"
CHANGE = {
    "instructions": NEW_INSTRUCTIONS,
    "model": "openai/gpt-6-luna",
    "reasoning_effort": "low",
    "reason": "Late claims were approved.",
}
RECIPE = {"recipe": "1. Read the results.\n", "reason": "Shorter."}
USED = ("openai/gpt-6-luna", "medium")


class Capturing(StubModel):
    """A stub model that keeps every message it was asked to answer."""

    seen: list = []

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


@pytest.fixture
def improver_script(script):
    """Build a capturing stub model for the improver from scripted steps."""

    def build(*steps):
        return Capturing(messages=script(*steps).messages, seen=[])

    return build


def answer(eval_set, source_id):
    key = tables.answer_key.c
    with db.connection() as conn:
        row = conn.execute(
            select(key.decision, key.payout_cents).where(
                key.eval_set == eval_set, key.claim_id == source_id
            )
        ).one()
    return row.decision, Decimal(row.payout_cents) / 100


@pytest.fixture
def worked(monkeypatch):
    """Work a run's claims with a stand-in: version 2 is right, version 1 declines."""
    seen = {"threads": [], "runs": []}
    real = dispatcher.run_dispatch

    def stand_in(run_id, concurrency):
        seen["threads"].append(var_child_runnable_config.get())
        run = api.get_run(run_id)
        seen["runs"].append(run_id)

        def decide(claim_id, *, run_id):
            decision, payout = ("decline", Decimal(0))
            if run["configuration_version"] == 2:
                decision, payout = answer(run["eval_set"], claim_id.split("-", 2)[2])
            api.decide_claim(claim_id, decision, payout, "Because.", "Section 3")
            return "Decided."

        return real(run_id, concurrency, decide)

    monkeypatch.setattr(dispatcher, "run_dispatch", stand_in)
    return seen


@pytest.fixture
def stop(backend, as_handler):
    """Stop a round the way a handler does, through the backend."""
    return lambda round_id: backend.post(
        f"/api/rounds/{round_id}/stop", headers=as_handler()
    )


def start_round(backend):
    created = rounds.new_round("HND-01")
    return created["round_id"], created["run_id"]


def state(backend, round_id):
    return backend.get(f"/api/rounds/{round_id}").json()


def decide(backend, proposal_id, approved, reason=""):
    recorded = improver_api.record_proposal_decision(
        proposal_id, approved, "HND-01", reason, USED
    )
    return recorded["run_id"], rounds.decision(approved, reason)


def full_script():
    return (
        ("read_results", {}),
        ("propose_change", CHANGE),
        ("run_evaluation", {}),
        ("propose_recipe", RECIPE),
        "Done.",
    )


def test_a_round_carries_out_the_recipe(backend, improver_script, saver, worked):
    llm = improver_script(*full_script())
    round_id, run_id = start_round(backend)

    # The first evaluations, then the improver reads its results and proposes.
    rounds.work_stretch(round_id, run_id, None, llm, saver)

    waiting = state(backend, round_id)
    assert waiting["stage"] == "change waiting"
    [proposal] = waiting["proposals"]
    assert (proposal["kind"], proposal["status"]) == ("change", "pending")
    assert len(backend.get("/api/configurations").json()) == 1
    assert len(worked["runs"]) == 3
    assert backend.get(f"/api/runs/{run_id}").json()["status"] == "finished"

    # An approval makes version 2, and the improver has it evaluated.
    run_id, resume = decide(backend, proposal["proposal_id"], True)
    rounds.work_stretch(round_id, run_id, resume, llm, saver)

    waiting = state(backend, round_id)
    assert waiting["stage"] == "recipe waiting"
    assert waiting["configuration_version"] == 2
    assert waiting["verdict"] == "kept"
    assert len(worked["runs"]) == 6
    version_2 = [backend.get(f"/api/runs/{r}").json() for r in worked["runs"][3:]]
    assert [r["eval_set"] for r in version_2] == ["evaluation", "held_out", "held_out"]
    assert {r["configuration_version"] for r in version_2} == {2}
    assert backend.get("/api/configuration/current").json()["version"] == 2

    # A recipe proposal pauses the round again; approving it finishes the round.
    recipe_id = waiting["proposals"][1]["proposal_id"]
    run_id, resume = decide(backend, recipe_id, True)
    rounds.work_stretch(round_id, run_id, resume, llm, saver)

    finished = state(backend, round_id)
    assert finished["stage"] == "finished"
    assert [r["version"] for r in backend.get("/api/recipes").json()] == [1, 2]
    assert finished["cost"] != "0.000000000"
    assert backend.get("/api/runs/current").json()["status"] == "finished"


def test_a_rejections_reason_reaches_the_improver_who_may_propose_again(
    backend, improver_script, saver, worked
):
    llm = improver_script(
        ("propose_change", CHANGE),
        ("propose_change", {**CHANGE, "reason": "A shorter rule."}),
        "Done.",
    )
    round_id, run_id = start_round(backend)
    rounds.work_stretch(round_id, run_id, None, llm, saver)
    first = state(backend, round_id)["proposals"][0]

    run_id, resume = decide(
        backend, first["proposal_id"], False, "Too long, shorten it."
    )
    rounds.work_stretch(round_id, run_id, resume, llm, saver)

    replies = [m for m in llm.seen[-1] if isinstance(m, ToolMessage)]
    assert "Too long, shorten it." in replies[-1].content
    again = state(backend, round_id)
    assert [p["status"] for p in again["proposals"]] == ["rejected", "pending"]
    assert again["proposals"][0]["rejection_reason"] == "Too long, shorten it."
    assert len(backend.get("/api/configurations").json()) == 1


def test_a_proposal_outside_the_models_allowed_never_reaches_a_handler(
    backend, improver_script, saver, worked
):
    llm = improver_script(
        ("propose_change", {**CHANGE, "model": "made/up-model"}),
        ("propose_change", CHANGE),
        "Done.",
    )
    round_id, run_id = start_round(backend)

    rounds.work_stretch(round_id, run_id, None, llm, saver)

    [proposal] = state(backend, round_id)["proposals"]
    assert proposal["content"]["model"] == "openai/gpt-6-luna"
    refusal = [m for m in llm.seen[-1] if isinstance(m, ToolMessage)][-1]
    assert "made/up-model at low isn't allowed" in refusal.content
    assert refusal.status == "error"


def test_a_round_waiting_for_approval_survives_a_restart(
    backend, improver_script, saver, worked
):
    round_id, run_id = start_round(backend)
    first_process = improver_script(("propose_change", CHANGE))
    rounds.work_stretch(round_id, run_id, None, first_process, saver)
    proposal = state(backend, round_id)["proposals"][0]

    # A new process: a new model object, with the same saved progress and thread.
    second_process = improver_script(("run_evaluation", {}), "Done.")
    run_id, resume = decide(backend, proposal["proposal_id"], True)
    rounds.work_stretch(round_id, run_id, resume, second_process, saver)

    assert state(backend, round_id)["verdict"] == "kept"
    thread = state(backend, round_id)["thread_id"]
    assert {c.config["configurable"]["thread_id"] for c in saver.list(None)} == {thread}


def test_the_evaluations_run_in_a_fresh_context(
    backend, improver_script, saver, worked
):
    llm = improver_script(("propose_change", CHANGE), "Done.")
    round_id, run_id = start_round(backend)

    rounds.work_stretch(round_id, run_id, None, llm, saver)

    assert worked["threads"] == [None, None, None]


def test_a_stopped_round_starts_no_claims_or_model_calls_and_frees_the_rule(
    backend, improver_script, saver, worked, stop
):
    llm = improver_script(("read_results", {}), "Done.")
    round_id, run_id = start_round(backend)
    stop(round_id)

    rounds.work_stretch(round_id, run_id, None, llm, saver)

    assert worked["runs"] == []
    assert llm.seen == []
    assert backend.get(f"/api/runs/{run_id}").json()["status"] == "finished"
    assert state(backend, round_id)["stage"] == "stopped"
    assert api.create_dispatch(
        1, api.ModelUsed(model="m", reasoning_effort="low", configuration_version=1)
    )


def test_a_round_stopped_while_evaluating_starts_no_more_claims(
    backend, improver_script, saver, monkeypatch, stop
):
    inner = dispatcher.run_dispatch

    def stop_first(run_id, concurrency):
        stop(round_id)
        return inner(run_id, concurrency)

    monkeypatch.setattr(dispatcher, "run_dispatch", stop_first)
    llm = improver_script(("read_results", {}), "Done.")
    round_id, run_id = start_round(backend)

    rounds.work_stretch(round_id, run_id, None, llm, saver)

    evaluation = backend.get("/api/runs/2").json()
    assert evaluation["status"] == "stopped"
    assert {c["status"] for c in evaluation["claims"]} == {"to do"}
    assert llm.seen == []


def test_the_improver_calls_are_capped_for_each_round(
    backend, improver_script, saver, worked, monkeypatch
):
    monkeypatch.setattr(harness, "MAX_IMPROVER_CALLS", 2)
    llm = improver_script(*[("read_results", {})] * 5)
    round_id, run_id = start_round(backend)

    with pytest.raises(Exception, match="call limit"):
        rounds.work_stretch(round_id, run_id, None, llm, saver)

    assert state(backend, round_id)["stage"] == "stopped"
    assert len(llm.seen) == 2


def test_the_improvers_model_has_parallel_tool_calls_off(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)

    settings = harness.improver_settings()
    model = harness.improver_model(settings)

    assert settings == harness.ModelSettings("openai/gpt-6-luna", "medium")
    assert model.model_kwargs == {"parallel_tool_calls": False}
    assert model.reasoning_effort == "medium"


def test_with_model_name_set_the_improver_uses_that_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")

    settings = harness.improver_settings()

    assert settings == harness.ModelSettings("openrouter/free", "default")
    assert harness.improver_model(settings).reasoning_effort is None


def test_a_round_may_not_start_while_a_run_is_going(backend):
    start_round(backend)

    with pytest.raises(ApiRefusal) as refused:
        rounds.new_round("HND-01")

    assert refused.value.status_code == 409


def test_the_first_evaluations_are_skipped_when_the_current_version_has_them(
    backend, improver_script, saver, worked
):
    round_id, run_id = start_round(backend)
    rounds.work_stretch(
        round_id, run_id, None, improver_script(("read_results", {}), "Done."), saver
    )
    assert len(worked["runs"]) == 3

    second_id, second_run = start_round(backend)
    rounds.work_stretch(second_id, second_run, None, improver_script("Done."), saver)

    assert len(worked["runs"]) == 3
    assert state(backend, second_id)["stage"] == "finished"


def test_a_round_that_proposes_nothing_finishes_with_no_version_tried(
    backend, improver_script, saver, worked
):
    round_id, run_id = start_round(backend)

    rounds.work_stretch(
        round_id, run_id, None, improver_script("Nothing to change."), saver
    )

    finished = state(backend, round_id)
    assert finished["stage"] == "finished"
    assert finished["configuration_version"] is None
    assert len(backend.get("/api/configurations").json()) == 1


def test_the_model_call_records_cost_with_the_round(
    backend, improver_script, saver, worked
):
    round_id, run_id = start_round(backend)
    llm = improver_script("Nothing to change.")

    rounds.work_stretch(round_id, run_id, None, llm, saver)

    assert state(backend, round_id)["cost"] != "0.000000000"
