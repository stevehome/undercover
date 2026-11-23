import time

import pytest

from agent import agents, api, dispatcher, heartbeat, resumption
from agent.tests import records
from agent.tests.conftest import (
    STUB_MODEL,
    create_dispatch,
    create_evaluation,
)
from agent.tests.invocations import invoke, wait_until_idle
from agent.tests.test_claim_graph import CLAIM, decision

RESUME = {"operation": "resume_claim", "claim_id": CLAIM}
IMPROVER = {"model": "openai/gpt-6-luna", "reasoning_effort": "medium"}


def work_run(run_id):
    return {"operation": "work_run", "run_id": run_id}


def new_round(backend):
    created = backend.post(
        "/api/improver/rounds", json={"handler_id": "HND-01", **IMPROVER}
    )
    return created.json()["round_id"], created.json()["run_id"]


def test_a_run_is_worked_in_the_background_with_its_concurrency(agentcore, dispatches):
    run_id = create_dispatch(4)

    response = invoke(agentcore, work_run(run_id))

    assert response.json() == {"accepted": True}
    wait_until_idle(agentcore)
    assert dispatches == [(run_id, 4)]


def test_an_evaluation_is_worked_the_same_way(agentcore, dispatches):
    run_id = create_evaluation(5, "held_out", True)

    invoke(agentcore, work_run(run_id))

    wait_until_idle(agentcore)
    assert dispatches == [(run_id, 5)]


def test_a_run_that_is_not_running_is_refused(agentcore, dispatches):
    run_id = create_dispatch(1)
    api.finish_run(run_id)

    response = invoke(agentcore, work_run(run_id))

    assert response.json() == {"refused": f"Run {run_id} is not a run that is going"}
    assert dispatches == []


def test_a_stretch_of_a_round_is_not_worked_as_a_run(agentcore, dispatches, backend):
    _, stretch = new_round(backend)

    response = invoke(agentcore, work_run(stretch))

    assert "refused" in response.json()


def test_a_run_that_does_not_exist_is_refused(agentcore, dispatches):
    assert "refused" in invoke(agentcore, work_run(999)).json()


def test_the_agent_marks_nothing_stopped_when_it_gets_ready(agentcore):
    run_id = create_dispatch(1)

    invoke(agentcore, {"operation": "health"})

    assert api.get_run(run_id)["status"] == "running"


def test_a_failed_run_stops_only_itself_with_the_reason(agentcore, monkeypatch):
    finished = create_dispatch(1)
    api.finish_run(finished)

    def fails(run_id, concurrency):
        raise RuntimeError("The model fell over")

    monkeypatch.setattr(dispatcher, "run_dispatch", fails)
    running = create_dispatch(1)

    invoke(agentcore, work_run(running))
    wait_until_idle(agentcore)

    stopped = api.get_run(running)
    assert stopped["status"] == "stopped"
    assert stopped["stopped_reason"] == "The agent's work failed: RuntimeError"
    assert api.get_run(finished)["status"] == "finished"


def test_a_run_is_heard_from_while_it_works(agentcore, monkeypatch):
    run_id = create_dispatch(1)
    beating = heartbeat.beating
    monkeypatch.setattr(
        heartbeat, "beating", lambda tell: beating(tell, milliseconds=10)
    )
    monkeypatch.setattr(dispatcher, "run_dispatch", lambda *_: time.sleep(0.1))

    invoke(agentcore, work_run(run_id))
    wait_until_idle(agentcore)

    assert api.get_run(run_id)["heard_from_on"] is not None


def test_a_round_is_worked_from_its_first_evaluations(agentcore, stretches, backend):
    round_id, run_id = new_round(backend)

    response = invoke(agentcore, {"operation": "work_round", "round_id": round_id})

    assert response.json() == {"accepted": True}
    wait_until_idle(agentcore)
    assert stretches == [(round_id, run_id, None)]


def test_a_round_that_is_closed_is_refused(agentcore, stretches, backend):
    round_id, _ = new_round(backend)
    backend.post(f"/api/rounds/{round_id}/stop")

    response = invoke(agentcore, {"operation": "work_round", "round_id": round_id})

    assert "refused" in response.json()
    assert stretches == []


def reviewed(backend, kind):
    """A round whose proposal a handler has reviewed, with the stretch it began."""
    round_id, stretch = new_round(backend)
    backend.post(f"/api/runs/{stretch}/finish")
    change = {
        "instructions": "New.\n",
        "model": "openai/gpt-6-luna",
        "reasoning_effort": "low",
    }
    proposal = backend.post(
        f"/api/improver/rounds/{round_id}/proposals",
        json={"kind": "change", "content": change, "reason": "A rule."},
    ).json()["proposal_id"]
    backend.post(
        f"/api/improver/proposals/{proposal}/decision",
        json={
            "approved": kind == "approve",
            "handler_id": "HND-01",
            "rejection_reason": "Too long." if kind == "reject" else "",
            **IMPROVER,
        },
    )
    return round_id, proposal


def carry_on(round_id, proposal_id):
    return {
        "operation": "carry_round_on",
        "round_id": round_id,
        "proposal_id": proposal_id,
    }


def test_a_round_is_carried_on_with_the_review_the_agent_reads_from_the_app(
    agentcore, stretches, backend
):
    round_id, proposal = reviewed(backend, "reject")

    response = invoke(agentcore, carry_on(round_id, proposal))

    assert response.json() == {"accepted": True}
    wait_until_idle(agentcore)
    [(_, run_id, resume)] = stretches
    assert resume["decisions"][0]["type"] == "reject"
    assert "Too long." in resume["decisions"][0]["message"]
    assert api.get_run(run_id)["round_id"] == round_id


def test_an_approval_carries_the_round_on_as_approved(agentcore, stretches, backend):
    round_id, proposal = reviewed(backend, "approve")

    invoke(agentcore, carry_on(round_id, proposal))

    wait_until_idle(agentcore)
    assert stretches[0][2]["decisions"] == [{"type": "approve"}]


def test_a_proposal_nobody_reviewed_is_refused(agentcore, stretches, backend):
    round_id, stretch = new_round(backend)
    backend.post(f"/api/runs/{stretch}/finish")
    change = {
        "instructions": "New.\n",
        "model": "openai/gpt-6-luna",
        "reasoning_effort": "low",
    }
    proposal = backend.post(
        f"/api/improver/rounds/{round_id}/proposals",
        json={"kind": "change", "content": change, "reason": "A rule."},
    ).json()["proposal_id"]

    response = invoke(agentcore, carry_on(round_id, proposal))

    assert "refused" in response.json()
    assert stretches == []


def test_a_proposal_of_another_round_is_refused(agentcore, stretches, backend):
    round_id, proposal = reviewed(backend, "reject")

    response = invoke(agentcore, carry_on(round_id + 1, proposal))

    assert "refused" in response.json()


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
    create_dispatch(1, STUB_MODEL)

    assert invoke(agentcore, RESUME).json() == {"accepted": True}
    wait_until_idle(agentcore)


def test_the_health_check_answers_healthy(backend, agentcore):
    assert invoke(agentcore, {"operation": "health"}).json() == {"healthy": True}
