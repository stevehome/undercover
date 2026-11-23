import pytest

from agent import agents, api, resumption
from agent.tests import records
from agent.tests.conftest import STUB_MODEL
from agent.tests.invocations import invoke, wait_until_idle
from agent.tests.test_claim_graph import CLAIM, decision

DISPATCH = {"operation": "start_dispatch", "concurrency": 4}
EVALUATION = {
    "operation": "start_evaluation",
    "concurrency": 5,
    "eval_set": "held_out",
    "tiny": True,
}
ROUND = {"operation": "start_round", "handler_id": "HND-01"}
RESUME = {"operation": "resume_claim", "claim_id": CLAIM}


def test_a_start_is_accepted_at_once_and_works_the_run_in_the_background(
    backend, agentcore, dispatches
):
    response = invoke(agentcore, DISPATCH)

    assert response.status_code == 200
    run = api.get_run(response.json()["run_id"])
    assert response.json()["accepted"] is True
    assert (run["status"], run["concurrency"], run["kind"]) == (
        "running",
        4,
        "dispatch",
    )
    wait_until_idle(agentcore)
    assert dispatches == [(run["run_id"], 4)]


def test_a_second_start_is_refused_while_a_run_is_going(backend, agentcore, dispatches):
    invoke(agentcore, DISPATCH)

    second = invoke(agentcore, DISPATCH)

    assert second.status_code == 200
    assert list(second.json()) == ["refused"]
    wait_until_idle(agentcore)
    assert len(dispatches) == 1


def test_the_run_records_the_model_and_effort(
    backend, agentcore, dispatches, monkeypatch
):
    monkeypatch.delenv("MODEL_NAME", raising=False)

    run_id = invoke(agentcore, DISPATCH).json()["run_id"]

    run = api.get_run(run_id)
    assert (run["model"], run["reasoning_effort"]) == ("openai/gpt-6-luna", "low")


def test_an_evaluation_starts_on_its_set_and_is_refused_while_a_run_is_going(
    backend, agentcore, dispatches
):
    first = invoke(agentcore, EVALUATION)

    run = api.get_run(first.json()["run_id"])
    assert (run["kind"], run["eval_set"], run["tiny"], len(run["claims"])) == (
        "evaluation",
        "held_out",
        True,
        5,
    )
    wait_until_idle(agentcore)
    assert dispatches == [(run["run_id"], 5)]
    assert "refused" in invoke(agentcore, EVALUATION).json()


def test_starting_a_round_answers_at_once_and_works_it_in_the_background(
    backend, agentcore, stretches
):
    response = invoke(agentcore, ROUND)

    wait_until_idle(agentcore)
    [(round_id, run_id, resume)] = stretches
    assert response.json() == {"accepted": True, "round_id": round_id}
    assert resume is None
    stretch = api.get_run(run_id)
    assert (stretch["kind"], stretch["status"], stretch["round_id"]) == (
        "improver",
        "running",
        round_id,
    )


def test_a_second_round_is_refused_while_a_run_is_going(backend, agentcore, stretches):
    invoke(agentcore, ROUND)

    second = invoke(agentcore, ROUND)

    assert "refused" in second.json()
    wait_until_idle(agentcore)
    assert len(stretches) == 1


def propose(backend, agentcore, stretches):
    """Start a round and have it propose a change, as the improver's stretch does."""
    invoke(agentcore, ROUND)
    wait_until_idle(agentcore)
    round_id, run_id, _ = stretches[0]
    backend.post(f"/api/runs/{run_id}/finish")
    change = {
        "instructions": "New.\n",
        "model": "openai/gpt-6-luna",
        "reasoning_effort": "low",
    }
    proposal = backend.post(
        f"/api/improver/rounds/{round_id}/proposals",
        json={"kind": "change", "content": change, "reason": "A rule."},
    ).json()
    return proposal["proposal_id"]


