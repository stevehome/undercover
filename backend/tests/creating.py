"""Routes only the tests have: they make runs, rounds and reviews the way the app does.

The app creates the agent's work itself (`backend/starts.py`) and asks the agent to
work it, so it has no route for the agent to create it. The tests that need a run, a
round or a review in a given state make it here with the settings they choose, and
play the agent's part through the routes it still has.
"""

from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from backend import evaluations, proposals, rounds, runs
from backend.api_key import require_api_key
from backend.runs import RunSettings

Concurrency = Annotated[int, Field(ge=1, le=25)]


class NewDispatch(RunSettings):
    concurrency: Concurrency


class NewEvaluation(RunSettings):
    concurrency: Concurrency
    eval_set: Literal["evaluation", "held_out"]
    tiny: bool


class NewRound(BaseModel):
    handler_id: str
    model: str
    reasoning_effort: str


class RecordedDecision(BaseModel):
    approved: bool
    handler_id: str
    rejection_reason: str
    model: str
    reasoning_effort: str


def install(app: FastAPI) -> None:
    """Add the routes to the app, once."""
    if any(getattr(r, "path", "") == "/api/runs/dispatch" for r in app.routes):
        return
    agent = [Depends(require_api_key)]

    @app.post("/api/runs/dispatch", dependencies=agent)
    def create_dispatch(dispatch: NewDispatch) -> dict[str, Any]:
        return runs.create_dispatch(dispatch.concurrency, dispatch)

    @app.post("/api/runs/evaluation", dependencies=agent)
    def create_evaluation(evaluation: NewEvaluation) -> dict[str, Any]:
        return evaluations.start_evaluation(
            evaluation.eval_set, evaluation.tiny, evaluation.concurrency, evaluation
        )

    @app.post("/api/improver/rounds", dependencies=agent)
    def create_round(new: NewRound) -> dict[str, int]:
        return rounds.create_round(new.handler_id, new.model, new.reasoning_effort)

    @app.post("/api/improver/proposals/{proposal_id}/decision", dependencies=agent)
    def record_decision(proposal_id: int, decision: RecordedDecision) -> dict[str, Any]:
        return proposals.record_decision(
            proposal_id,
            decision.approved,
            decision.handler_id,
            decision.rejection_reason,
            (decision.model, decision.reasoning_effort),
        )
