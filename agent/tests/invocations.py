"""Calling the agent's AgentCore app as the app does: a payload to `/invocations`."""

import time
from typing import Any

from starlette.testclient import TestClient

from conftest import API_KEY


def invoke(
    client: TestClient, payload: dict[str, Any] | str, key: str | None = API_KEY
) -> Any:
    """Post a payload with the agent's key as a bearer token, unless `key` is None."""
    headers = {} if key is None else {"Authorization": f"Bearer {key}"}
    return client.post("/invocations", json=payload, headers=headers)


def ping(client: TestClient) -> str:
    """The AgentCore app's own ping: Healthy, or HealthyBusy while work is going."""
    return client.get("/ping").json()["status"]


def wait_until_idle(client: TestClient) -> None:
    """Wait for the background work to end, as Runtime's ping would say."""
    for _ in range(500):
        if ping(client) == "Healthy":
            return
        time.sleep(0.01)
    raise AssertionError("The agent's work never ended")
