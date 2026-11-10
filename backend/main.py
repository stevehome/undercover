"""The UnderCover backend: the HTTP routes, each a thin call into the logic modules."""

from typing import Annotated, Any, Literal, Self

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from backend import (
    agent_process,
    agent_service,
    claims,
    payouts,
    reference,
    runs,
    usage,
)
from backend.errors import Conflict, NotFound, ServiceUnavailable
from backend.instructions import CLAIM_INSTRUCTIONS
from backend.money import Amount
from backend.payouts import Benefit, Line
from backend.statuses import ItemStatus

app = FastAPI(title="UnderCover")


@app.exception_handler(NotFound)
def not_found(_: Request, error: NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=404)


@app.exception_handler(Conflict)
def conflict(_: Request, error: Conflict) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=409)


@app.exception_handler(ServiceUnavailable)
def service_unavailable(_: Request, error: ServiceUnavailable) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=503)


MAX_CONCURRENCY = 25
Concurrency = Annotated[int, Field(ge=1, le=MAX_CONCURRENCY)]


class Decision(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: Amount
    reason: str
    policy_reference: str

    @model_validator(mode="after")
    def only_an_approval_pays(self) -> Self:
        if self.decision != "approve" and self.payout != 0:
            raise ValueError("Only an approval has a payout")
        return self


class Step(BaseModel):
    text: str


class SignOff(BaseModel):
    handler_id: str


class Lease(BaseModel):
    owner: str


class Payment(BaseModel):
    amount: Amount


class PayoutRequest(BaseModel):
    policy_id: str
    benefit: Benefit
    lines: list[Line]
    paid_by_others: Amount


class WorkSegment(BaseModel):
    run_id: int | None
    started_on: str
    finished_on: str


class StartDispatch(BaseModel):
    concurrency: Concurrency


class NewDispatch(BaseModel):
    concurrency: Concurrency
    model: str
    reasoning_effort: str


class RunClaimUpdate(BaseModel):
    status: ItemStatus
    note: str


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims() -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    return claims.list_summaries()


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Return one claim in full, with its policy and its customer's claim history."""
    return claims.get_full(claim_id)


@app.get("/api/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: str) -> list[str]:
    """List a document's section headings, in order."""
    return list(reference.sections(document))


@app.get("/api/documents/{document}/section", operation_id="get_section")
def get_section(document: str, heading: str) -> dict[str, str]:
    """Return the text of one section of a document."""
    return {"text": reference.section(document, heading)}


@app.get("/api/claim-instructions", operation_id="get_claim_instructions")
def get_claim_instructions() -> dict[str, str]:
    """Return the instructions for deciding one claim, read only."""
    return {"instructions": CLAIM_INSTRUCTIONS}


@app.post("/api/payouts", operation_id="calculate_payout")
def calculate_payout(request: PayoutRequest) -> dict[str, Any]:
    """Work out the payout on an approved claim with UnderCover's payout rules."""
    return payouts.work_out_payout(
        request.policy_id, request.benefit, request.lines, request.paid_by_others
    )


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[dict[str, Any]]:
    """List the claims handlers who can sign off an over-limit payout."""
    return reference.approvers()


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record a decision on a claim, approve, decline or refer."""
    return claims.decide(claim_id, **decision.model_dump())


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: Step) -> dict[str, Any]:
    """Record one step of the agent's work on a claim."""
    claims.record_step(claim_id, step.text)
    return {"claim_id": claim_id, "text": step.text}


@app.get("/api/claims/{claim_id}/steps", operation_id="list_claim_steps")
def list_claim_steps(claim_id: str) -> list[dict[str, Any]]:
    """List a claim's steps, in the order they happened."""
    return claims.list_steps(claim_id)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(
    claim_id: str, sign_off: SignOff, background: BackgroundTasks
) -> dict[str, Any]:
    """Have a handler sign off an over-limit approved claim's payout."""
    signed = claims.sign_off(claim_id, sign_off.handler_id)
    background.add_task(agent_service.notify_sign_off, claim_id)
    return signed


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay a claim's approved payout, blocked until any required sign-off is given."""
    return claims.pay(claim_id, payment.amount)


@app.post("/api/claims/{claim_id}/lease", operation_id="acquire_lease")
def acquire_lease(claim_id: str, lease: Lease) -> dict[str, int]:
    """Lease a claim to an agent, or renew its lease; refused while another holds it."""
    return {"lease_seconds": claims.acquire_lease(claim_id, lease.owner)}


@app.post("/api/claims/{claim_id}/lease/release", operation_id="release_lease")
def release_lease(claim_id: str, lease: Lease) -> dict[str, str]:
    """Give up a claim's lease, if the agent still holds it."""
    claims.release_lease(claim_id, lease.owner)
    return {"claim_id": claim_id}


@app.post("/api/claims/{claim_id}/model-calls", operation_id="record_model_call")
def record_model_call(claim_id: str, call: usage.ModelCall) -> dict[str, Any]:
    """Record one model call's tokens and cost, with its run if it has one."""
    return usage.record_model_call(claim_id, call)


@app.post("/api/claims/{claim_id}/work-segments", operation_id="record_work_segment")
def record_work_segment(claim_id: str, segment: WorkSegment) -> dict[str, Any]:
    """Record one stretch of the agent working on a claim, with its run if any."""
    return usage.record_work_segment(claim_id, **segment.model_dump())


@app.post("/api/claims/{claim_id}/run", operation_id="run_agent")
def run_agent(claim_id: str) -> dict[str, Any]:
    """Start the UnderCover Agent on a waiting claim."""
    return claims.start_work(claim_id, agent_process.start)


@app.post("/api/claims/{claim_id}/requeue", operation_id="requeue_claim")
def requeue_claim(claim_id: str) -> dict[str, Any]:
    """Put a stuck claim back in the queue as waiting."""
    return claims.requeue(claim_id)


@app.post("/api/dispatches", operation_id="start_dispatch", status_code=202)
def start_dispatch(start: StartDispatch) -> dict[str, int]:
    """Have the agent's service start a dispatch with N claim agents at once."""
    return {"run_id": agent_service.start_dispatch(start.concurrency)}


@app.post("/api/runs/dispatch", operation_id="create_dispatch")
def create_dispatch(dispatch: NewDispatch) -> dict[str, Any]:
    """Start a dispatch of the claims in progress and the waiting ones."""
    return runs.create_dispatch(**dispatch.model_dump())


@app.get("/api/runs/current", operation_id="get_current_run")
def get_current_run() -> dict[str, Any] | None:
    """Return the most recently started run, with its claims and totals, or null."""
    return runs.get_current_run()


@app.get("/api/runs/{run_id}", operation_id="get_run")
def get_run(run_id: int) -> dict[str, Any]:
    """Return one run with its claims and its model cost and working time."""
    return runs.get_run(run_id)


@app.post("/api/runs/{run_id}/claims/{claim_id}", operation_id="update_run_claim")
def update_run_claim(
    run_id: int, claim_id: str, update: RunClaimUpdate
) -> dict[str, Any]:
    """Update the status and note of one claim of a run."""
    return runs.update_run_claim(run_id, claim_id, update.status, update.note)


@app.post("/api/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: int) -> dict[str, Any]:
    """Finish a run."""
    return runs.finish_run(run_id)


@app.post("/api/runs/stop-unfinished", operation_id="stop_unfinished_runs")
def stop_unfinished_runs() -> dict[str, int]:
    """Mark every run still running as stopped, as the agent's service does on start."""
    return {"stopped": runs.stop_unfinished_runs()}
