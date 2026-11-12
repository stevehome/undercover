"""The agent's service: the web entry point the backend calls.

It carries on a signed-off claim, and starts dispatches and evaluations.
Each is answered at once and worked in the background.
"""

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from agent import (
    agents,
    api,
    backend_http,
    checkpoint,
    dispatcher,
    harness,
    improver_api,
    rounds,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    checkpoint.saver()
    api.stop_unfinished_runs()
    yield


app = FastAPI(title="UnderCover Agent", lifespan=lifespan)


class StartDispatch(BaseModel):
    concurrency: int


class StartEvaluation(BaseModel):
    concurrency: int
    eval_set: str
    tiny: bool


class StartRound(BaseModel):
    handler_id: str


class ProposalDecision(BaseModel):
    decision: str
    handler_id: str
    reason: str


def _create[T](create: Callable[..., T], *arguments: object) -> T:
    """Create a run through the backend, which refuses a second one running."""
    try:
        return create(*arguments)
    except backend_http.ApiRefusal as refusal:
        raise HTTPException(refusal.status_code, refusal.detail) from refusal


def _current_model() -> api.ModelUsed:
    """The model, effort and version a run on the current configuration uses."""
    configuration = api.current_configuration()
    settings = harness.model_settings(configuration)
    return api.ModelUsed(
        model=settings.name,
        reasoning_effort=settings.reasoning_effort,
        configuration_version=configuration["version"],
    )


def round_worker() -> Callable[..., None]:
    """Return what works a stretch of a round; tests swap in a stand-in."""
    return rounds.work_stretch


def claim_worker() -> Callable[[str], str]:
    """Return what carries on with a claim; tests swap in a stub model."""
    return agents.decide_claim


def dispatch_worker() -> Callable[[int, int], object]:
    """Return what works a run's claims; tests swap in a stand-in."""
    return dispatcher.run_dispatch


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the agent's service is running."""
    return {"status": "ok"}


@app.post("/api/claims/{claim_id}/resume", operation_id="resume_claim", status_code=202)
def resume_claim(
    claim_id: str,
    background: BackgroundTasks,
    worker: Annotated[Callable[[str], str], Depends(claim_worker)],
) -> dict[str, str]:
    """Carry on with a signed-off claim, and pay it."""
    background.add_task(worker, claim_id)
    return {"claim_id": claim_id}


@app.post("/api/dispatches", operation_id="start_dispatch", status_code=202)
def start_dispatch(
    start: StartDispatch,
    background: BackgroundTasks,
    worker: Annotated[Callable[[int, int], object], Depends(dispatch_worker)],
) -> dict[str, int]:
    """Start a dispatch with N claim agents at once; refused while a run is going."""
    run_id = _create(api.create_dispatch, start.concurrency, _current_model())
    background.add_task(worker, run_id, start.concurrency)
    return {"run_id": run_id}


@app.post("/api/evaluations", operation_id="start_evaluation", status_code=202)
def start_evaluation(
    start: StartEvaluation,
    background: BackgroundTasks,
    worker: Annotated[Callable[[int, int], object], Depends(dispatch_worker)],
) -> dict[str, int]:
    """Start an evaluation on a labelled set; refused while a run is going."""
    run_id = _create(
        api.create_evaluation,
        start.concurrency,
        start.eval_set,
        start.tiny,
        _current_model(),
    )
    background.add_task(worker, run_id, start.concurrency)
    return {"run_id": run_id}


@app.post("/api/rounds", operation_id="start_round", status_code=202)
def start_round(
    start: StartRound,
    background: BackgroundTasks,
    worker: Annotated[Callable[..., None], Depends(round_worker)],
) -> dict[str, int]:
    """Start an improvement round; refused while a run is going."""
    created = _create(rounds.new_round, start.handler_id)
    background.add_task(worker, created["round_id"], created["run_id"], None)
    return {"round_id": created["round_id"]}


@app.post("/api/rounds/{round_id}/stop", operation_id="stop_round")
def stop_round(round_id: int) -> dict[str, int]:
    """Acknowledge a stopped round: the backend refuses what it records from now on."""
    return {"round_id": round_id}


@app.post(
    "/api/proposals/{proposal_id}/decision",
    operation_id="decide_proposal",
    status_code=202,
)
def decide_proposal(
    proposal_id: int,
    decision: ProposalDecision,
    background: BackgroundTasks,
    worker: Annotated[Callable[..., None], Depends(round_worker)],
) -> dict[str, int]:
    """Record a handler's decision, then resume the improver with it."""
    approved = decision.decision == "approve"
    settings = harness.improver_settings()
    recorded = _create(
        improver_api.record_proposal_decision,
        proposal_id,
        approved,
        decision.handler_id,
        decision.reason,
        (settings.name, settings.reasoning_effort),
    )
    background.add_task(
        worker,
        recorded["round_id"],
        recorded["run_id"],
        rounds.decision(approved, decision.reason),
    )
    return {"proposal_id": proposal_id}
