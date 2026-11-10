"""Asking the agent's service to do something: pick a claim up, or start a dispatch."""

import logging
import os

import httpx

from backend.errors import Conflict, ServiceUnavailable

DEFAULT_AGENT_URL = "http://127.0.0.1:8002"
TIMEOUT_SECONDS = 5

logger = logging.getLogger(__name__)


def _post(path: str, body: dict[str, int] | None = None) -> httpx.Response:
    base_url = os.environ.get("UNDERCOVER_AGENT", DEFAULT_AGENT_URL)
    return httpx.post(f"{base_url}{path}", json=body, timeout=TIMEOUT_SECONDS)


def notify_sign_off(claim_id: str) -> None:
    """Ask the agent to pick a signed-off claim back up."""
    try:
        _post(f"/api/claims/{claim_id}/resume")
    except httpx.HTTPError:
        logger.warning(
            "The agent could not be reached; it will pick up %s on its next run",
            claim_id,
        )


def start_dispatch(concurrency: int) -> int:
    """Ask the agent to start a dispatch with this many claim agents; return its run.

    Raises Conflict while a run is going and ServiceUnavailable if the agent is down.
    """
    try:
        response = _post("/api/dispatches", {"concurrency": concurrency})
    except httpx.HTTPError as error:
        raise ServiceUnavailable("The agent's service isn't running") from error
    if response.status_code == httpx.codes.CONFLICT:
        raise Conflict(response.json()["detail"])
    response.raise_for_status()
    return response.json()["run_id"]
