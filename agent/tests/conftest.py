from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver

from agent import api, backend_http, harness
from agent.screening import Screening
from backend.main import app
from conftest import API_KEY

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


def new_run() -> int:
    """Create a dispatch with no claims to work, and finish it, so a claim has a run."""
    run_id = api.create_dispatch(1, STUB_MODEL)
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
