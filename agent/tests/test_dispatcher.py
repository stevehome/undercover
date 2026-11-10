import threading
import time
from decimal import Decimal

import pytest
from langchain_core.exceptions import ModelRateLimitError, ModelTimeoutError
from langgraph.types import RetryPolicy

from agent import agents, api, dispatcher, work

DECISION = {
    "decision": "approve",
    "payout": Decimal("100.00"),
    "reason": "Stubbed.",
    "policy_reference": "Section 1",
}
FAST = RetryPolicy(initial_interval=0.01, max_attempts=3, retry_on=work.WAIT_AND_RETRY)


def start(n=3):
    return api.create_dispatch(n, "stub/model", "low")


def run(run_id, decide, n=3):
    graph = dispatcher.build_dispatcher(decide, FAST)
    graph.invoke(
        dispatcher.Dispatch(run_id=run_id, claims=[], results=[]),
        {"max_concurrency": n},
    )
    api.finish_run(run_id)
    return {c["claim_id"]: c for c in api.get_run(run_id)["claims"]}


def approve(claim_id, run_id):
    api.record_step(claim_id, "started")
    api.decide_claim(claim_id, **DECISION)
    return "Approved."


@pytest.mark.parametrize("n", [1, 3, 25])
def test_never_more_than_n_claims_are_worked_at_once(backend, n):
    inside = 0
    most = 0
    lock = threading.Lock()

    def decide(claim_id, run_id):
        nonlocal inside, most
        with lock:
            inside += 1
            most = max(most, inside)
        time.sleep(0.2 if n > 1 else 0)
        approve(claim_id, run_id)
        with lock:
            inside -= 1
        return "Approved."

    rows = run(start(n), decide, n)

    assert len(rows) == 25
    assert {r["status"] for r in rows.values()} == {"done"}
    assert most == min(n, 25)


def test_every_claim_in_progress_or_waiting_is_worked_oldest_first(backend):
    api.record_step("CLM-1003", "started")
    worked = []

    def decide(claim_id, run_id):
        worked.append(claim_id)
        return approve(claim_id, run_id)

    run_id = start()
    run(run_id, decide, 1)

    assert worked == [c["claim_id"] for c in api.get_run(run_id)["claims"]]
    assert worked[0] == "CLM-1001"
    assert "CLM-1003" in worked


def test_a_claim_in_progress_carries_on_as_the_same_attempt(backend):
    run_id = start()
    api.update_run_claim(run_id, "CLM-1001", "in progress", "")

    rows = run(run_id, approve)

    assert rows["CLM-1001"]["attempts"] == 1
    assert rows["CLM-1001"]["status"] == "done"


@pytest.mark.parametrize("error", [ModelRateLimitError, ModelTimeoutError])
def test_a_rate_limit_waits_and_carries_on_as_the_same_attempt(backend, error):
    tries = []

    def decide(claim_id, run_id):
        if claim_id == "CLM-1001":
            tries.append(claim_id)
            if len(tries) == 1:
                api.record_step(claim_id, "started")
                raise error("slow down")
        return approve(claim_id, run_id)

    rows = run(start(), decide)

    assert len(tries) == 2
    assert rows["CLM-1001"]["status"] == "done"
    assert rows["CLM-1001"]["attempts"] == 1
    assert api.get_claim("CLM-1001")["thread"] == 1


def test_a_claim_still_rate_limited_stays_in_progress_and_the_run_finishes(backend):
    def decide(claim_id, run_id):
        if claim_id == "CLM-1001":
            api.record_step(claim_id, "started")
            raise ModelRateLimitError("slow down")
        return approve(claim_id, run_id)

    run_id = start()
    rows = run(run_id, decide)

    assert rows["CLM-1001"]["status"] == "still in progress"
    assert rows["CLM-1001"]["note"].endswith("ModelRateLimitError")
    assert api.get_claim("CLM-1001")["status"] == "in progress"
    assert {r["status"] for k, r in rows.items() if k != "CLM-1001"} == {"done"}
    assert api.get_run(run_id)["status"] == "finished"


def test_a_claim_that_fails_is_tried_once_more_then_left_for_a_handler(backend):
    attempts = []

    def decide(claim_id, run_id):
        if claim_id in ("CLM-1001", "CLM-1002"):
            attempts.append(claim_id)
            api.record_step(claim_id, "started")
            if claim_id == "CLM-1001" or len(attempts) < 4:
                raise RuntimeError("boom")
        return approve(claim_id, run_id)

    rows = run(start(), decide)

    assert rows["CLM-1001"]["status"] == "left for a handler"
    assert attempts.count("CLM-1001") == 2
    assert rows["CLM-1002"]["status"] == "done"
    assert rows["CLM-1002"]["attempts"] == 2
    assert rows["CLM-1003"]["status"] == "done"


def test_a_claim_another_agent_holds_is_skipped_and_counted_done(backend):
    def decide(claim_id, run_id):
        return f"{claim_id} is being worked by another agent."

    rows = run(start(), decide)

    assert {r["note"] for r in rows.values()} == {work.BUSY_NOTE}
    assert {r["status"] for r in rows.values()} == {"done"}


def test_no_claim_is_decided_twice(backend):
    decisions = []

    def decide(claim_id, run_id):
        decisions.append(claim_id)
        return approve(claim_id, run_id)

    run(start(), decide)

    assert len(decisions) == len(set(decisions)) == 25


def test_a_held_approval_in_an_evaluation_is_finished_and_its_progress_cleared(
    backend, script, saver
):
    run_id = api.create_evaluation(1, "held_out", True, "stub/model", "low")
    copies = [c["claim_id"] for c in api.get_run(run_id)["claims"]]
    approve = (
        "decide_claim",
        {
            "decision": "approve",
            "payout": "1200.00",
            "reason": "Stubbed.",
            "policy_reference": "S1",
        },
    )

    def decide(claim_id, run_id):
        return agents.decide_claim(claim_id, script(approve, "Done."), saver, run_id)

    rows = run(run_id, decide, 1)

    assert {r["status"] for r in rows.values()} == {"done"}
    assert {r["note"] for r in rows.values()} == {
        "Approved $1,200.00, waiting for sign-off"
    }
    assert [api.get_claim(c)["status"] for c in copies] == ["waiting for sign-off"] * 5
    assert list(saver.list(None)) == []
