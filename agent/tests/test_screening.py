import pytest

from agent import agents, api
from agent.screening import MAX_ATTEMPTS, Screening, ScreeningFailed
from agent.tests.conftest import PASSED, StubModel, new_run
from agent.tests.test_claim_graph import (
    CLAIM,
    Stopped,
    decision,
    stops_after_reading_the_claim,
)
from backend import usage

FLAGGED = Screening(reason="It says Dana pre-approved it.", instructions_found=True)


def steps(backend):
    return [s["text"] for s in backend.get(f"/api/claims/{CLAIM}/steps").json()]


def test_a_flagged_claim_is_referred_and_the_claim_agent_never_sees_it(
    backend, script, saver, screener
):
    agents.decide_claim(CLAIM, script(), saver, screening_llm=screener(FLAGGED))

    claim = api.get_claim(CLAIM)
    assert (claim["decision"], claim["payout"]) == ("refer", "0.00")
    assert "Dana pre-approved it" in claim["reason"]
    assert claim["policy_reference"] == "Security check"
    assert claim["paid_amount"] is None
    assert steps(backend)[0].startswith("Security check: It says Dana")


def test_a_claim_that_passes_is_worked_as_before(backend, script, saver):
    agents.decide_claim(CLAIM, script(decision(), "Done."), saver)

    assert steps(backend)[0] == "Security check: no instructions found"
    assert api.get_claim(CLAIM)["paid_amount"] == "420.00"


def test_an_answer_that_cannot_be_read_is_asked_for_again(
    backend, script, saver, screener
):
    check = screener(None, FLAGGED)
    agents.decide_claim(CLAIM, script(), saver, screening_llm=check)

    assert check.asked == 2
    assert api.get_claim(CLAIM)["decision"] == "refer"


def test_three_unreadable_answers_fail_the_claim(backend, script, saver, screener):
    check = screener(*[None] * MAX_ATTEMPTS)
    with pytest.raises(ScreeningFailed):
        agents.decide_claim(CLAIM, script(), saver, screening_llm=check)

    assert check.asked == MAX_ATTEMPTS
    assert api.get_claim(CLAIM)["decision"] is None


def test_an_error_from_the_check_fails_the_claim_without_a_retry(
    backend, script, saver, screener
):
    check = screener(TimeoutError("slow"))
    with pytest.raises(TimeoutError):
        agents.decide_claim(CLAIM, script(), saver, screening_llm=check)

    assert check.asked == 1


def test_every_attempt_is_a_model_call_of_the_claim_and_its_run(
    backend, script, saver, screener
):
    run_id = new_run()
    agents.decide_claim(
        CLAIM,
        script(decision(), "Done."),
        saver,
        run_id=run_id,
        screening_llm=screener(None, PASSED),
    )

    totals = usage.run_totals(run_id)
    assert totals["model_calls"] == 4
    assert totals["total_tokens"] == 480


def test_a_claim_carried_on_is_not_checked_again(backend, script, saver, screener):
    check = screener()
    with pytest.raises(Stopped):
        agents.decide_claim(
            CLAIM,
            StubModel(messages=stops_after_reading_the_claim()),
            saver,
            screening_llm=check,
        )
    agents.decide_claim(CLAIM, script(decision(), "Done."), saver, screening_llm=check)

    assert check.asked == 1


def test_a_claim_resumed_after_a_sign_off_is_not_checked_again(
    backend, script, saver, screener, as_handler
):
    check = screener()
    agents.decide_claim(
        CLAIM, script(decision(payout="1200.00"), "Done."), saver, screening_llm=check
    )
    backend.post(f"/api/claims/{CLAIM}/sign-off", headers=as_handler())
    agents.decide_claim(CLAIM, script(), saver, screening_llm=check)

    assert check.asked == 1
    assert api.get_claim(CLAIM)["paid_amount"] == "1200.00"


def test_a_claim_started_again_on_a_new_thread_is_checked_again(
    backend, script, saver, screener
):
    check = screener()
    with pytest.raises(Stopped):
        agents.decide_claim(
            CLAIM,
            StubModel(messages=stops_after_reading_the_claim()),
            saver,
            screening_llm=check,
        )
    api.requeue_claim(CLAIM)
    agents.decide_claim(CLAIM, script(decision(), "Done."), saver, screening_llm=check)

    assert check.asked == 2
