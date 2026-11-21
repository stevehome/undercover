import pytest

from backend.tests import records
from conftest import API_KEY

APPROVAL = {
    "decision": "approve",
    "payout": "420.00",
    "reason": "Covered.",
    "policy_reference": "Section 3",
}
AGENT_ROUTES = [
    ("get", "/api/configuration/current", None),
    ("post", "/api/claims/CLM-1001/decision", APPROVAL),
    ("post", "/api/claims/CLM-1001/payment", {"amount": "420.00"}),
    ("post", "/api/claims/CLM-1001/lease", {"owner": "agent"}),
]


@pytest.mark.parametrize(("method", "path", "body"), AGENT_ROUTES)
def test_an_agent_route_refuses_no_key(anonymous, method, path, body):
    response = anonymous.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), AGENT_ROUTES)
def test_an_agent_route_refuses_a_wrong_key(anonymous, method, path, body):
    headers = {"X-API-Key": "not-the-key"}
    response = anonymous.request(method, path, json=body, headers=headers)
    assert response.status_code == 401


def test_an_agent_route_works_with_the_key(agent):
    assert agent.get("/api/configuration/current").status_code == 200
    assert records.decide(agent, "CLM-1001", APPROVAL).status_code == 200
    paid = agent.post("/api/claims/CLM-1001/payment", json={"amount": "420.00"})
    assert paid.status_code == 200


def test_a_handler_cannot_use_an_agent_route(anonymous, as_handler):
    response = anonymous.get("/api/configuration/current", headers=as_handler())
    assert response.status_code == 401


def test_with_no_key_set_every_agent_route_is_refused(agent, monkeypatch):
    monkeypatch.delenv("UNDERCOVER_API_KEY")
    assert agent.get("/api/configuration/current").status_code == 401
    empty = agent.get("/api/configuration/current", headers={"X-API-Key": ""})
    assert empty.status_code == 401


def test_the_key_is_read_as_each_request_arrives(agent, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_API_KEY", "changed")
    assert agent.get("/api/configuration/current").status_code == 401
    changed = agent.get("/api/configuration/current", headers={"X-API-Key": "changed"})
    assert changed.status_code == 200
    assert API_KEY != "changed"
