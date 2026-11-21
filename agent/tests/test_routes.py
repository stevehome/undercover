import pytest

from agent import agents, api, routes
from agent.direct import DirectRoute
from agent.tools import CLAIM_TOOLS

CLAIM = "CLM-1001"
SECTIONS = ("list_sections", {"document": "policy_wording"})
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
    return [s["text"] for s in backend.get(f"/api/claims/{CLAIM}/steps").json()]


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


def test_no_tool_takes_a_claim_a_policy_or_a_customer_from_the_model():
    for tool in CLAIM_TOOLS:
        assert not {"claim_id", "policy_id", "customer_id"} & set(tool.args), tool.name


def test_a_refusal_by_the_app_reaches_the_model_and_the_claim_goes_on(
    backend, script, saver, on_route
):
    refused = decide("decline", "100.00")  # only an approval has a payout

    agents.decide_claim(CLAIM, script(refused, decide(), "Approved."), saver)

    assert any(s.startswith("Refused by the app: ") for s in steps(backend))
    assert api.get_claim(CLAIM)["status"] == "decided"


def test_a_tool_the_gateways_policy_refuses_is_recorded_as_the_gateways(
    backend, script, saver, on_gateway
):
    on_gateway.denied.add("undercover-app___list_sections")

    agents.decide_claim(CLAIM, script(SECTIONS, PAYOUT, decide(), "Approved."), saver)

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
