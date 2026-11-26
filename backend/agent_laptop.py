"""Asking an AgentCore app on a host of its own: a payload to `/invocations`.

The claim agent is asked with the agent's key. The Copilot is asked with none: it
holds the handler's sign-in, which is in the payload, and never the agent's key.
"""

import os
from typing import Any

import httpx

from backend.errors import ServiceUnavailable, Unconfirmed

TIMEOUT_SECONDS = 10


def post(payload: dict[str, Any], url: str, with_key: bool) -> dict[str, Any]:
    """Post a payload once to the app at a URL and return its answer.

    ServiceUnavailable when it was never sent or never connected, or the agent
    answered with an error: nothing was started. Unconfirmed when anything else goes
    wrong once it was sent: it may have been.
    """
    headers = (
        {"Authorization": f"Bearer {os.environ['UNDERCOVER_API_KEY']}"}
        if with_key
        else {}
    )
    try:
        response = httpx.post(
            f"{url}/invocations",
            json=payload,
            headers=headers,
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
