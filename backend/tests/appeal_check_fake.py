"""A stand-in for the model that checks an appeal's text, for tests."""

import json
from types import SimpleNamespace

from backend import appeal_check


class FakeChat:
    """A stand-in for OpenRouter's chat endpoint, answering the appeal check."""

    def __init__(self):
        self.calls = []
        self.found = False
        self.reason = "The text only says what happened."
        self.unreadable = False

    def send(self, **kwargs):
        self.calls.append(kwargs)
        content = "not json"
        if not self.unreadable:
            content = json.dumps(
                {"reason": self.reason, "instructions_found": self.found}
            )
        message = SimpleNamespace(content=content)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=SimpleNamespace(cost=0.00002),
        )


def install(monkeypatch):
    """Put a `FakeChat` in place of the check's client, and return it."""
    chat = FakeChat()
    monkeypatch.setattr(appeal_check, "_client", lambda: SimpleNamespace(chat=chat))
    return chat
