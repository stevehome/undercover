import io
import json

import httpx
import pytest
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    ReadTimeoutError,
    ResponseStreamingError,
)

from backend import agent_laptop, agent_runtime

START = {"concurrency": 3}
ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent"


def start(client):
    return client.post("/api/dispatches", json=START)


def test_the_laptop_route_posts_the_payload_to_invocations_with_the_key(
    client, agent_stub
):
    start(client)

    assert agent_stub.calls == ["work_run"]
    assert agent_stub.bodies == [{"run_id": 1}]
    assert agent_stub.keys == ["Bearer test-agent-key"]


def test_the_laptop_route_passes_on_a_refusal_as_a_409(client, agent_stub):
    agent_stub.refuse = True

    response = start(client)

    assert (response.status_code, response.json()["detail"]) == (
        409,
        "A run is already going",
    )


def test_an_error_answer_means_nothing_was_started(client, monkeypatch):
    def broken(*_, **__):
        return httpx.Response(500, json={"error": "boom"})

    monkeypatch.setattr(httpx, "post", broken)

    response = start(client)

    assert response.status_code == 503
    assert "boom" in response.json()["detail"]


@pytest.mark.parametrize(
    "failure",
    [httpx.ReadTimeout("slow"), httpx.RemoteProtocolError("cut off")],
)
def test_a_timeout_or_a_cut_off_answer_tells_the_handler_to_reload(
    client, monkeypatch, failure
):
    def fails(*_, **__):
        raise failure

    monkeypatch.setattr(httpx, "post", fails)

    response = start(client)

    assert response.status_code == 504
    assert "Reload the page" in response.json()["detail"]


def test_an_answer_that_is_not_json_is_unconfirmed(client, monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *_, **__: httpx.Response(200, text="{"))

    assert start(client).status_code == 504


def test_a_request_is_sent_once_with_no_retry(client, monkeypatch):
    sent = []

    def fails(*_, **__):
        sent.append(1)
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "post", fails)
    start(client)

    assert sent == [1]


class FakeRuntime:
    """A stand-in for boto3's Runtime client: it records each call."""

    def __init__(self, answer=None, error=None):
        self.answer = answer if answer is not None else {"accepted": True, "run_id": 7}
        self.error = error
        self.calls = []

    def invoke_agent_runtime(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"response": io.BytesIO(json.dumps(self.answer).encode())}


@pytest.fixture
def runtime(monkeypatch):
    """Point the app at a runtime, with a stand-in for boto3's client."""
    monkeypatch.setenv("UNDERCOVER_AGENT_RUNTIME", ARN)

    def use(fake):
        monkeypatch.setattr(agent_runtime, "_client", lambda: fake)
        return fake

    return use


def test_the_runtime_route_sends_the_payload_in_a_new_session_each_time(
    client, runtime
):
    fake = runtime(FakeRuntime())

    first = start(client)
    client.post(f"/api/runs/{first.json()['run_id']}/finish")
    second = start(client)

    assert (first.json(), second.json()) == ({"run_id": 1}, {"run_id": 2})
    assert [json.loads(call["payload"]) for call in fake.calls] == [
        {"operation": "work_run", "run_id": 1},
        {"operation": "work_run", "run_id": 2},
    ]
    assert {call["agentRuntimeArn"] for call in fake.calls} == {ARN}
    sessions = [call["runtimeSessionId"] for call in fake.calls]
    assert len(set(sessions)) == 2
    assert all(len(session) >= 33 for session in sessions)


def test_the_runtime_route_sends_no_key(client, runtime):
    fake = runtime(FakeRuntime())

    start(client)

    assert "Authorization" not in json.dumps(fake.calls, default=str)


def test_the_runtime_route_passes_on_a_refusal_as_a_409(client, runtime):
    runtime(FakeRuntime({"refused": "A run is already going"}))

    assert start(client).status_code == 409


@pytest.mark.parametrize(
    "error",
    [
        ConnectTimeoutError(endpoint_url="https://runtime"),
        ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "Invoke"),
    ],
)
def test_a_runtime_that_never_connected_or_answered_an_error_started_nothing(
    client, runtime, error
):
    runtime(FakeRuntime(error=error))

    assert start(client).status_code == 503


@pytest.mark.parametrize(
    "error",
    [
        ReadTimeoutError(endpoint_url="https://runtime"),
        ResponseStreamingError(error="cut off"),
    ],
)
def test_a_runtime_that_timed_out_or_was_cut_off_is_unconfirmed(client, runtime, error):
    runtime(FakeRuntime(error=error))

    assert start(client).status_code == 504


def test_a_runtime_answer_cut_off_while_reading_is_unconfirmed(client, runtime):
    class Cut(FakeRuntime):
        def invoke_agent_runtime(self, **kwargs):
            raise_in_read = io.BytesIO(b'{"accepted"')
            return {"response": raise_in_read}

    runtime(Cut())

    assert start(client).status_code == 504


def test_the_runtime_client_makes_one_attempt_with_the_briefs_timeouts(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATEST")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")

    config = agent_runtime._client().meta.config  # noqa: SLF001

    assert config.retries["total_max_attempts"] == 1
    assert (config.connect_timeout, config.read_timeout) == (5, 20)


def test_the_laptop_route_waits_ten_seconds():
    assert agent_laptop.TIMEOUT_SECONDS == 10
