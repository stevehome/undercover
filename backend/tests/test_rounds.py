import json
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from backend import db, tables

MARCUS = "marcus.oyelaran@undercover.example"
IMPROVER = {"model": "openai/gpt-6-luna", "reasoning_effort": "medium"}
CHANGE = {
    "instructions": "Better instructions.\n",
    "model": "openai/gpt-6-luna",
    "reasoning_effort": "low",
}


class Flow:
    """Plays the agent's service against the backend, as the improver's round does."""

    def __init__(self, client):
        self.client = client
        created = client.post(
            "/api/improver/rounds", json={"handler_id": "HND-01", **IMPROVER}
        )
        assert created.status_code == 200, created.text
        self.round_id = created.json()["round_id"]
        self.stretch = created.json()["run_id"]

    def url(self, path):
        return f"/api/improver/rounds/{self.round_id}/{path}"

    def evaluate(self, version, eval_set, correct, model="m", worked=None):
        """Run a whole-set evaluation of a version, answering rightly or declining."""
        body = {
            "concurrency": 5,
            "model": model,
            "reasoning_effort": "low",
            "configuration_version": version,
            "parent_run_id": self.stretch,
            "eval_set": eval_set,
            "check_spending": False,
        }
        created = self.client.post(self.url("evaluations"), json=body)
        assert created.status_code == 200, created.text
        run = created.json()
        for position, claim in enumerate(run["claims"]):
            if worked is not None and position >= worked:
                continue
            self.answer(run["run_id"], claim, correct, eval_set)
        self.client.post(f"/api/runs/{run['run_id']}/finish")
        return run

    def answer(self, run_id, claim, correct, eval_set):
        key = tables.answer_key.c
        source_id = claim["claim_id"].split("-", 2)[2]
        with db.connection() as conn:
            row = conn.execute(
                select(key.decision, key.payout_cents).where(
                    key.eval_set == eval_set, key.claim_id == source_id
                )
            ).one()
        decision, payout = (
            (row.decision, f"{Decimal(row.payout_cents) / 100:.2f}")
            if correct
            else ("decline", "0.00")
        )
        self.client.post(
            f"/api/claims/{claim['claim_id']}/decision",
            json={
                "decision": decision,
                "payout": payout,
                "reason": "Because.",
                "policy_reference": "Section 3",
            },
        )
        self.client.post(
            f"/api/runs/{run_id}/claims/{claim['claim_id']}",
            json={"status": "done", "note": "done"},
        )

    def first_evaluations(self, correct=False):
        for eval_set in self.client.get(self.url("first-evaluations")).json():
            self.evaluate(1, eval_set, correct)

    def propose(self, kind="change", content=None, reason="Add a rule."):
        content = content or (CHANGE if kind == "change" else {"recipe": "1. Read.\n"})
        return self.client.post(
            self.url("proposals"),
            json={"kind": kind, "content": content, "reason": reason},
        )

    def decide(self, proposal_id, approved=True, reason=""):
        self.end_stretch()
        decided = self.client.post(
            f"/api/improver/proposals/{proposal_id}/decision",
            json={
                "approved": approved,
                "handler_id": "HND-01",
                "rejection_reason": reason,
                **IMPROVER,
            },
        )
        if decided.status_code == 200:
            self.stretch = decided.json()["run_id"]
        return decided

    def end_stretch(self):
        self.client.post(f"/api/runs/{self.stretch}/finish")


@pytest.fixture
def flow(client):
    return Flow(client)


def current_version(client):
    return client.get("/api/configuration/current").json()["version"]


def test_a_round_starts_with_the_settings_and_recipe_it_followed(client):
    client.post("/api/settings/round_spending_limit", json={"value": "0.75"})
    flow = Flow(client)
    client.post("/api/settings/round_spending_limit", json={"value": "9"})

    started = client.get(f"/api/rounds/{flow.round_id}").json()

    assert started["stage"] == "first evaluations"
    assert started["recipe_version"] == 1
    assert started["settings"]["round_spending_limit"] == "0.75"
    assert started["spending_limit"] == "0.75"
    assert started["started_by"] == "HND-01"