def decision_of(proposal_id, kind, reason):
    return {
        "operation": "decide_proposal",
        "proposal_id": proposal_id,
        "decision": kind,
        "handler_id": "HND-01",
        "reason": reason,
    }


def test_a_decision_is_recorded_before_the_improver_is_resumed(
    backend, agentcore, stretches
):
    proposal_id = propose(backend, agentcore, stretches)

    response = invoke(agentcore, decision_of(proposal_id, "reject", "Too long."))

    assert response.json() == {"accepted": True, "proposal_id": proposal_id}
    proposal = backend.get(f"/api/proposals/{proposal_id}").json()
    assert (proposal["status"], proposal["rejection_reason"]) == (
        "rejected",
        "Too long.",
    )
    wait_until_idle(agentcore)
    [_, (round_id, run_id, resume)] = stretches
    assert resume["decisions"][0]["type"] == "reject"
    assert "Too long." in resume["decisions"][0]["message"]
    assert api.get_run(run_id)["round_id"] == round_id


def test_a_decision_while_a_run_is_going_is_refused_and_records_nothing(
    backend, agentcore, stretches
):
    proposal_id = propose(backend, agentcore, stretches)
    api.create_dispatch(1, STUB_MODEL)

    response = invoke(agentcore, decision_of(proposal_id, "approve", ""))

    assert "refused" in response.json()
    assert backend.get(f"/api/proposals/{proposal_id}").json()["status"] == "pending"
    assert len(backend.get("/api/configurations").json()) == 1
    wait_until_idle(agentcore)
    assert len(stretches) == 1


@pytest.fixture
def resuming(monkeypatch, saver, script):
    """The agent's resume, working on this test's saver and a stub model."""
    worked = []

    def work(claim_id):
        worked.append(claim_id)
        return agents.decide_claim(claim_id, script(), saver)

    monkeypatch.setattr(resumption, "work", work)
    refusal = resumption.refusal
    monkeypatch.setattr(
        resumption, "refusal", lambda claim_id: refusal(claim_id, saver)
    )
    return worked


def test_the_agent_carries_on_with_a_signed_off_claim(
    backend, agentcore, script, saver, resuming
):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Done."), saver)
    backend.post(f"/api/claims/{CLAIM}/sign-off")

    response = invoke(agentcore, RESUME)

    assert response.json() == {"accepted": True}
    wait_until_idle(agentcore)
    assert resuming == [CLAIM]
    assert "Signed off by HND-01" in records.step_texts(backend, CLAIM)


def test_a_claim_nobody_signed_off_is_refused_with_its_reason(
    backend, agentcore, script, saver, resuming
):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Done."), saver)

    response = invoke(agentcore, RESUME)

    assert response.json() == {
        "refused": "CLM-1001 is waiting for a handler to sign off"
    }
    assert resuming == []


def test_a_claim_that_is_not_paused_is_refused(
    backend, agentcore, script, saver, resuming
):
    agents.decide_claim(CLAIM, script(decision(), "Done."), saver)

    response = invoke(agentcore, RESUME)

    assert response.json() == {"refused": "CLM-1001 is not waiting for an answer"}


def test_a_claim_that_does_not_exist_is_refused(backend, agentcore, resuming):
    response = invoke(agentcore, {**RESUME, "claim_id": "CLM-9999"})

    assert "CLM-9999" in response.json()["refused"]


def test_a_resume_is_answered_at_once_beside_a_dispatch(
    backend, agentcore, script, saver, resuming
):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Done."), saver)
    backend.post(f"/api/claims/{CLAIM}/sign-off")
    api.create_dispatch(1, STUB_MODEL)

    assert invoke(agentcore, RESUME).json() == {"accepted": True}
    wait_until_idle(agentcore)


def test_the_health_check_answers_healthy(backend, agentcore):
    assert invoke(agentcore, {"operation": "health"}).json() == {"healthy": True}
