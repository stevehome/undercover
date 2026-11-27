"""Helpers for the Copilot's tests: a handler's turn begun in the app, a model that
records what it is given, and a client to the app that records what it sends."""

from types import SimpleNamespace
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent import copilot_turns as agent_turns
from agent.tests.conftest import REPLY_USAGE, StubModel
from backend import copilot_conversations, copilot_turns
from conftest import DANA

HANDLERS = {
    "dana.whitfield@undercover.example": "HND-01",
    "marcus.oyelaran@undercover.example": "HND-02",
}


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


def tool_calls(*calls: tuple[str, dict[str, Any]]) -> AIMessage:
    """A reply that asks for several tools at once."""
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": str(i)}
            for i, (name, args) in enumerate(calls)
        ],
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


def turn_for(conversation, email, model, saver, token_for):
    """A Copilot turn for the conversation, on this model and saved state."""
    return agent_turns.Turn(
        conversation.conversation_id, token_for(email), model, saver, None
    )


def pause(token_for, ask, email=DANA, calls=(), saver=None):
    """Work a turn whose first reply asks for these tools; return what it left."""
    saver = saver or InMemorySaver()
    conversation = begin(email, ask)
    model = seen_model(tool_calls(*calls), reply("All done."))
    agent_turns.work_turn(turn_for(conversation, email, model, saver, token_for), ask)
    return conversation, saver, model


def answer(conversation, saver, token_for, confirmed):
    """Answer the waiting card with a Copilot built fresh on the same saved state."""
    shown = copilot_turns.answer_confirmation(
        conversation.conversation_id, conversation.handler_id
    )
    model = seen_model(reply("Back again."))
    turn = turn_for(conversation, DANA, model, saver, token_for)
    agent_turns.answer_confirmation(turn, confirmed, shown)
    return model


def read(backend, conversation, as_handler, email=DANA):
    """The conversation as the sidebar reads it."""
    path = f"/api/copilot/conversations/{conversation.conversation_id}"
    return backend.get(path, headers=as_handler(email)).json()


def tool_result(model, name):
    """The result of the named tool as the model saw it on its last call."""
    return next(
        m for m in model.seen[-1] if isinstance(m, ToolMessage) and m.name == name
    )
