import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent import api, backend_http
from backend.main import app

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


@pytest.fixture(autouse=True)
def backend(tmp_path, monkeypatch):
    """Point the agent at the backend in-process, on a throwaway database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    client = TestClient(app)
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
