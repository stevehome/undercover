"""Helpers for the Copilot's tests: a handler's turn begun in the app, a model that
records what it is given, and a client to the app that records what it sends."""

from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, BaseMessage

from agent.tests.conftest import REPLY_USAGE, StubModel
from backend import copilot_conversations, copilot_turns
from backend.main import app

HANDLERS = {
    "dana.whitfield@undercover.example": "HND-01",
    "marcus.oyelaran@undercover.example": "HND-02",
}


class RecordingClient(TestClient):
    """The app as the Copilot sees it, with no default headers: it keeps the headers
    of every request it is sent."""

    def __init__(self) -> None:
        super().__init__(app)
        self.sent: list[dict[str, str]] = []

    def request(self, method: str, url: Any, *args: Any, **kwargs: Any):  # type: ignore[override]
        self.sent.append(dict(kwargs.get("headers") or {}))
        return super().request(method, url, *args, **kwargs)


class SeenModel(StubModel):
    """A scripted model that keeps the messages of each call it is given."""

    seen: list[list[BaseMessage]] = []

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


def seen_model(*replies: AIMessage) -> SeenModel:
    """A model that gives these replies in turn, and records what it is asked."""
    return SeenModel(messages=iter(replies), seen=[])


def tool_call(name: str, args: dict[str, Any] | None = None, call_id: str = "1"):
    """A reply that asks for one tool."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args or {}, "id": call_id}],
        response_metadata=REPLY_USAGE,
    )


def reply(text: str) -> AIMessage:
    """A final reply."""
    return AIMessage(content=text, response_metadata=REPLY_USAGE)


def forever(name: str, args: dict[str, Any] | None = None) -> SeenModel:
    """A model that asks for the same tool every time it is called."""
    return SeenModel(messages=iter(lambda: tool_call(name, args), None), seen=[])


def begin(email: str, text: str) -> SimpleNamespace:
    """Begin a handler's turn in the app, as it does; return the conversation."""
    handler_id = HANDLERS[email]
    conversation_id = copilot_conversations.make(handler_id)
    copilot_turns.begin(conversation_id, handler_id, text)
    return SimpleNamespace(conversation_id=conversation_id, handler_id=handler_id)
