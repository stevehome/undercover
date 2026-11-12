"""The calls to the backend that both of the agent's clients share.

`api.py` is the claim agent's client and `improver_api.py` the improver's. Each
holds its own operations, so the claim agent has no way to the scores; this holds
only the plumbing: the one HTTP client and what a refusal looks like.
"""

import os
from typing import Any

import httpx

BACKEND_URL = os.environ.get("UNDERCOVER_BACKEND", "http://localhost:8000")
TIMEOUT_SECONDS = 30

client = httpx.Client(base_url=BACKEND_URL, timeout=TIMEOUT_SECONDS)


class ApiRefusal(Exception):  # noqa: N818 - a refusal, not a failure
    """The backend refused a request; the message says why, for the model to read."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def call(method: str, path: str, **kwargs: Any) -> Any:
    """Call the backend and return its JSON; a 4xx is an ApiRefusal."""
    response = client.request(method, path, **kwargs)
    if response.is_client_error:
        detail = response.json().get("detail", response.text)
        raise ApiRefusal(response.status_code, str(detail))
    response.raise_for_status()
    return response.json()
