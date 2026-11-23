import json
import threading
import time
from typing import Any

import boto3
import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver

from agent import (
    api,
    backend_http,
    checkpoint,
    dispatcher,
    entrypoint,
    harness,
    memory,
    readiness,
    rounds,
)
from agent.gateway import GatewayRoute
from agent.mcp_connection import McpConnection
from agent.screening import Screening
from agent.sigv4 import SigV4Auth
from agent.tests.gateway_stand_in import StandInGateway, answer
from agent.tests.stand_in_memory import StandInMemory
from backend.main import app
from conftest import API_KEY
from context import server as context_server

REPLY_USAGE = {
    "model_name": "stub/model",
    "token_usage": {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
        "cost": 0.000312,
    },
}


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


PASSED = Screening(reason="Nothing found.", instructions_found=False)


class ScreeningStub(StubModel):
    """The check's model, scripted: each answer is a Screening, None (one that can't
    be read) or an exception to raise. With no answers it passes every claim.
    """

    answers: Any = None
    asked: int = 0

    def with_structured_output(self, schema, **kwargs):
        def answer(_):
            self.asked += 1
            reply = next(self.answers) if self.answers else PASSED
            if isinstance(reply, Exception):
                raise reply
            raw = AIMessage(content="", response_metadata=REPLY_USAGE)
            return {"raw": raw, "parsed": reply, "parsing_error": None}

        return RunnableLambda(answer)


@pytest.fixture
def screener():
    """Build a check's model from answers, and keep count of how often it is asked."""

    def build(*answers):
        return ScreeningStub(
            messages=iter([]), answers=iter(answers) if answers else None
        )

    return build


@pytest.fixture(autouse=True)
def checks_nothing(monkeypatch, screener):
    """A claim passes the check unless a test gives its own model."""
    monkeypatch.setattr(harness, "screening_model", screener)


@pytest.fixture(autouse=True)
def backend(tmp_path, monkeypatch, as_handler):
    """Point the agent at the backend in-process, on a throwaway database.

    The test's own calls hold the key and a handler's sign-in, so it can play
    the agent or read what only a handler may. The agent's calls add the key.
    """
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    client = TestClient(app, headers={**as_handler(), "X-API-Key": API_KEY})
    monkeypatch.setattr(backend_http, "client", client)
    return client


STUB_MODEL = api.ModelUsed(
    model="stub/model", reasoning_effort="low", configuration_version=1
)


def create_dispatch(concurrency: int, model: api.ModelUsed = STUB_MODEL) -> int:
    """Create a dispatch as the app does, and return its run's id."""
    body = {"concurrency": concurrency, **model.model_dump()}
    return backend_http.call("POST", "/api/runs/dispatch", json=body)["run_id"]


def create_evaluation(
    concurrency: int, eval_set: str, tiny: bool, model: api.ModelUsed = STUB_MODEL
) -> int:
    """Create an evaluation as the app does, and return its run's id."""
    body = {
        "concurrency": concurrency,
        "eval_set": eval_set,
        "tiny": tiny,
        **model.model_dump(),
    }
    return backend_http.call("POST", "/api/runs/evaluation", json=body)["run_id"]


def new_run() -> int:
    """Create a dispatch with no claims to work, and finish it, so a claim has a run."""
    run_id = create_dispatch(1)
    api.finish_run(run_id)
    return run_id


@pytest.fixture
def script():
    """Build a stub model from steps: a (tool, args) pair, or a final reply."""

    def build(*steps):
        replies = [
            AIMessage(content=step, response_metadata=REPLY_USAGE)
            if isinstance(step, str)
            else AIMessage(
                content="",
                tool_calls=[{"name": step[0], "args": step[1], "id": str(i)}],
                response_metadata=REPLY_USAGE,
            )
            for i, step in enumerate(steps)
        ]
        return StubModel(messages=iter(replies))

    return build


@pytest.fixture
def saver():
    """Saved progress in memory; reuse it across two runs to stand for a restart."""
    return InMemorySaver()


@pytest.fixture
def gateway(backend):
    """A stand-in Gateway whose app tools are the backend's operations."""
    stand_in = StandInGateway()
    app = "undercover-app___"
    tools = stand_in.tools
    tools[app + "get_claim"] = lambda a: answer(
        backend.get(f"/api/claims/{a['claim_id']}")
    )
    tools[app + "calculate_payout"] = lambda a: answer(
        backend.post(f"/api/claims/{a['claim_id']}/payout", json=a)
    )
    tools[app + "decide_claim"] = lambda a: answer(
        backend.post(f"/api/claims/{a['claim_id']}/decision", json=a)
    )
    tools[app + "pay_claim"] = lambda a: answer(
        backend.post(f"/api/claims/{a['claim_id']}/payment", json=a)
    )
    for tool in context_server.TOOLS:
        tools["undercover-context___" + tool.__name__] = _context_tool(tool)
    return stand_in


def _context_tool(function):
    """A stand-in Gateway tool that is a tool of the real context layer."""

    def call(arguments):
        try:
            return json.dumps(function(**arguments)), False
        except ValueError as error:
            return str(error), True

    return call


@pytest.fixture
def signed_gateway_route(gateway):
    """A route to the stand-in Gateway, signing as the real one is signed."""
    session = boto3.Session(
        aws_access_key_id="AKIATESTKEY",
        aws_secret_access_key="secret",  # noqa: S106 - a made-up test key
        region_name="us-east-1",
    )
    url = "http://gateway.test/mcp"
    connection = McpConnection(
        url,
        auth=SigV4Auth("bedrock-agentcore", session),
        transport=httpx.ASGITransport(app=gateway.app),
    )
    return GatewayRoute(url, connection)


@pytest.fixture(scope="session")
def context_server_url():
    """The real context layer, serving on a local port for the whole test run."""
    app = context_server.build_server().streamable_http_app()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join()


@pytest.fixture(autouse=True)
def context_layer(monkeypatch, context_server_url):
    """Point the direct route's context layer at the real one."""
    monkeypatch.setenv("UNDERCOVER_CONTEXT", context_server_url)


@pytest.fixture
def memory_on(monkeypatch):
    """Turn the agent's memory on, with a stand-in for AgentCore Memory."""
    store = StandInMemory()
    monkeypatch.setenv("UNDERCOVER_MEMORY_ID", "memory-1")
    monkeypatch.setattr(memory, "open_store", lambda memory_id: store)
    return store


@pytest.fixture
def agentcore(monkeypatch):
    """The agent's AgentCore app on a TestClient, ready without a Postgres pool."""
    monkeypatch.setattr(checkpoint, "saver", lambda: None)
    readiness.forget()
    yield TestClient(entrypoint.app)
    readiness.forget()


@pytest.fixture
def dispatches(monkeypatch):
    """Replace the dispatch with a stand-in that records the runs it is given."""
    given = []
    monkeypatch.setattr(
        dispatcher, "run_dispatch", lambda run_id, n: given.append((run_id, n))
    )
    return given


@pytest.fixture
def stretches(monkeypatch):
    """Replace a round's work with a stand-in that records the stretches it is given."""
    given = []
    monkeypatch.setattr(
        rounds,
        "work_stretch",
        lambda round_id, run_id, resume: given.append((round_id, run_id, resume)),
    )
    return given