def test_a_proposal_changes_nothing_until_it_is_approved(client, flow):
    flow.first_evaluations()

    proposal = flow.propose().json()

    assert proposal["status"] == "pending"
    assert len(client.get("/api/configurations").json()) == 1
    assert (
        client.get(f"/api/rounds/{flow.round_id}").json()["stage"] == "change waiting"
    )
    flow.decide(proposal["proposal_id"])
    [first, second] = client.get("/api/configurations").json()
    assert second["version"] == 2
    assert second["instructions"] == CHANGE["instructions"]
    assert second["approved_by"] == "HND-01"
    assert second["approved_on"] is not None
    assert second["verdict"] is None
    assert second["round_id"] == flow.round_id
    decided = client.get(f"/api/proposals/{proposal['proposal_id']}").json()
    assert (decided["status"], decided["decided_by"]) == ("approved", "Dana Whitfield")
    assert decided["version"] == 2
    assert first["version"] == 1


def test_the_proposals_diff_shows_the_change_and_the_models(client, flow):
    flow.first_evaluations()

    proposal = flow.propose().json()

    kinds = {line["kind"] for line in proposal["lines"]}
    assert {"added", "removed"} <= kinds
    assert proposal["model_before"] == "openai/gpt-6-luna"
    assert proposal["reasoning_effort_after"] == "low"


@pytest.mark.parametrize(
    "change",
    [
        {"model": "made/up-model"},
        {"model": "deepseek/deepseek-v4.1-flash", "reasoning_effort": "high"},
        {"instructions": "  "},
    ],
)
def test_a_proposal_outside_the_models_allowed_is_refused_and_never_pending(
    client, flow, change
):
    refused = flow.propose(content={**CHANGE, **change})

    assert refused.status_code == 422
    assert refused.json()["detail"]
    assert client.get(f"/api/rounds/{flow.round_id}").json()["proposals"] == []


def test_a_rejection_records_the_handlers_reason_and_makes_no_version(client, flow):
    proposal = flow.propose().json()

    flow.decide(proposal["proposal_id"], approved=False, reason="Too long.")

    rejected = client.get(f"/api/proposals/{proposal['proposal_id']}").json()
    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == "Too long."
    assert len(client.get("/api/configurations").json()) == 1
    assert (
        client.get(f"/api/rounds/{flow.round_id}").json()["stage"] == "improver working"
    )


def test_an_approval_while_a_dispatch_runs_is_refused_and_records_nothing(client, flow):
    proposal = flow.propose().json()
    flow.end_stretch()
    dispatch = client.post(
        "/api/runs/dispatch",
        json={**IMPROVER, "concurrency": 1, "configuration_version": 1},
    ).json()

    refused = client.post(
        f"/api/improver/proposals/{proposal['proposal_id']}/decision",
        json={
            "approved": True,
            "handler_id": "HND-01",
            "rejection_reason": "",
            **IMPROVER,
        },
    )

    assert refused.status_code == 409
    assert "already running" in refused.json()["detail"]
    assert (
        client.get(f"/api/proposals/{proposal['proposal_id']}").json()["status"]
        == "pending"
    )
    assert len(client.get("/api/configurations").json()) == 1
    client.post(f"/api/runs/{dispatch['run_id']}/finish")
    assert flow.decide(proposal["proposal_id"]).status_code == 200


def test_a_round_may_not_start_while_a_run_is_going(client, flow):
    second = client.post(
        "/api/improver/rounds", json={"handler_id": "HND-01", **IMPROVER}
    )

    assert second.status_code == 409


