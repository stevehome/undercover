import time

from langchain_core.messages import HumanMessage

from agent import agents, api, backend_http, heartbeat, resumption
from agent.tests import records
from agent.tests.conftest import StubModel
from agent.tests.test_claim_graph import CLAIM, decision

NOTE = "The receipts don't match the dates."


def send_back(backend, as_handler, note=NOTE):
    return backend.post(
        f"/api/claims/{CLAIM}/send-back", json={"note": note}, headers=as_handler()
    )


def waiting_claim(script, saver, payout="1200.00"):
    agents.decide_claim(CLAIM, script(decision(payout=payout), "Approved."), saver)


class Recording(StubModel):
    """A scripted model that keeps the conversation of each call."""

    seen: list = []

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


def test_a_send_back_gives_the_model_the_note_and_it_decides_again(
    backend, script, saver, as_handler
):
    waiting_claim(script, saver)
    send_back(backend, as_handler)

    agents.decide_claim(CLAIM, script(decision(payout="420.00"), "Revised."), saver)

    claim = api.get_claim(CLAIM)
    assert (claim["status"], claim["paid_amount"]) == ("decided", "420.00")
    assert [d["payout"] for d in claim["sent_back_decisions"]] == ["1200.00"]
    assert claim["paid_amount"] != "1200.00"


def test_the_model_reads_who_sent_it_back_and_how_to_treat_the_note(
    backend, script, saver, as_handler
):
    waiting_claim(script, saver)
    send_back(backend, as_handler)
    llm = Recording(messages=script(decision(payout="420.00"), "Revised.").messages)

    agents.decide_claim(CLAIM, llm, saver)

    sent = [m for m in llm.seen[0] if isinstance(m, HumanMessage)][-1].content
    assert "HND-01" in sent
    assert NOTE in sent
    assert "not an order" in sent
    assert "refer the claim" in sent


def test_a_revised_decision_over_the_limit_waits_again_and_can_be_sent_back_again(
    backend, script, saver, as_handler
):
    waiting_claim(script, saver)
    send_back(backend, as_handler)

    agents.decide_claim(CLAIM, script(decision(payout="1300.00"), "Revised."), saver)
    assert api.get_claim(CLAIM)["status"] == "waiting for sign-off"
    send_back(backend, as_handler, "Still too high.")

    agents.decide_claim(CLAIM, script(decision(payout="420.00"), "Again."), saver)
    claim = api.get_claim(CLAIM)
    assert [d["payout"] for d in claim["sent_back_decisions"]] == ["1200.00", "1300.00"]
    assert claim["paid_amount"] == "420.00"


def test_a_claim_sent_back_that_took_many_calls_gets_all_its_calls_again(
    backend, script, saver, as_handler
):
    reads = [("get_claim", {})] * 25
    agents.decide_claim(
        CLAIM, script(*reads, decision(payout="1200.00"), "Approved."), saver
    )
    send_back(backend, as_handler)

    agents.decide_claim(
        CLAIM, script(*reads[:10], decision(payout="420.00"), "Done."), saver
    )

    assert api.get_claim(CLAIM)["paid_amount"] == "420.00"


def test_a_resume_after_a_send_back_takes_the_claim_once(
    backend, script, saver, as_handler
):
    waiting_claim(script, saver)
    send_back(backend, as_handler)
    assert resumption.refusal(CLAIM, saver) is None

    agents.decide_claim(CLAIM, script(decision(payout="420.00"), "Done."), saver)

    steps = records.step_texts(backend, CLAIM)
    assert steps.count(f"Sent back by Dana Whitfield: {NOTE}") == 1


def test_a_claim_the_agent_took_and_lost_is_carried_on_with_the_note(
    backend, script, saver, as_handler
):
    waiting_claim(script, saver)
    send_back(backend, as_handler)
    api.take_claim(CLAIM)

    agents.decide_claim(CLAIM, script(decision(payout="420.00"), "Done."), saver)

    assert api.get_claim(CLAIM)["paid_amount"] == "420.00"


def test_a_claim_another_agent_has_just_taken_is_left_to_it(
    backend, script, saver, as_handler, monkeypatch
):
    waiting_claim(script, saver)
    send_back(backend, as_handler)

    def taken(claim_id):
        raise backend_http.ApiRefusal(409, "taken")

    monkeypatch.setattr(api, "take_claim", taken)

    message = agents.decide_claim(CLAIM, script(), saver)

    assert message == "CLM-1001 was taken by another agent."
    assert api.get_claim(CLAIM)["status"] == "sent back"


def test_the_heartbeat_tells_every_beat_and_stops_with_the_work():
    told = []

    with heartbeat.beating(lambda: told.append(1), milliseconds=20):
        time.sleep(0.1)
    count = len(told)
    time.sleep(0.06)

    assert count >= 2
    assert len(told) == count
