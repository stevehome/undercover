import time
from decimal import Decimal
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from backend import auth, judge
from backend.main import app

DANA = "dana.whitfield@undercover.example"
MARCUS = "marcus.oyelaran@undercover.example"


@pytest.fixture(autouse=True)
def no_outside_services(monkeypatch):
    """Tests run on SQLite and make no network calls, whatever .env holds."""
    for name in ("DATABASE_URL", "LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNDERCOVER_AGENT", "http://127.0.0.1:9")


STUB_JUDGEMENT = judge.Judgement(
    score=Decimal("2.100"),
    letter="B",
    same_grounds=Decimal("0.9000"),
    same_section=Decimal("0.8000"),
    cost=Decimal("0.000040000"),
)


@pytest.fixture(autouse=True)
def stub_judge(monkeypatch):
    """No test asks the real judge; each grade is B unless the test says otherwise."""
    monkeypatch.setattr(judge, "judge", lambda handler, agent: STUB_JUDGEMENT)
    monkeypatch.delenv("MODEL_NAME", raising=False)


@pytest.fixture(scope="session")
def signing_key():
    """A key of the tests' own, standing for Supabase's signing key."""
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(autouse=True)
def public_keys(signing_key):
    """Check tokens against the tests' key, not the project's public keys."""
    keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=signing_key.public_key())
    )
    app.dependency_overrides[auth.key_client] = lambda: keys
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def token_for(signing_key):
    """Make an access token for a handler's email, signed by the tests' key."""

    def make(email=DANA, key=None, **claims):
        payload = {
            "aud": "authenticated",
            "email": email,
            "exp": time.time() + 3600,
            **claims,
        }
        return jwt.encode(payload, key or signing_key, algorithm="ES256")

    return make


@pytest.fixture
def as_handler(token_for):
    """Return the headers of a handler signed in, Dana Whitfield unless named."""

    def headers(email=DANA):
        return {"Authorization": f"Bearer {token_for(email)}"}

    return headers
