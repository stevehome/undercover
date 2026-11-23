"""The calls to the backend that both of the agent's clients share.

`api.py` is the claim agent's client and `improver_api.py` the improver's. Each
holds its own operations, so the claim agent has no way to the scores; this holds
only the plumbing: the one HTTP client and what a refusal looks like.
"""

import os
from typing import Any

import httpx

from agent import endpoints
from agent.refusals import BY_APP, Refusal

DEFAULT_API_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 30
API_KEY_VARIABLE = "UNDERCOVER_API_KEY"
API_KEY_HEADER = "X-API-Key"

client: httpx.Client | None = None


def _client() -> httpx.Client:
    """Return the client to the backend, made on first use at the app's address."""
    global client  # noqa: PLW0603 - one client, made when it is first needed
    if client is None:
        client = httpx.Client(
            base_url=endpoints.api_url() or DEFAULT_API_URL, timeout=TIMEOUT_SECONDS
        )
    return client


def require_key() -> str:
    """Return the backend's API key from the environment, or say it is missing."""
    key = os.environ.get(API_KEY_VARIABLE)
    if not key:
        raise RuntimeError(f"{API_KEY_VARIABLE} is missing: set it in .env")
    return key


def send(method: str, path: str, **kwargs: Any) -> httpx.Response:
    """Send one request to the backend with the API key, read as it is sent."""
    headers = {**kwargs.pop("headers", {}), API_KEY_HEADER: require_key()}
    return _client().request(method, path, headers=headers, **kwargs)


class ApiRefusal(Refusal):
    """The backend refused a request; the message says why, for the model to read."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(BY_APP, detail)
        self.status_code = status_code


def _answer(response: httpx.Response) -> Any:
    """Return the backend's JSON; a 4xx is an ApiRefusal."""
    if response.is_client_error:
        detail = response.json().get("detail", response.text)
        raise ApiRefusal(response.status_code, str(detail))
    response.raise_for_status()
    return response.json()


def call(method: str, path: str, attempts: int = 1, **kwargs: Any) -> Any:
    """Call the backend and return its JSON; a 4xx is an ApiRefusal.

    A request that times out is sent again, up to `attempts` times in all. Only
    ask for more than one for a request the backend answers the same way twice.
    """
    for _ in range(attempts - 1):
        try:
            return _answer(send(method, path, **kwargs))
        except httpx.TimeoutException:
            continue
    return _answer(send(method, path, **kwargs))