def test_a_rounds_own_evaluations_are_not_refused_by_its_stretch(client, flow):
    run = flow.evaluate(1, "evaluation", correct=False)

    assert client.get(f"/api/runs/{run['run_id']}").json()["status"] == "finished"


def test_a_dispatch_runs_while_a_round_waits_for_a_handler(client, flow):
    flow.first_evaluations()
    flow.propose()
    flow.end_stretch()

    dispatch = client.post(
        "/api/runs/dispatch",
        json={**IMPROVER, "concurrency": 1, "configuration_version": 1},
    )

    assert dispatch.status_code == 200


def test_the_first_evaluations_are_what_the_current_version_lacks(client, flow):
    assert client.get(flow.url("first-evaluations")).json() == [
        "evaluation",
        "held_out",
        "held_out",
    ]
    flow.evaluate(1, "evaluation", correct=False)
    flow.evaluate(1, "held_out", correct=False)

    assert client.get(flow.url("first-evaluations")).json() == ["held_out"]


def test_a_version_that_improves_is_kept_and_becomes_current(client, flow):
    flow.first_evaluations(correct=False)
    flow.decide(flow.propose().json()["proposal_id"])
    flow.evaluate(2, "evaluation", correct=True)
    flow.evaluate(2, "held_out", correct=True)
    flow.evaluate(2, "held_out", correct=True)

    verdict = client.post(flow.url("verdict")).json()

    assert verdict["verdict"] == "kept"
    assert "accuracy improved" in verdict["reason"]
    assert current_version(client) == 2
    finished = client.get(f"/api/rounds/{flow.round_id}").json()
    assert finished["verdict"] == "kept"
    assert (
        finished["held_out_before"]["accuracy"]
        != finished["held_out_after"]["accuracy"]
    )
    assert finished["configuration_version"] == 2


def test_a_version_that_does_not_improve_is_rolled_back(client, flow):
    flow.first_evaluations(correct=True)
    flow.decide(flow.propose().json()["proposal_id"])
    for eval_set in ("evaluation", "held_out", "held_out"):
        flow.evaluate(2, eval_set, correct=True)

    verdict = client.post(flow.url("verdict")).json()

    assert verdict["verdict"] == "rolled back"
    assert "noise" in verdict["reason"]
    assert current_version(client) == 1
    assert client.get("/api/configurations").json()[1]["verdict"] == "rolled back"


def test_a_version_that_misses_the_objectives_is_rolled_back(client, flow):
    flow.first_evaluations(correct=False)
    flow.decide(flow.propose().json()["proposal_id"])
    for eval_set in ("evaluation", "held_out", "held_out"):
        flow.evaluate(2, eval_set, correct=False)

    verdict = client.post(flow.url("verdict")).json()

    assert verdict["verdict"] == "rolled back"
    assert verdict["reason"] == "it missed the objectives on accuracy"


def test_a_versions_scores_count_only_its_rounds_whole_set_evaluations(client):
    body = {
        "concurrency": 5,
        "eval_set": "held_out",
        "model": "m",
        "reasoning_effort": "low",
        "configuration_version": 1,
    }
    scoreboard = client.post("/api/runs/evaluation", json={**body, "tiny": False})
    client.post(f"/api/runs/{scoreboard.json()['run_id']}/finish")
    flow = Flow(client)
    tiny = client.post(
        flow.url("evaluations"),
        json={**body, "parent_run_id": flow.stretch, "check_spending": False},
    )
    flow.first_evaluations()

    view = client.get(flow.url("view")).json()

    assert tiny.status_code == 200
    assert view["scores"]["held_out"]["runs"] == 2
    assert view["scores"]["evaluation"]["runs"] == 1


