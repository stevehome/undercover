"""Asking the agent's service to do something: pick a claim up, or start a dispatch."""

import logging
import os
from typing import Any

import httpx

from backend import stopwatch
from backend.errors import Conflict, ServiceUnavailable

DEFAULT_AGENT_URL = "http://127.0.0.1:8002"
TIMEOUT_SECONDS = 5
# What the agent takes to answer a start or a decision, which waits on its own calls
# to the backend: 30 seconds each, asked up to twice. This must stay above that.
ANSWER_TIMEOUT_SECONDS = 70

logger = logging.getLogger(__name__)


def _post(
    path: str, body: dict[str, Any] | None = None, timeout: int = TIMEOUT_SECONDS
) -> httpx.Response:
    base_url = os.environ.get("UNDERCOVER_AGENT", DEFAULT_AGENT_URL)
    return httpx.post(f"{base_url}{path}", json=body, timeout=timeout)


def notify_sign_off(claim_id: str) -> None:
    """Ask the agent to pick a signed-off claim back up."""
    try:
        _post(f"/api/claims/{claim_id}/resume")
    except httpx.HTTPError:
        logger.warning(
            "The agent could not be reached; it will pick up %s on its next run",
            claim_id,
        )


def _start(path: str, body: dict[str, Any], key: str = "run_id") -> int:
    """Ask the agent to start a run, a round or a decision; return the id it names.

    Raises Conflict while a run is going and ServiceUnavailable if the agent is down.
    """
    watch = stopwatch.Stopwatch(f"The agent's answer to {path}")
    try:
        response = _post(path, body, ANSWER_TIMEOUT_SECONDS)
    except httpx.HTTPError as error:
        raise ServiceUnavailable("The agent's service isn't running") from error
    finally:
        watch.lap("the agent's answer")
        watch.log()
    if response.status_code == httpx.codes.CONFLICT:
        raise Conflict(response.json()["detail"])
    response.raise_for_status()
    return response.json()[key]


def start_dispatch(concurrency: int) -> int:
    """Ask the agent to start a dispatch with this many claim agents at once."""
    return _start("/api/dispatches", {"concurrency": concurrency})


def start_evaluation(concurrency: int, eval_set: str, tiny: bool) -> int:
    """Ask the agent to start an evaluation on a labelled set."""
    body = {"concurrency": concurrency, "eval_set": eval_set, "tiny": tiny}
    return _start("/api/evaluations", body)


def start_round(handler_id: str) -> int:
    """Ask the agent to start an improvement round; return the round's id."""
    return _start("/api/rounds", {"handler_id": handler_id}, "round_id")


def decide_proposal(
    proposal_id: int, decision: str, handler_id: str, reason: str
) -> int:
    """Ask the agent to record a handler's decision on a proposal and carry on."""
    body = {"decision": decision, "handler_id": handler_id, "reason": reason}
    return _start(f"/api/proposals/{proposal_id}/decision", body, "proposal_id")


def stop_round(round_id: int) -> None:
    """Tell the agent a round is stopped, so it starts no more claims or calls."""
    try:
        _post(f"/api/rounds/{round_id}/stop")
    except httpx.HTTPError:
        logger.warning("The agent could not be told round %s is stopped", round_id)
