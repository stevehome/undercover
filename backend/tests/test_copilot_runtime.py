import io
import json
import logging
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from backend import agent_runtime, copilot_service
from backend.tests.test_copilot import ask, make, read

ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:123456789012:"
    "runtime/undercover_default_copilot-abc"
)
NOT_READY = ClientError(
    {
        "Error": {
            "Code": "RuntimeClientError",
            "Message": "Received error (502) from runtime.",
        }
    },
    "InvokeAgentRuntime",
)
BAD_GATEWAY_LOOKALIKE = ClientError(
    {"Error": {"Code": "RuntimeClientError", "Message": "Received error (500)"}},
    "InvokeAgentRuntime",
)
DENIED = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "Invoke")


class Runtime:
    """A stand-in for boto3's Runtime client: it fails as told, then accepts."""

    def __init__(self, errors, waits):
        self.errors = list(errors)
        self.waits = waits
        self.calls = []

    def invoke_agent_runtime(self, **kwargs):
        self.calls.append(kwargs)
        if self.errors:
            raise self.errors.pop(0)
        return {"response": io.BytesIO(json.dumps({"accepted": True}).encode())}


@pytest.fixture
def runtime(monkeypatch):
    """Point the Copilot's route at a runtime that fails as given; waits are skipped."""
    monkeypatch.setenv("UNDERCOVER_COPILOT_RUNTIME", ARN)
    waits = []
    monkeypatch.setattr(copilot_service.time, "sleep", waits.append)

    def use(*errors):
        fake = Runtime(errors, waits)
        monkeypatch.setattr(agent_runtime, "_client", lambda: fake)
        return fake

    return use


def test_a_container_still_starting_gets_the_message_again_in_the_same_session(
    client, runtime
):
    fake = runtime(NOT_READY, NOT_READY)
    conversation_id = make(client)

    assert ask(client, conversation_id).status_code == 202

    assert len(fake.calls) == 3
    assert {call["runtimeSessionId"] for call in fake.calls} == {conversation_id}
    assert fake.waits == [copilot_service.WAIT_SECONDS] * 2
    assert [m["role"] for m in read(client, conversation_id)["messages"]] == ["handler"]


def test_a_container_that_never_starts_ends_in_a_503_and_the_message_is_taken_back(
    client, runtime
):
    fake = runtime(*[NOT_READY] * copilot_service.TRIES)
    conversation_id = make(client)

    refused = ask(client, conversation_id)

    assert refused.status_code == 503
    assert len(fake.calls) == copilot_service.TRIES
    assert read(client, conversation_id)["messages"] == []
    assert ask(client, conversation_id).status_code == 202


@pytest.mark.parametrize("error", [DENIED, BAD_GATEWAY_LOOKALIKE])
def test_any_other_refusal_is_not_sent_again(client, runtime, error):
    fake = runtime(error)

    assert ask(client, make(client)).status_code == 503
    assert len(fake.calls) == 1


def test_a_refusal_is_logged_with_the_runtime_operation_and_session_but_no_sign_in(
    client, runtime, caplog
):
    runtime(NOT_READY)
    conversation_id = make(client)
    token = client.headers["Authorization"].removeprefix("Bearer ")

    with caplog.at_level(logging.WARNING, logger="backend.agent_runtime"):
        ask(client, conversation_id)

    [line] = [r.getMessage() for r in caplog.records]
    assert "undercover_default_copilot-abc" in line
    assert "start_turn" in line
    assert conversation_id in line
    assert token not in line
    assert "123456789012" not in line


def test_the_copilots_runtime_stays_up_for_fifteen_minutes_between_messages():
    path = Path(__file__).parents[2] / "agentcore" / "agentcore.json"
    runtimes = json.loads(path.read_text())["runtimes"]
    idle = {r["name"]: r["lifecycleConfiguration"] for r in runtimes}

    assert idle["copilot"]["idleRuntimeSessionTimeout"] == 900
