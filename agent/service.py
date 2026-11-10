"""The agent's service: the web entry point the backend calls.

It carries on a signed-off claim, and starts dispatches and evaluations.
Each is answered at once and worked in the background.
"""

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel

from agent import agents, api, checkpoint, dispatcher, harness


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


def _create(create: Callable[..., int], *arguments: object) -> int:
    """Create a run through the backend, which refuses a second one running."""
    try:
        return create(*arguments)
    except api.ApiRefusal as refusal:
        raise HTTPException(refusal.status_code, refusal.detail) from refusal


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
    model = harness.model_settings()
    run_id = _create(
        api.create_dispatch, start.concurrency, model.name, model.reasoning_effort
    )
    background.add_task(worker, run_id, start.concurrency)
    return {"run_id": run_id}


@app.post("/api/evaluations", operation_id="start_evaluation", status_code=202)
def start_evaluation(
    start: StartEvaluation,
    background: BackgroundTasks,
    worker: Annotated[Callable[[int, int], object], Depends(dispatch_worker)],
) -> dict[str, int]:
    """Start an evaluation on a labelled set; refused while a run is going."""
    model = harness.model_settings()
    run_id = _create(
        api.create_evaluation,
        start.concurrency,
        start.eval_set,
        start.tiny,
        model.name,
        model.reasoning_effort,
    )
    background.add_task(worker, run_id, start.concurrency)
    return {"run_id": run_id}
