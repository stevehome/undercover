import pytest
from fastapi.routing import APIRoute

from backend.main import app

SHARED_READS = ["/api/claims", "/api/claims/CLM-1001", "/api/models", "/api/recipes"]
HANDLER_ACTIONS = [
    ("post", "/api/claims/CLM-1001/sign-off", None),
    ("post", "/api/dispatches", {"concurrency": 3}),
    ("post", "/api/rounds", None),
    ("post", "/api/proposals/1/decision", {"decision": "approve", "reason": ""}),
    ("post", "/api/settings/approval_limit", {"value": "500"}),
    ("get", "/api/handlers", None),
    ("get", "/api/settings", None),
]


@pytest.mark.parametrize("path", SHARED_READS)
def test_a_shared_read_takes_the_key_or_a_handler(agent, anonymous, as_handler, path):
    assert agent.get(path).status_code == 200
    assert anonymous.get(path, headers=as_handler()).status_code == 200
    assert anonymous.get(path).status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), HANDLER_ACTIONS)
def test_a_handler_route_is_refused_with_only_the_key(agent, method, path, body):
    assert agent.request(method, path, json=body).status_code == 401


def test_a_handler_route_works_with_a_handler(anonymous, as_handler):
    assert anonymous.get("/api/handlers", headers=as_handler()).status_code == 200


def test_a_bad_sign_in_is_not_made_good_by_a_bad_key(anonymous, as_handler):
    headers = {**as_handler(), "Authorization": "Bearer nonsense"}
    headers["X-API-Key"] = "wrong"
    assert anonymous.get("/api/claims", headers=headers).status_code == 401


def test_with_no_key_set_a_handler_can_still_read_the_claims(
    anonymous, as_handler, monkeypatch
):
    monkeypatch.delenv("UNDERCOVER_API_KEY")
    assert anonymous.get("/api/claims", headers=as_handler()).status_code == 200


def test_health_is_open_and_every_other_route_needs_credentials(anonymous):
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert len(routes) > 40
    for route in routes:
        path = route.path.replace("{key}", "approval_limit")
        path = "/".join(
            "1" if part.startswith("{") else part for part in path.split("/")
        )
        for method in route.methods or []:
            response = anonymous.request(method, path)
            expected = 200 if route.operation_id == "health" else 401
            assert response.status_code == expected, f"{method} {route.path}"
