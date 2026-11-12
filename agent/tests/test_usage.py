import time
from decimal import Decimal

import pytest

from agent import agents
from agent.tests.conftest import StubModel, new_run
from agent.tests.test_claim_graph import CLAIM, Stopped, decision, sign_off
from backend import usage


def test_each_model_reply_is_recorded_with_its_run(backend, script, saver):
    run_id = new_run()
    agents.decide_claim(CLAIM, script(decision(), "Done."), saver, run_id=run_id)

    totals = usage.run_totals(run_id)
    assert totals["model_calls"] == 2
    assert totals["total_tokens"] == 240
    assert totals["cost"] == Decimal("0.000624")


def test_work_with_no_run_belongs_to_no_run(backend, script, saver):
    agents.decide_claim(CLAIM, script(decision(), "Done."), saver)

    assert usage.run_totals(7)["model_calls"] == 0
    assert usage.run_totals(7)["work_ms"] == 0


def test_two_runs_have_separate_totals(backend, script, saver):
    first, second = new_run(), new_run()
    agents.decide_claim("CLM-1001", script(decision(), "Done."), saver, run_id=first)
    agents.decide_claim("CLM-1002", script(decision(), "Done."), saver, run_id=second)

    assert usage.run_totals(first)["model_calls"] == 2
    assert usage.run_totals(second)["model_calls"] == 2


def test_a_wait_for_sign_off_is_not_counted(backend, script, saver, as_handler):
    run_id = new_run()
    agents.decide_claim(
        CLAIM, script(decision(payout="1200.00"), "Done."), saver, run_id=run_id
    )
    time.sleep(0.5)
    sign_off(backend, as_handler)
    agents.decide_claim(CLAIM, script(), saver, run_id=run_id)

    assert usage.run_totals(run_id)["work_ms"] < 400


def test_a_failed_attempt_still_has_its_work_and_cost(backend, saver):
    def stops_after_a_moment():
        time.sleep(0.2)
        raise Stopped
        yield

    run_id = new_run()
    with pytest.raises(Stopped):
        agents.decide_claim(
            CLAIM, StubModel(messages=stops_after_a_moment()), saver, run_id=run_id
        )

    assert usage.run_totals(run_id)["work_ms"] >= 200