def test_the_improvers_view_holds_nothing_from_the_held_out_set_but_scores(
    client, flow
):
    flow.first_evaluations()
    held_out = json.loads(
        (
            Path(__file__).resolve().parents[2] / "data/evals/held_out_decisions.json"
        ).read_text()
    )
    evaluation_set = json.loads(
        (Path(__file__).resolve().parents[2] / "data/evals/decisions.json").read_text()
    )
    held_out_claims = json.loads(
        (
            Path(__file__).resolve().parents[2] / "data/evals/held_out_claims.json"
        ).read_text()
    )

    view = json.dumps(client.get(flow.url("view")).json())

    shared = {a["reference"] for a in evaluation_set}
    for answer in held_out:
        assert answer["reason"] not in view
        if answer["reference"] not in shared:
            assert answer["reference"] not in view
    for claim in held_out_claims:
        assert claim["claim_id"] not in view
        assert claim["story"] not in view


def test_the_improver_sees_the_wrong_claims_and_five_right_ones(client, flow):
    flow.first_evaluations(correct=False)

    view = client.get(flow.url("view")).json()

    claims = view["evaluation_set_claims"]
    assert claims["wrong"]
    assert all(not c["right"] and c["handler"]["reason"] for c in claims["wrong"])
    assert len(claims["right_but_explained_least_well"]) <= 5
    assert view["rule"].startswith("A new version is kept")
    assert view["models_allowed"][0]["model"] == "openai/gpt-6-luna"
    # 75 graded claims at the stub judge's $0.00004 each.
    assert view["spending"]["left"] == "0.497000000"
    assert view["objectives_on_the_held_out_set"]["accuracy"] == "0.60"


def test_an_evaluation_too_costly_for_what_is_left_is_refused(client, flow):
    run = flow.evaluate(1, "evaluation", correct=False)
    for claim in run["claims"]:
        client.post(
            f"/api/claims/{claim['claim_id']}/model-calls",
            json={
                "run_id": run["run_id"],
                "model": "m",
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
                "cost": "0.010000000",
            },
        )
    body = {
        "concurrency": 5,
        "model": "m",
        "reasoning_effort": "low",
        "configuration_version": 1,
        "parent_run_id": flow.stretch,
        "eval_set": "held_out",
        "check_spending": True,
    }

    refused = client.post(flow.url("evaluations"), json=body)

    assert refused.status_code == 409
    assert "likely to cost" in refused.json()["detail"]


def improver_call(client, flow, cost="0.600000000"):
    return client.post(
        flow.url("calls"),
        json={
            "model": "openai/gpt-6-luna",
            "input_tokens": 100,
            "output_tokens": 10,
            "total_tokens": 110,
            "cost": cost,
        },
    )


def test_a_round_that_spent_its_limit_starts_no_new_claim(client, flow):
    run = flow.evaluate(1, "evaluation", correct=False, worked=0)
    assert client.get(f"/api/runs/{run['run_id']}/may-start-claim").json() == {
        "may_start": True
    }

    improver_call(client, flow)

    assert client.get(f"/api/runs/{run['run_id']}/may-start-claim").json() == {
        "may_start": False
    }


def test_a_run_outside_a_round_may_always_start_a_claim(client):
    run = client.post(
        "/api/runs/dispatch",
        json={**IMPROVER, "concurrency": 1, "configuration_version": 1},
    ).json()

    assert client.get(f"/api/runs/{run['run_id']}/may-start-claim").json() == {
        "may_start": True
    }


def test_an_evaluation_cut_short_ends_stopped_and_its_version_is_rolled_back(
    client, flow
):
    flow.first_evaluations(correct=True)
    flow.decide(flow.propose().json()["proposal_id"])
    cut_short = flow.evaluate(2, "evaluation", correct=True, worked=3)
    flow.evaluate(2, "held_out", correct=True)
    flow.evaluate(2, "held_out", correct=True)

    run = client.get(f"/api/runs/{cut_short['run_id']}").json()
    verdict = client.post(flow.url("verdict")).json()

    assert run["status"] == "stopped"
    assert verdict["verdict"] == "rolled back"
    assert "did not all finish" in verdict["reason"]
    assert current_version(client) == 1


