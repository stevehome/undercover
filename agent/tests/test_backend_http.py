import httpx
import pytest

from agent import api, backend_http, improver_api, readiness


@pytest.fixture
def requests(monkeypatch):
    """A backend that records each request it gets and answers with an empty claim."""
    seen = []

    def answer(request):
        seen.append(request)
        return httpx.Response(200, json={"lease_seconds": 60, "text": "", "run_id": 1})

    client = httpx.Client(
        base_url="http://backend", transport=httpx.MockTransport(answer)
    )
    monkeypatch.setattr(backend_http, "client", client)
    return seen


def keys(requests):
    return [request.headers.get("X-API-Key") for request in requests]


def test_a_call_carries_the_key(requests, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_API_KEY", "the-key")
    api.get_claim("CLM-1001")
    assert keys(requests) == ["the-key"]


def test_a_lease_carries_the_key(requests, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_API_KEY", "the-key")
    assert api.acquire_lease("CLM-1001", "agent") == 60
    assert keys(requests) == ["the-key"]


def test_the_improvers_calls_carry_the_key(requests, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_API_KEY", "the-key")
    improver_api.models_allowed()
    assert keys(requests) == ["the-key"]


def test_the_key_is_read_as_each_request_is_sent(requests, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_API_KEY", "first")
    api.get_claim("CLM-1001")
    monkeypatch.setenv("UNDERCOVER_API_KEY", "second")
    api.get_claim("CLM-1001")
    assert keys(requests) == ["first", "second"]


def test_a_request_with_no_key_set_is_not_sent(requests, monkeypatch):
    monkeypatch.delenv("UNDERCOVER_API_KEY")
    with pytest.raises(RuntimeError, match="UNDERCOVER_API_KEY is missing"):
        api.get_claim("CLM-1001")
    assert requests == []


def test_the_agent_is_not_ready_without_the_key(monkeypatch):
    monkeypatch.delenv("UNDERCOVER_API_KEY")
    readiness.forget()

    with pytest.raises(RuntimeError, match="UNDERCOVER_API_KEY is missing"):
        readiness.ensure()
