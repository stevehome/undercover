from decimal import Decimal

import pytest

from agent import agents, api, routes
from agent.direct import DirectRoute
from agent.tests import records
from agent.tools import CLAIM_TOOLS

CLAIM = "CLM-1001"
TERM = ("lookup_term", {"term": "carrier"})
LINE = {"description": "Hotel", "amount": "420.00", "kind": "expense"}
PAYOUT = ("calculate_payout", {"benefit": "trip_delay", "lines": [LINE]})


def decide(kind="approve", payout="420.00"):
    arguments = {
        "decision": kind,
        "payout": payout,
        "reason": "Stubbed.",
        "policy_reference": "Section 3",
    }
    return ("decide_claim", arguments)


def steps(backend):
    return records.step_texts(backend, CLAIM)


@pytest.fixture(params=["direct", "gateway"])
def on_route(request, monkeypatch, signed_gateway_route):
    """Work claims on the direct route, then on the stand-in Gateway's."""
    route = DirectRoute() if request.param == "direct" else signed_gateway_route
    monkeypatch.setattr(routes, "choose", lambda: route)
    return request.param


@pytest.fixture
def on_gateway(gateway, signed_gateway_route, monkeypatch):
    """Work claims on the stand-in Gateway's route, and return the stand-in."""
    monkeypatch.setattr(routes, "choose", lambda: signed_gateway_route)
    return gateway


def test_the_same_tools_decide_and_pay_a_claim_on_either_route(
    backend, script, saver, on_route
):
    reply = script(("get_claim", {}), PAYOUT, decide(), "Approved.")

    agents.decide_claim(CLAIM, reply, saver)

    claim = api.get_claim(CLAIM)
    assert (claim["status"], claim["payout"], claim["paid_amount"]) == (
        "decided",
        "420.00",
        "420.00",
    )
    texts = steps(backend)
    assert "Read the claim, its policy and the customer's claim history" in texts
    assert texts[-2:] == ["Decided: approve for $420.00", "Paid $420.00"]
    claim = api.get_claim(CLAIM)
    assert claim["decided_by"] == "UnderCover Agent, configuration version 1"
    assert claim["manual_version"] == "2026.3"
    assert sum(Decimal(s["amount"]) for s in claim["calculation"]) == Decimal("420.00")


def test_the_gateway_route_calls_the_tools_and_the_payment_as_the_gateways(
    script, saver, monkeypatch, gateway, signed_gateway_route
):
    monkeypatch.setattr(routes, "choose", lambda: signed_gateway_route)

    agents.decide_claim(
        CLAIM, script(("get_claim", {}), PAYOUT, decide(), "Ok."), saver
    )

    assert gateway.names == [
        "undercover-app___get_claim",
        "undercover-app___calculate_payout",
        "undercover-app___decide_claim",
        "undercover-app___pay_claim",
    ]


def test_no_tool_takes_a_claim_a_policy_a_customer_or_the_maker_from_the_model():
    ids = {"claim_id", "policy_id", "customer_id", "decided_by"}
    for tool in CLAIM_TOOLS:
        assert not ids & set(tool.args), tool.name


def test_a_refusal_by_the_app_reaches_the_model_and_the_claim_goes_on(
    backend, script, saver, on_route
):
    refused = decide("decline", "100.00")  # only an approval has a payout

    agents.decide_claim(CLAIM, script(refused, PAYOUT, decide(), "Approved."), saver)

    assert any(s.startswith("Refused by the app: ") for s in steps(backend))
    assert api.get_claim(CLAIM)["status"] == "decided"


def test_a_tool_the_gateways_policy_refuses_is_recorded_as_the_gateways(
    backend, script, saver, on_gateway
):
    on_gateway.denied.add("undercover-context___lookup_term")

    agents.decide_claim(CLAIM, script(TERM, PAYOUT, decide(), "Approved."), saver)

    refusals = [s for s in steps(backend) if s.startswith("Refused by the Gateway: ")]
    assert len(refusals) == 1
    assert "Tool Execution Denied" in refusals[0]
    assert api.get_claim(CLAIM)["status"] == "decided"


