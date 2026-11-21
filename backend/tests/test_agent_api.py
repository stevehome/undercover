import pytest

from backend.agent_api import AGENT_OPERATIONS

PATH = "/api/agent/openapi.json"


@pytest.fixture
def document(agent):
    return agent.get(PATH).json()


def operations(document):
    return {
        operation["operationId"]: operation
        for path in document["paths"].values()
        for operation in path.values()
    }


def test_the_document_holds_exactly_the_agents_operations(document):
    assert set(operations(document)) == AGENT_OPERATIONS


def test_the_document_has_no_servers_key_or_security(document):
    assert "servers" not in document
    assert "securitySchemes" not in document.get("components", {})
    for operation in operations(document).values():
        assert "security" not in operation
        for parameter in operation.get("parameters", []):
            assert parameter["in"] != "header"
        assert "x-api-key" not in str(operation).lower()


def test_each_operation_keeps_its_id_and_one_line_description(document):
    for name, operation in operations(document).items():
        assert operation["operationId"] == name
        assert operation["description"].strip()
        assert "\n" not in operation["description"].strip()


def test_pay_claim_takes_an_amount(document):
    schema = document["components"]["schemas"]["Payment"]
    assert list(schema["properties"]) == ["amount"]


def test_the_document_takes_the_key_or_a_handler(agent, anonymous, as_handler):
    assert agent.get(PATH).status_code == 200
    assert anonymous.get(PATH, headers=as_handler()).status_code == 200
    assert anonymous.get(PATH).status_code == 401


@pytest.mark.parametrize(
    ("schema", "field"),
    [
        ("Payment", "amount"),
        ("Decision", "payout"),
        ("Line", "amount"),
        ("PayoutRequest", "paid_by_others"),
    ],
)
def test_a_money_input_is_a_plain_number_the_gateway_can_take(document, schema, field):
    """The Gateway can't take an `anyOf`: it turns the input into an object."""
    amount = document["components"]["schemas"][schema]["properties"][field]
    assert amount == {"type": "number", "minimum": 0, "title": amount["title"]}


def test_a_payment_may_still_be_sent_as_a_number_or_a_string_of_cents(agent):
    for amount in (400.0, "400.00"):
        response = agent.post("/api/claims/CLM-1001/payment", json={"amount": amount})
        assert response.status_code != 422


def test_the_decision_is_a_string_so_a_policy_can_compare_it(document):
    """An enum becomes its own Cedar type on the Gateway, which a string can't match."""
    decision = document["components"]["schemas"]["Decision"]["properties"]["decision"]
    assert decision["type"] == "string"
    assert "enum" not in decision
    assert "approve" in decision["description"]


def test_a_decision_other_than_the_three_is_still_refused(agent):
    response = agent.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "maybe",
            "payout": 0,
            "reason": "x",
            "policy_reference": "S",
            "decided_by": "A test agent",
        },
    )
    assert response.status_code == 422
