from contextlib import suppress

import httpx

from agent import backend_http, improver_api
from backend import agent_service


class SlowOnce:
    """A stand-in client whose first request times out, as a lost reply does."""

    def __init__(self, real):
        self.real = real
        self.requests = 0

    def request(self, method, path, **kwargs):
        self.requests += 1
        if self.requests == 1:
            raise httpx.ReadTimeout("timed out")
        return self.real.request(method, path, **kwargs)


def test_a_decision_whose_reply_timed_out_is_asked_for_again(backend, monkeypatch):
    slow = SlowOnce(backend_http.client)
    monkeypatch.setattr(backend_http, "client", slow)

    answer = backend_http.call("GET", "/api/configuration/current", attempts=2)

    assert answer["version"] == 1
    assert slow.requests == 2


def test_a_call_with_one_attempt_does_not_retry_a_timeout(backend, monkeypatch):
    slow = SlowOnce(backend_http.client)
    monkeypatch.setattr(backend_http, "client", slow)

    with suppress(httpx.ReadTimeout):
        backend_http.call("GET", "/api/configuration/current")

    assert slow.requests == 1


def test_recording_a_decision_asks_twice_at_most():
    assert improver_api.DECISION_ATTEMPTS == 2


def test_the_backend_waits_for_the_agent_longer_than_the_agent_waits_for_it():
    agent_wait = backend_http.TIMEOUT_SECONDS * improver_api.DECISION_ATTEMPTS

    assert agent_wait < agent_service.ANSWER_TIMEOUT_SECONDS