def test_a_payment_the_gateway_refuses_waits_for_a_sign_off_which_pays_it_once(
    backend, script, saver, on_gateway, as_handler
):
    on_gateway.denied.add("undercover-app___pay_claim")

    agents.decide_claim(CLAIM, script(PAYOUT, decide(), "Approved."), saver)

    held = api.get_claim(CLAIM)
    assert (held["status"], held["hold_reason"]) == ("waiting for sign-off", "gateway")
    assert held["paid_amount"] is None
    assert steps(backend)[-2].startswith("Refused by the Gateway: ")
    assert steps(backend)[-1] == "Waiting for a handler to sign off $420.00"

    backend.post(f"/api/claims/{CLAIM}/sign-off", headers=as_handler())

    paid = api.get_claim(CLAIM)
    assert (paid["status"], paid["paid_amount"]) == ("decided", "420.00")
    assert paid["signed_off_by"] == "HND-01"
    assert paid["signed_off_on"]
    assert on_gateway.names.count("undercover-app___pay_claim") == 1


CONTEXT_CALLS = [
    ("lookup_term", {"term": "carrier"}),
    ("describe_fields", {"record": "claim"}),
    ("get_plan", {"plan": "premium"}),
    ("get_claim_rules", {}),
    ("search_reference_data", {"query": "tropical storm"}),
    ("search_documents", {"query": "sign off"}),
    ("read_section", {"document": "claims_manual", "number": 14}),
]


def test_all_seven_context_tools_answer_on_either_route(
    backend, script, saver, on_route
):
    reply = script(*CONTEXT_CALLS, PAYOUT, decide(), "Approved.")

    agents.decide_claim(CLAIM, reply, saver)

    texts = steps(backend)
    assert "Looked up the term carrier" in texts
    assert "Looked up the fields of a claim" in texts
    assert "Looked up the premium plan" in texts
    assert "Looked up the claim rules" in texts
    assert "Searched the reference data for tropical storm" in texts
    assert "Searched the documents for sign off" in texts
    assert "Read claims manual section 14: Records" in texts
    assert not any(t.startswith("Refused") for t in texts)


def test_the_gateway_names_the_context_layers_tools_after_its_target(
    script, saver, on_gateway
):
    agents.decide_claim(CLAIM, script(*CONTEXT_CALLS, PAYOUT, decide(), "Done."), saver)

    context_calls = [n for n in on_gateway.names if "context" in n]
    assert context_calls == [
        "undercover-context___lookup_term",
        "undercover-context___describe_fields",
        "undercover-context___get_plan",
        "undercover-context___get_claim_rules",
        "undercover-context___search_reference_data",
        "undercover-context___search_documents",
        "undercover-context___read_section",
    ]


def test_a_section_that_does_not_exist_is_a_refusal_by_the_context_layer(
    backend, script, saver, on_route
):
    missing = ("read_section", {"document": "claims_manual", "number": 99})

    agents.decide_claim(CLAIM, script(missing, PAYOUT, decide(), "Approved."), saver)

    refusals = [s for s in steps(backend) if s.startswith("Refused by")]
    assert len(refusals) == 1
    assert refusals[0].startswith("Refused by the context layer: ")
    assert "no section 99" in refusals[0]
    assert api.get_claim(CLAIM)["status"] == "decided"


def test_an_approval_before_any_calculation_is_refused_and_the_model_puts_it_right(
    backend, script, saver, on_route
):
    agents.decide_claim(CLAIM, script(decide(), PAYOUT, decide(), "Approved."), saver)

    refused = [s for s in steps(backend) if s.startswith("Refused by the app")]
    assert len(refused) == 1
    assert "Claims manual section 14" in refused[0]
    assert "calculation" in refused[0]
    assert api.get_claim(CLAIM)["status"] == "decided"
