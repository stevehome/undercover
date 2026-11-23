import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend import agent_service
from backend.tests.test_decisions import decide

SIGN_OFF = "/api/claims/CLM-1001/sign-off"


def test_a_sign_off_asks_the_agent_to_resume_the_claim(client, agent_stub):
    decide(client, "1200.00")

    client.post(SIGN_OFF)

    assert agent_stub.calls == ["/api/claims/CLM-1001/resume"]


def test_a_sign_off_pays_and_answers_when_the_agent_is_down(
    client, monkeypatch, caplog
):
    monkeypatch.setenv("UNDERCOVER_AGENT", "http://127.0.0.1:9")
    decide(client, "1200.00")

    with caplog.at_level(logging.WARNING):
        signed = client.post(SIGN_OFF)

    assert signed.status_code == 200
    assert signed.json()["paid_amount"] == "1200.00"
    assert "could not be asked to resume CLM-1001" in caplog.text


def test_a_sign_off_pays_and_answers_when_the_agent_refuses(client, agent_stub, caplog):
    agent_stub.refuse = True
    decide(client, "1200.00")

    with caplog.at_level(logging.WARNING):
        signed = client.post(SIGN_OFF)

    assert signed.json()["paid_amount"] == "1200.00"
    assert "could not be asked to resume CLM-1001" in caplog.text


@pytest.fixture
def silent_agent(monkeypatch):
    """A stand-in agent that takes longer to answer than the app waits."""

    class Silent(BaseHTTPRequestHandler):
        def do_POST(self):
            time.sleep(1)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Silent)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("UNDERCOVER_AGENT", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setattr(agent_service, "TIMEOUT_SECONDS", 0.1)
    yield
    server.shutdown()


def test_a_sign_off_pays_and_answers_when_the_agent_times_out(
    client, silent_agent, caplog
):
    decide(client, "1200.00")

    with caplog.at_level(logging.WARNING):
        signed = client.post(SIGN_OFF)

    assert signed.json()["paid_amount"] == "1200.00"
    assert "could not be asked to resume CLM-1001" in caplog.text
