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
