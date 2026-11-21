import asyncio
from decimal import Decimal

import httpx
import pytest
from mcp.shared.exceptions import McpError

from agent.api import Line
from agent.gateway import GatewayRoute
from agent.mcp_connection import McpConnection
from agent.refusals import BY_APP, BY_CONTEXT_LAYER, BY_GATEWAY, Refusal
from agent.tests import gateway_stand_in as stand_in
from agent.tests.gateway_stand_in import StandInGateway
from agent.tool_route import APP, CONTEXT

CLAIM = "CLM-1001"
LINE = Line(description="Hotel", amount=Decimal("420.00"), kind="expense")


def test_the_gateway_names_each_tool_after_its_target(gateway, signed_gateway_route):
    claim = signed_gateway_route.call(APP, "get_claim", {"claim_id": CLAIM})

    assert gateway.names == ["undercover-app___get_claim"]
    assert claim["claim_id"] == CLAIM


def test_every_request_is_signed_for_bedrock_agentcore(gateway, signed_gateway_route):
    signed_gateway_route.call(APP, "get_claim", {"claim_id": CLAIM})

    authorization = gateway.calls[0]["authorization"]
    assert "Credential=AKIATESTKEY/" in authorization
    assert "/us-east-1/bedrock-agentcore/aws4_request" in authorization


def test_an_amount_goes_to_the_gateway_as_a_number(gateway, signed_gateway_route):
    gateway.tools["undercover-app___pay_claim"] = lambda _: ("{}", False)
    arguments = {"claim_id": CLAIM, "amount": Decimal("420.00")}
    signed_gateway_route.call(APP, "pay_claim", arguments)
    signed_gateway_route.call(
        APP,
        "calculate_payout",
        {
            "claim_id": CLAIM,
            "benefit": "trip_delay",
            "lines": [LINE],
            "paid_by_others": Decimal(0),
        },
    )

    paid, calculated = (call["arguments"] for call in gateway.calls)
    assert paid["amount"] == 420.0
    assert isinstance(paid["amount"], float)
    assert calculated["lines"][0]["amount"] == 420.0
    assert calculated["paid_by_others"] == 0


def test_a_tool_the_app_refuses_is_a_refusal_by_the_app(gateway, signed_gateway_route):
    with pytest.raises(Refusal) as refused:
        signed_gateway_route.call(APP, "get_claim", {"claim_id": "CLM-9999"})

    assert refused.value.source == BY_APP
    assert "No claim CLM-9999" in refused.value.detail


def test_a_tool_the_context_layer_refuses_is_a_refusal_by_it():
    gateway = StandInGateway()
    gateway.tools["undercover-context___lookup_term"] = lambda _: ("No such term", True)
    route = _route(gateway)

    with pytest.raises(Refusal) as refused:
        route.call(CONTEXT, "lookup_term", {"term": "x"})

    assert refused.value.source == BY_CONTEXT_LAYER


def test_a_call_the_policy_refuses_is_a_refusal_by_the_gateway(
    gateway, signed_gateway_route
):
    gateway.denied.add("undercover-app___pay_claim")

    with pytest.raises(Refusal) as refused:
        signed_gateway_route.call(
            APP, "pay_claim", {"claim_id": CLAIM, "amount": Decimal("4800.00")}
        )

    assert refused.value.source == BY_GATEWAY
    assert "Tool Execution Denied" in refused.value.detail


def test_a_protocol_error_that_is_not_a_denial_is_not_hidden(
    gateway, signed_gateway_route, monkeypatch
):
    gateway.denied.add("undercover-app___get_claim")
    monkeypatch.setattr(stand_in, "DENIED", "Internal error")

    with pytest.raises(McpError):
        signed_gateway_route.call(APP, "get_claim", {"claim_id": CLAIM})


def test_a_call_leaves_the_main_threads_event_loop_as_it_was(
    gateway, signed_gateway_route
):
    before = asyncio.get_event_loop_policy().get_event_loop()

    signed_gateway_route.call(APP, "get_claim", {"claim_id": CLAIM})

    assert asyncio.get_event_loop_policy().get_event_loop() is before
    assert not before.is_closed()


def _route(gateway: StandInGateway) -> GatewayRoute:
    url = "http://gateway.test/mcp"
    connection = McpConnection(url, transport=httpx.ASGITransport(app=gateway.app))
    return GatewayRoute(url, connection)
