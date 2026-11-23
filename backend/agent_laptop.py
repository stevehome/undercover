"""Asking the agent on a host of its own: a payload to `/invocations` with the key."""

import os
from typing import Any

import httpx

from backend.errors import ServiceUnavailable, Unconfirmed

DEFAULT_AGENT_URL = "http://127.0.0.1:8080"
TIMEOUT_SECONDS = 10


def post(payload: dict[str, Any]) -> dict[str, Any]:
    """Post a payload once and return the agent's answer.

    ServiceUnavailable when it was never sent or never connected, or the agent
    answered with an error: nothing was started. Unconfirmed when anything else goes
    wrong once it was sent: it may have been.
    """
    base_url = os.environ.get("UNDERCOVER_AGENT", DEFAULT_AGENT_URL)
    key = os.environ["UNDERCOVER_API_KEY"]
    try:
        response = httpx.post(
            f"{base_url}/invocations",
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=TIMEOUT_SECONDS,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout) as error:
        raise ServiceUnavailable("The agent isn't running") from error
    except httpx.HTTPError as error:
        raise Unconfirmed(str(error) or type(error).__name__) from error
    if response.is_error:
        raise ServiceUnavailable(f"The agent answered with an error: {response.text}")
    try:
        return response.json()
    except ValueError as error:
        raise Unconfirmed("The agent's answer was cut off") from error