def test_a_stopped_round_before_its_verdict_leaves_the_current_version(client, flow):
    flow.first_evaluations(correct=False)
    flow.decide(flow.propose().json()["proposal_id"])

    stopped = client.post(f"/api/rounds/{flow.round_id}/stop").json()

    assert stopped["stage"] == "stopped"
    assert current_version(client) == 1
    assert client.get("/api/configurations").json()[1]["verdict"] is None


def test_a_stopped_round_after_its_verdict_keeps_it(client, flow):
    flow.first_evaluations(correct=False)
    flow.decide(flow.propose().json()["proposal_id"])
    for eval_set in ("evaluation", "held_out", "held_out"):
        flow.evaluate(2, eval_set, correct=True)
    assert client.post(flow.url("verdict")).json()["verdict"] == "kept"

    client.post(f"/api/rounds/{flow.round_id}/stop")

    assert current_version(client) == 2
    assert client.get(f"/api/rounds/{flow.round_id}").json()["stage"] == "stopped"


def test_the_backend_refuses_what_a_stopped_round_records(client, flow):
    flow.first_evaluations()
    proposal = flow.propose().json()
    client.post(f"/api/rounds/{flow.round_id}/stop")

    refused = [
        improver_call(client, flow),
        flow.propose(),
        client.post(flow.url("stage"), json={"stage": "verdict", "progress": 0}),
        client.post(flow.url("verdict")),
        client.get(flow.url("view")),
        client.post(
            f"/api/improver/proposals/{proposal['proposal_id']}/decision",
            json={
                "approved": True,
                "handler_id": "HND-01",
                "rejection_reason": "",
                **IMPROVER,
            },
        ),
    ]

    assert [r.status_code for r in refused] == [409] * 6
    assert "stopped" in refused[0].json()["detail"]


def test_a_round_cannot_be_stopped_twice(client, flow):
    client.post(f"/api/rounds/{flow.round_id}/stop")

    assert client.post(f"/api/rounds/{flow.round_id}/stop").status_code == 409


def test_a_restart_stops_a_round_that_was_working_but_not_one_waiting(client):
    working = Flow(client)
    client.post("/api/runs/stop-unfinished")
    waiting = Flow(client)
    waiting.propose()
    waiting.end_stretch()

    client.post("/api/runs/stop-unfinished")

    assert client.get(f"/api/rounds/{working.round_id}").json()["stage"] == "stopped"
    assert (
        client.get(f"/api/rounds/{waiting.round_id}").json()["stage"]
        == "change waiting"
    )


def test_a_rounds_cost_is_the_improver_the_claims_and_the_judge(client, flow):
    run = flow.evaluate(1, "evaluation", correct=False)
    for claim in run["claims"][:5]:
        client.post(
            f"/api/claims/{claim['claim_id']}/model-calls",
            json={
                "run_id": run["run_id"],
                "model": "m",
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
                "cost": "0.002000000",
            },
        )
    improver_call(client, flow, cost="0.003000000")

    cost = client.get(f"/api/rounds/{flow.round_id}").json()["cost"]

    # 5 claims at $0.002, the improver's $0.003, and the judge's $0.00004 for 25.
    assert cost == "0.014000000"


def test_a_round_lists_newest_first_with_its_proposals(client):
    first = Flow(client)
    first.propose()
    first.end_stretch()
    second = Flow(client)

    listed = client.get("/api/rounds").json()

    assert [r["round_id"] for r in listed] == [second.round_id, first.round_id]
    assert len(listed[1]["proposals"]) == 1


