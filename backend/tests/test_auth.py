import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from backend.main import app

MARCUS = "marcus.oyelaran@undercover.example"
OVER_THE_LIMIT = {
    "decision": "approve",
    "payout": "1200.00",
    "reason": "Large emergency medical claim.",
    "policy_reference": "Section 7",
}


@pytest.fixture
def anonymous(tmp_path, monkeypatch):
    """A client with no sign-in, on a fresh database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    return TestClient(app)


def get_me(anonymous, authorization):
    return anonymous.get("/api/me", headers={"Authorization": authorization})


def test_a_valid_token_is_accepted(anonymous, token_for):
    me = get_me(anonymous, f"Bearer {token_for()}")
    assert me.status_code == 200
    assert me.json()["name"] == "Dana Whitfield"
    assert me.json()["can_approve_over_limit"] is True


def test_me_says_when_a_handler_cannot_sign_off(anonymous, token_for):
    me = get_me(anonymous, f"Bearer {token_for(MARCUS)}").json()
    assert me["name"] == "Marcus Oyelaran"
    assert me["can_approve_over_limit"] is False


def test_the_email_may_be_in_any_case(anonymous, token_for):
    assert get_me(anonymous, f"Bearer {token_for('DANA.Whitfield@undercover.example')}")


def test_no_token_is_refused(anonymous):
    response = anonymous.get("/api/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Sign in to do this"


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(lambda t: "Bearer not-a-token", id="malformed"),
        pytest.param(lambda t: "Basic abc", id="not a bearer token"),
        pytest.param(
            lambda t: f"Bearer {t(key=ec.generate_private_key(ec.SECP256R1()))}",
            id="badly signed",
        ),
        pytest.param(lambda t: f"Bearer {t(aud='anon')}", id="wrong audience"),
        pytest.param(lambda t: f"Bearer {t(exp=1)}", id="expired"),
        pytest.param(
            lambda t: f"Bearer {t('stranger@undercover.example')}", id="unknown email"
        ),
        pytest.param(lambda t: f"Bearer {t(email='')}", id="no email"),
    ],
)
def test_a_bad_token_is_refused(anonymous, token_for, make):
    assert get_me(anonymous, make(token_for)).status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/claims/CLM-1001/sign-off", None),
        ("post", "/api/dispatches", {"concurrency": 3}),
        (
            "post",
            "/api/evaluations",
            {"concurrency": 3, "eval_set": "evaluation", "tiny": True},
        ),
        ("post", "/api/claims/CLM-1001/run", None),
    ],
)
def test_every_handler_action_needs_a_sign_in(anonymous, method, path, body):
    assert getattr(anonymous, method)(path, json=body).status_code == 401


def test_the_agents_routes_and_the_reads_stay_open(anonymous):
    assert anonymous.get("/api/claims").status_code == 200
    assert anonymous.get("/api/runs/current").status_code == 200
    decided = anonymous.post("/api/claims/CLM-1001/decision", json=OVER_THE_LIMIT)
    assert decided.status_code == 200


def test_a_sign_off_over_the_limit_by_marcus_is_refused_with_a_reason(
    anonymous, as_handler
):
    anonymous.post("/api/claims/CLM-1001/decision", json=OVER_THE_LIMIT)
    refused = anonymous.post(
        "/api/claims/CLM-1001/sign-off", headers=as_handler(MARCUS)
    )
    assert refused.status_code == 403
    assert "Marcus Oyelaran" in refused.json()["detail"]
    assert anonymous.get("/api/claims/CLM-1001").json()["signed_off_by"] is None


def test_a_sign_off_by_dana_records_dana(anonymous, as_handler):
    anonymous.post("/api/claims/CLM-1001/decision", json=OVER_THE_LIMIT)
    signed = anonymous.post("/api/claims/CLM-1001/sign-off", headers=as_handler())
    assert signed.status_code == 200
    assert signed.json()["signed_off_by"] == "HND-01"
