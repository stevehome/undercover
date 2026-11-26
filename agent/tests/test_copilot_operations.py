import importlib
import os
import threading

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from agent import (
    checkpoint,
    copilot_entrypoint,
    copilot_readiness,
    credentials,
    harness,
)
from agent.tests.copilot_helpers import SeenModel, begin, reply, seen_model, tool_call
from agent.tests.copilot_invocations import invoke
from agent.tests.invocations import ping, wait_until_idle
from agent.tests.test_copilot_sign_off import hold
from backend import copilot_turns as app_turns
from conftest import DANA

HEALTH = {"operation": "health"}
CLAIM = "CLM-1001"


class GatedModel(SeenModel):
    """A scripted model that waits to be let go before it gives its reply."""

    gate: threading.Event = threading.Event()

    def _generate(self, messages, *args, **kwargs):
        self.gate.wait(timeout=10)
        return super()._generate(messages, *args, **kwargs)


@pytest.fixture
def copilot(monkeypatch, app_client):
    """The Copilot's AgentCore app on a TestClient, ready without a Postgres pool."""
    saver = InMemorySaver()
    monkeypatch.setattr(checkpoint, "saver", lambda: saver)
    copilot_readiness.forget()
    client = TestClient(copilot_entrypoint.app)
    yield client
    copilot_readiness.forget()


def uses(monkeypatch, model):
    """Have the Copilot's turns use this scripted model, whatever the app names."""
    monkeypatch.setattr(harness, "copilot_model", lambda name, effort: model)


def turn_payload(conversation, token, **more):
    return {
        "operation": "start_turn",
        "conversation_id": conversation.conversation_id,
        "sign_in": token,
        "model": "stub/model",
        "reasoning_effort": "low",
        "message": "Who needs me?",
        **more,
    }


def test_importing_the_copilot_opens_nothing_and_fetches_nothing(monkeypatch):
    def refuse(*_):
        raise AssertionError("opened at import")

    monkeypatch.setattr(checkpoint, "saver", refuse)
    monkeypatch.setattr(credentials, "fetch", refuse)
    monkeypatch.setattr(copilot_readiness, "ensure", refuse)

    importlib.reload(copilot_entrypoint)

    assert not copilot_readiness._ready  # noqa: SLF001 - what the import must not change


def test_health_answers_without_a_key(copilot):
    response = invoke(copilot, HEALTH)

    assert (response.status_code, response.json()) == (200, {"healthy": True})


@pytest.mark.parametrize(
    ("payload", "says"),
    [
        ("start_turn", "start_turn"),
        ({}, 'an "operation"'),
        ({"operation": "dance"}, "Unknown operation 'dance'"),
    ],
)
def test_a_payload_that_is_not_right_is_a_400_that_says_what(copilot, payload, says):
    sent = {"operation": payload} if isinstance(payload, str) else payload

    response = invoke(copilot, sent)

    assert response.status_code == 400
    assert says in response.json()["error"]


def test_a_missing_or_wrong_input_is_named_and_the_sign_in_is_never_echoed(copilot):
    sign_in = "secret-sign-in-value"
    payload = {
        "operation": "start_turn",
        "conversation_id": "copilot-x",
        "sign_in": sign_in,
        "model": "stub/model",
        "reasoning_effort": "low",
        "colour": "red",
    }

    response = invoke(copilot, payload)

    assert response.status_code == 400
    assert "message: Field required" in response.json()["error"]
    assert "colour: Extra inputs are not permitted" in response.json()["error"]
    assert sign_in not in response.text


def test_a_turn_is_accepted_at_once_and_goes_on_as_a_registered_task(
    copilot, backend, as_handler, token_for, monkeypatch
):
    model = GatedModel(
        messages=iter([reply("Nobody.")]), seen=[], gate=threading.Event()
    )
    uses(monkeypatch, model)
    conversation = begin(DANA, "Who needs me?")

    response = invoke(copilot, turn_payload(conversation, token_for(DANA)))

    assert response.json() == {"accepted": True}
    assert ping(copilot) == "HealthyBusy"
    model.gate.set()
    wait_until_idle(copilot)
    path = f"/api/copilot/conversations/{conversation.conversation_id}"
    seen = backend.get(path, headers=as_handler()).json()
    assert (seen["status"], seen["messages"][-1]["text"]) == ("done", "Nobody.")


def test_getting_ready_fails_once_and_works_on_the_next_request(copilot, monkeypatch):
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("no pool yet")
        return InMemorySaver()

    monkeypatch.setattr(checkpoint, "saver", flaky)

    first = invoke(copilot, HEALTH)
    second = invoke(copilot, HEALTH)

    assert first.status_code == 500
    assert second.json() == {"healthy": True}
    assert len(attempts) == 2


def test_on_runtime_the_copilot_fetches_two_credentials_and_never_the_agents_key(
    copilot, monkeypatch
):
    for name in ("OPENROUTER_API_KEY", "UNDERCOVER_API_KEY", "DATABASE_URL"):
        monkeypatch.setenv(f"AGENTCORE_CREDENTIAL_{name}_NAME", f"provider-{name}")
        monkeypatch.setenv(name, "")
    fetched = []

    def from_identity(provider):
        fetched.append(provider)
        return f"value-of-{provider}"

    monkeypatch.setattr(credentials, "from_identity", from_identity)

    first = invoke(copilot, HEALTH)
    second = invoke(copilot, HEALTH)

    assert first.json() == second.json() == {"healthy": True}
    assert sorted(fetched) == ["provider-DATABASE_URL", "provider-OPENROUTER_API_KEY"]
    assert os.environ["UNDERCOVER_API_KEY"] == ""


def test_an_answer_to_a_confirmation_carries_the_paused_turn_on(
    copilot, backend, as_handler, token_for, monkeypatch
):
    hold(backend)
    first = seen_model(
        tool_call("sign_off_claim", {"claim_id": CLAIM}), reply("Signed off.")
    )
    uses(monkeypatch, first)
    conversation = begin(DANA, "Sign off CLM-1001")
    token = token_for(DANA)
    invoke(copilot, turn_payload(conversation, token, message="Sign off CLM-1001"))
    wait_until_idle(copilot)
    path = f"/api/copilot/conversations/{conversation.conversation_id}"
    waiting = backend.get(path, headers=as_handler()).json()
    assert waiting["status"] == "waiting for a confirmation"
    card = app_turns.answer_confirmation(
        conversation.conversation_id, conversation.handler_id
    )

    answered = invoke(
        copilot,
        {
            "operation": "answer_confirmation",
            "conversation_id": conversation.conversation_id,
            "sign_in": token,
            "model": "stub/model",
            "reasoning_effort": "low",
            "confirmed": True,
            "card": {**card, "payout": str(card["payout"])},
        },
    )
    wait_until_idle(copilot)

    assert answered.json() == {"accepted": True}
    assert backend.get(f"/api/claims/{CLAIM}").json()["paid_amount"] == "1200.00"
    assert backend.get(path, headers=as_handler()).json()["status"] == "done"