def test_starting_stopping_and_deciding_need_a_senior_handler(
    client, flow, agent_stub, as_handler
):
    proposal = flow.propose().json()
    marcus = as_handler(MARCUS)
    requests = [
        ("post", "/api/rounds", None),
        ("post", f"/api/rounds/{flow.round_id}/stop", None),
        (
            "post",
            f"/api/proposals/{proposal['proposal_id']}/decision",
            {"decision": "approve", "reason": ""},
        ),
    ]

    for method, path, body in requests:
        assert (
            getattr(client, method)(path, json=body, headers=marcus).status_code == 403
        )
        anonymous = getattr(client, method)(
            path, json=body, headers={"Authorization": ""}
        )
        assert anonymous.status_code == 401
    assert agent_stub.calls == []


def test_starting_a_round_asks_the_service_and_passes_on_its_refusal(
    client, agent_stub
):
    started = client.post("/api/rounds")
    assert started.status_code == 202
    assert started.json() == {"round_id": 5}
    assert agent_stub.calls == ["/api/rounds"]
    assert agent_stub.bodies == [{"handler_id": "HND-01"}]

    agent_stub.refuse = True
    refused = client.post("/api/rounds")
    assert refused.status_code == 409


def test_deciding_asks_the_service_with_the_handler_and_the_reason(
    client, flow, agent_stub
):
    proposal = flow.propose().json()

    client.post(
        f"/api/proposals/{proposal['proposal_id']}/decision",
        json={"decision": "reject", "reason": "Too long."},
    )

    assert agent_stub.calls == [f"/api/proposals/{proposal['proposal_id']}/decision"]
    assert agent_stub.bodies == [
        {"decision": "reject", "handler_id": "HND-01", "reason": "Too long."}
    ]


def test_a_rejection_needs_a_reason(client, flow, agent_stub):
    proposal = flow.propose().json()

    refused = client.post(
        f"/api/proposals/{proposal['proposal_id']}/decision",
        json={"decision": "reject", "reason": " "},
    )

    assert refused.status_code == 422
    assert agent_stub.calls == []


def test_stopping_a_round_tells_the_service(client, flow, agent_stub):
    client.post(f"/api/rounds/{flow.round_id}/stop")

    assert agent_stub.calls == [f"/api/rounds/{flow.round_id}/stop"]


def test_the_configurations_list_carries_each_versions_held_out_scores(client, flow):
    flow.first_evaluations(correct=False)
    flow.decide(flow.propose().json()["proposal_id"])
    for eval_set in ("evaluation", "held_out", "held_out"):
        flow.evaluate(2, eval_set, correct=True)

    first, second = client.get("/api/configurations").json()

    assert first["held_out"]["runs"] == 2
    assert second["held_out"]["runs"] == 2
    assert Decimal(second["held_out"]["accuracy"]) > Decimal(
        first["held_out"]["accuracy"]
    )
    assert (
        client.get(f"/api/rounds/{flow.round_id}").json()["started_by_name"]
        == "Dana Whitfield"
    )


def test_the_rounds_list_takes_the_same_queries_however_many_there_are(
    client, statements_to_get
):
    def a_stopped_round_with_a_proposal_and_a_call():
        flow = Flow(client)
        flow.propose()
        improver_call(client, flow)
        flow.end_stretch()
        client.post(f"/api/rounds/{flow.round_id}/stop")

    a_stopped_round_with_a_proposal_and_a_call()
    one = statements_to_get("/api/rounds")

    a_stopped_round_with_a_proposal_and_a_call()
    a_stopped_round_with_a_proposal_and_a_call()

    assert len(client.get("/api/rounds").json()) == 3
    assert statements_to_get("/api/rounds") == one


def test_the_configurations_list_takes_the_same_queries_however_many_there_are(
    client, flow, statements_to_get
):
    flow.first_evaluations()
    one = statements_to_get("/api/configurations")

    flow.decide(flow.propose().json()["proposal_id"])
    flow.evaluate(2, "evaluation", correct=True)
    flow.evaluate(2, "held_out", correct=True)

    assert len(client.get("/api/configurations").json()) == 2
    assert statements_to_get("/api/configurations") == one
