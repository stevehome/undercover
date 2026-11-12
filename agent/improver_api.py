"""The improver's way to the backend: one function for each operation it uses.

The claim agent's client (`api.py`) has no way to these. They give the improver the
scores, the handlers' reasons on the evaluation set and the round's records, and
they let the agent's service record a round's progress.
"""

from decimal import Decimal
from typing import Any

from agent import api
from agent.backend_http import call


def create_round(handler_id: str, model: str, reasoning_effort: str) -> dict[str, Any]:
    """Start a round and its first stretch of work; return their ids."""
    body = {
        "handler_id": handler_id,
        "model": model,
        "reasoning_effort": reasoning_effort,
    }
    return call("POST", "/api/improver/rounds", json=body)


def get_round(round_id: int) -> dict[str, Any]:
    """Return a round with its proposals and cost."""
    return call("GET", f"/api/rounds/{round_id}")


def recipe_text(version: int) -> str:
    """Return the text of one recipe version."""
    recipes = call("GET", "/api/recipes")
    return next(r["text"] for r in recipes if r["version"] == version)


def models_allowed() -> list[dict[str, Any]]:
    """List the models the claim agent may use, with their reasoning efforts."""
    return call("GET", "/api/models")


def get_view(round_id: int) -> dict[str, Any]:
    """Return what the improver may read for a round."""
    return call("GET", f"/api/improver/rounds/{round_id}/view")


def get_configuration(version: int) -> dict[str, Any]:
    """Return a configuration version as the claim agent is given it."""
    return call("GET", f"/api/configuration/{version}")


def first_evaluations(round_id: int) -> list[str]:
    """List the evaluations the current version lacks, as the sets to run."""
    return call("GET", f"/api/improver/rounds/{round_id}/first-evaluations")


def record_call(round_id: int, model: str, usage: dict[str, Any]) -> None:
    """Record one of the improver's model calls, from the usage OpenRouter reports."""
    body = {
        "model": model,
        "input_tokens": usage["prompt_tokens"],
        "output_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
        "cost": format(Decimal(str(usage["cost"])), "f"),
    }
    call("POST", f"/api/improver/rounds/{round_id}/calls", json=body)


def record_stage(round_id: int, stage: str, progress: int) -> None:
    """Record where the round has got to."""
    body = {"stage": stage, "progress": progress}
    call("POST", f"/api/improver/rounds/{round_id}/stage", json=body)


def record_proposal(
    round_id: int, kind: str, content: dict[str, str], reason: str
) -> dict[str, Any]:
    """Record a proposal as waiting for a handler."""
    body = {"kind": kind, "content": content, "reason": reason}
    return call("POST", f"/api/improver/rounds/{round_id}/proposals", json=body)


def create_round_evaluation(
    round_id: int,
    parent_run_id: int,
    eval_set: str,
    used: api.ModelUsed,
    check_spending: bool,
) -> dict[str, Any]:
    """Start a whole-set evaluation for the round; refused if it costs too much."""
    body = {
        **used.model_dump(),
        "parent_run_id": parent_run_id,
        "eval_set": eval_set,
        "check_spending": check_spending,
    }
    return call("POST", f"/api/improver/rounds/{round_id}/evaluations", json=body)


def record_verdict(round_id: int) -> dict[str, Any]:
    """Have the backend keep or roll back the version under test."""
    return call("POST", f"/api/improver/rounds/{round_id}/verdict")


def record_proposal_decision(
    proposal_id: int,
    approved: bool,
    handler_id: str,
    rejection_reason: str,
    used: tuple[str, str],
) -> dict[str, Any]:
    """Record a handler's decision; refused if something else is running."""
    body = {
        "approved": approved,
        "handler_id": handler_id,
        "rejection_reason": rejection_reason,
        "model": used[0],
        "reasoning_effort": used[1],
    }
    return call("POST", f"/api/improver/proposals/{proposal_id}/decision", json=body)


def finish_run(run_id: int) -> None:
    """Finish a stretch of the improver's work, letting go of the one-run rule."""
    call("POST", f"/api/runs/{run_id}/finish")
