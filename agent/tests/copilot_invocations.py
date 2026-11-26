"""Calling the Copilot's AgentCore app as our app does: a payload to `/invocations`."""

from typing import Any

from starlette.testclient import TestClient


def invoke(client: TestClient, payload: dict[str, Any] | str) -> Any:
    """Post a payload, with no key: the Copilot asks for none."""
    return client.post("/invocations", json=payload)
