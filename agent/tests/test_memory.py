import logging

from botocore.exceptions import ClientError
from langchain_core.messages import AIMessage, HumanMessage

from agent import agents, api
from agent.memory import CustomerMemory
from agent.screening import Screening
from agent.tests import records
from agent.tests.conftest import STUB_MODEL, create_evaluation
from agent.tests.stand_in_memory import StandInMemory
from agent.tests.test_claim_graph import CLAIM, decision, sign_off
from agent.tools import claim_tools

CUSTOMER = "CUS-3001"
THROTTLED = ClientError(
    {"Error": {"Code": "ThrottlingException", "Message": "Slow down"}}, "CreateEvent"
)


def steps(backend):
    return records.step_texts(backend, CLAIM)


def test_a_decided_claim_is_saved_as_two_events_for_its_customer_and_claim(
    backend, script, saver, memory_on
):
    agents.decide_claim(CLAIM, script(decision(), "Approved."), saver)

    claim = api.get_claim(CLAIM)
    (claim_event, decision_event) = memory_on.events
    assert claim_event[:2] == ((CUSTOMER, CLAIM), "claim")
    assert decision_event[:2] == ((CUSTOMER, CLAIM), "decision")
    asked, answered = claim_event[2]["message"], decision_event[2]["message"]
    assert isinstance(asked, HumanMessage)
    assert isinstance(answered, AIMessage)
    for part in (
        claim["summary"],
        claim["claim_type"],
        claim["incident_date"],
        claim["incident_location"],
        claim["items"][0]["description"],
    ):
        assert part in asked.content
    assert claim["story"] not in asked.content
    for part in ("approve", "$420.00", "Section 3", "Stubbed."):
        assert part in answered.content
    assert "Saved the claim and its decision to the customer's memory" in steps(backend)


def test_a_decline_is_saved_too_without_a_payout(backend, script, saver, memory_on):
    agents.decide_claim(CLAIM, script(decision("decline", "0.00"), "Done."), saver)

    answered = memory_on.events[1][2]["message"].content
    assert "decline" in answered
    assert "payout" not in answered


def test_nothing_is_saved_for_a_claim_the_check_referred(
    backend, script, saver, memory_on, screener
):
    flagged = Screening(reason="It tells us to approve.", instructions_found=True)

    agents.decide_claim(CLAIM, script(), saver, screening_llm=screener(flagged))

    assert memory_on.events == []


def test_nothing_is_saved_for_an_evaluations_copy_of_a_claim(
    backend, script, saver, memory_on
):
    run_id = create_evaluation(1, "held_out", True, STUB_MODEL)
    copy = api.get_run(run_id)["claims"][0]["claim_id"]

    agents.decide_claim(
        copy, script(decision("decline", "0.00"), "Done."), saver, run_id
    )

    assert memory_on.events == []


def test_the_memory_tool_is_there_only_when_memory_is_on():
    assert "search_memory" not in [t.name for t in claim_tools(False)]
    assert "search_memory" in [t.name for t in claim_tools(True)]


def test_a_search_stays_with_the_claims_customer_and_leaves_out_the_claim_in_hand():
    store = StandInMemory()
    store.memories = [
        (("customers", CUSTOMER, "facts"), "Travels with a service dog."),
        (("customers", CUSTOMER, "claims", "CLM-0900"), "Earlier: lost a bag."),
        (("customers", CUSTOMER, "claims", CLAIM), "This claim's own summary."),
        (("customers", "CUS-3002", "facts"), "Another customer's fact."),
    ]

    found = CustomerMemory(store).search(CUSTOMER, "bags", CLAIM)

    assert found == ["Travels with a service dog.", "Earlier: lost a bag."]
    assert store.searches == [(("customers", CUSTOMER), "bags")]


def test_the_model_searches_the_memory_of_its_own_claims_customer(
    backend, script, saver, memory_on
):
    memory_on.memories = [(("customers", CUSTOMER, "facts"), "A returning customer.")]
    search = ("search_memory", {"query": "earlier claims"})

    agents.decide_claim(CLAIM, script(search, decision(), "Done."), saver)

    assert memory_on.searches == [(("customers", CUSTOMER), "earlier claims")]
    assert "Searched the customer's memory for earlier claims" in steps(backend)


def test_a_claim_over_the_limit_is_saved_once_after_its_sign_off(
    backend, script, saver, memory_on, as_handler
):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Done."), saver)
    assert memory_on.events == []

    agents.decide_claim(CLAIM, script(), saver)
    assert memory_on.events == []
    sign_off(backend, as_handler)
    agents.decide_claim(CLAIM, script(), saver)
    assert len(memory_on.events) == 2

    agents.decide_claim(CLAIM, script(), saver)
    assert len(memory_on.events) == 2


def test_when_agentcore_cannot_be_reached_the_claim_keeps_its_decision(
    backend, script, saver, memory_on, caplog
):
    memory_on.failure = THROTTLED

    with caplog.at_level(logging.WARNING):
        agents.decide_claim(CLAIM, script(decision(), "Approved."), saver)

    claim = api.get_claim(CLAIM)
    assert (claim["status"], claim["paid_amount"]) == ("decided", "420.00")
    assert "Could not save CLM-1001 to the memory" in caplog.text
    assert not any("Saved the claim" in s for s in steps(backend))


def test_a_search_agentcore_cannot_answer_reaches_the_model_as_a_refusal(
    backend, script, saver, memory_on
):
    memory_on.failure = THROTTLED
    search = ("search_memory", {"query": "earlier claims"})

    agents.decide_claim(CLAIM, script(search, decision(), "Done."), saver)

    assert any(s.startswith("Refused by the memory: ") for s in steps(backend))
    assert api.get_claim(CLAIM)["status"] == "decided"
