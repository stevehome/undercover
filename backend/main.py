"""The UnderCover backend: the HTTP routes, each a thin call into the logic modules."""

from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field

from backend import (
    agent_api,
    agent_process,
    agent_service,
    appeal_routes,
    claims,
    copilot_routes,
    dashboard_files,
    evaluations,
    improver_view,
    lookup_routes,
    platform_settings,
    proposals,
    reference,
    round_view,
    rounds,
    runs,
    sent_back,
    spending,
    starts,
    usage,
    versions,
)
from backend.access import key_or_handler
from backend.api_key import require_api_key
from backend.auth import senior_handler, signed_in_handler
from backend.decision_record import Decision
from backend.errors import (
    Conflict,
    Forbidden,
    Invalid,
    NotFound,
    ServiceUnavailable,
    Unauthorized,
    Unconfirmed,
)
from backend.money import Amount
from backend.payouts import Benefit, Line
from backend.runs import RunSettings
from backend.statuses import ItemStatus, ProposalKind, Stage, StepKind

app = FastAPI(title="UnderCover")
app.include_router(appeal_routes.router)
app.include_router(copilot_routes.router)
app.include_router(lookup_routes.router)


@app.exception_handler(NotFound)
def not_found(_: Request, error: NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=404)


@app.exception_handler(Conflict)
def conflict(_: Request, error: Conflict) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=409)


@app.exception_handler(Unauthorized)
def unauthorized(_: Request, error: Unauthorized) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=401)


@app.exception_handler(Forbidden)
def forbidden(_: Request, error: Forbidden) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=403)


@app.exception_handler(Invalid)
def invalid(_: Request, error: Invalid) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=422)


@app.exception_handler(ServiceUnavailable)
def service_unavailable(_: Request, error: ServiceUnavailable) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=503)


@app.exception_handler(Unconfirmed)
def unconfirmed(_: Request, error: Unconfirmed) -> JSONResponse:
    detail = (
        "The agent didn't answer in time. Reload the page to see if it went through"
    )
    return JSONResponse({"detail": detail}, status_code=504)


AGENT = [Depends(require_api_key)]
SHARED = [Depends(key_or_handler)]
HANDLER = [Depends(signed_in_handler)]

SignedIn = Annotated[dict[str, Any], Depends(signed_in_handler)]
Senior = Annotated[dict[str, Any], Depends(senior_handler)]

MAX_CONCURRENCY = 25
Concurrency = Annotated[int, Field(ge=1, le=MAX_CONCURRENCY)]


class Step(BaseModel):
    kind: StepKind
    text: str
    details: dict[str, Any]


class Lease(BaseModel):
    owner: str


class Payment(BaseModel):
    amount: Amount


class RunStop(BaseModel):
    reason: str


class SendBack(BaseModel):
    note: str


class Hold(BaseModel):
    reason: Literal["gateway"]


class PayoutRequest(BaseModel):
    benefit: Benefit
    lines: list[Line]
    paid_by_others: Amount


class WorkSegment(BaseModel):
    run_id: int | None
    started_on: str
    finished_on: str


class StartDispatch(BaseModel):
    concurrency: Concurrency


EvalSet = Literal["evaluation", "held_out"]


class StartEvaluation(BaseModel):
    concurrency: Concurrency
    eval_set: EvalSet
    tiny: bool


class AgentConfiguration(BaseModel):
    """What the claim agent is given of a version: no scores, no reasons."""

    version: int
    instructions: str
    model: str
    reasoning_effort: str
    round_id: int | None = None


class SettingChange(BaseModel):
    value: Decimal


class RoundStage(BaseModel):
    stage: Stage
    progress: int


class NewProposal(BaseModel):
    kind: ProposalKind
    content: dict[str, str]
    reason: str


class RoundEvaluation(RunSettings):
    parent_run_id: int
    eval_set: EvalSet
    check_spending: bool


class ProposalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str


class RunClaimUpdate(BaseModel):
    status: ItemStatus
    note: str


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get(
    "/api/agent/openapi.json",
    operation_id="get_agent_openapi",
    dependencies=SHARED,
)
def get_agent_openapi() -> dict[str, Any]:
    """Return the OpenAPI document of the operations the claim agent is given."""
    return agent_api.agent_openapi(app.routes)


@app.get("/api/me", operation_id="get_me")
def get_me(handler: SignedIn) -> dict[str, Any]:
    """Return the signed-in handler, and whether they can sign off over the limit."""
    return handler


@app.get("/api/settings", operation_id="list_settings", dependencies=HANDLER)
def list_settings() -> list[dict[str, Any]]:
    """List the platform's settings, with who last changed each and when."""
    return platform_settings.list_settings()


@app.post("/api/settings/{key}", operation_id="change_setting")
def change_setting(key: str, change: SettingChange, handler: Senior) -> dict[str, Any]:
    """Change one setting as the signed-in handler; the change is recorded."""
    return platform_settings.change(key, change.value, handler)


@app.get("/api/models", operation_id="list_models", dependencies=SHARED)
def list_models() -> list[dict[str, Any]]:
    """List the models the claim agent may use, with efforts and prices."""
    return platform_settings.models()


@app.get("/api/claims", operation_id="list_claims", dependencies=SHARED)
def list_claims() -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    return claims.list_summaries()


@app.get("/api/claims/{claim_id}", operation_id="get_claim", dependencies=SHARED)
def get_claim(claim_id: str) -> dict[str, Any]:
    """Return one claim in full, with its policy and its customer's claim history."""
    return claims.get_full(claim_id)


@app.get(
    "/api/configuration/current",
    operation_id="get_current_configuration",
    dependencies=AGENT,
    response_model=AgentConfiguration,
)
def get_current_configuration() -> dict[str, Any]:
    """Return the current configuration version, for a claim worked with no run."""
    return versions.configuration_for_agent(versions.current_configuration()["version"])


@app.get(
    "/api/runs/{run_id}/configuration",
    operation_id="get_run_configuration",
    dependencies=AGENT,
    response_model=AgentConfiguration,
)
def get_run_configuration(run_id: int) -> dict[str, Any]:
    """Return the configuration version a run works to, with the run's model."""
    run = runs.get_run(run_id)
    return {
        **versions.configuration_for_agent(run["configuration_version"]),
        "model": run["model"],
        "reasoning_effort": run["reasoning_effort"],
        "round_id": run["round_id"],
    }


@app.get(
    "/api/configuration/{version}",
    operation_id="get_configuration_version",
    dependencies=AGENT,
    response_model=AgentConfiguration,
)
def get_configuration_version(version: int) -> dict[str, Any]:
    """Return one configuration version, as the claim agent is given it."""
    return versions.configuration_for_agent(version)


@app.get(
    "/api/configurations", operation_id="list_configurations", dependencies=HANDLER
)
def list_configurations() -> list[dict[str, Any]]:
    """List every configuration version, oldest first, with its held-out scores."""
    return round_view.list_configurations()


@app.get(
    "/api/configurations/{version}/diff",
    operation_id="get_configuration_diff",
    dependencies=HANDLER,
)
def get_configuration_diff(version: int) -> dict[str, Any]:
    """Return what a configuration version changed from the one before."""
    return versions.configuration_diff(version)


@app.get("/api/recipes", operation_id="list_recipes", dependencies=SHARED)
def list_recipes() -> list[dict[str, Any]]:
    """List every recipe version of the improver, oldest first."""
    return versions.list_recipes()


@app.get(
    "/api/recipes/{version}/diff", operation_id="get_recipe_diff", dependencies=HANDLER
)
def get_recipe_diff(version: int) -> dict[str, Any]:
    """Return what a recipe version changed from the one before."""
    return versions.recipe_diff(version)


@app.post(
    "/api/claims/{claim_id}/payout", operation_id="calculate_payout", dependencies=AGENT
)
def calculate_payout(claim_id: str, request: PayoutRequest) -> dict[str, Any]:
    """Work out the claim's payout with UnderCover's payout rules, and keep it."""
    return claims.calculate_payout(
        claim_id, request.benefit, request.lines, request.paid_by_others
    )


@app.get("/api/handlers", operation_id="list_handlers", dependencies=HANDLER)
def list_handlers() -> list[dict[str, Any]]:
    """List the claims handlers who can sign off an over-limit payout."""
    return reference.approvers()


@app.post(
    "/api/claims/{claim_id}/decision", operation_id="decide_claim", dependencies=AGENT
)
def decide_claim(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record a decision on a claim, approve, decline or refer."""
    return claims.decide(claim_id, decision)


@app.post(
    "/api/claims/{claim_id}/steps", operation_id="record_step", dependencies=AGENT
)
def record_step(claim_id: str, step: Step) -> dict[str, Any]:
    """Record one step of the agent's work on a claim."""
    claims.record_step(claim_id, step.kind, step.text, step.details)
    return {"claim_id": claim_id, "text": step.text}


@app.get(
    "/api/claims/{claim_id}/steps",
    operation_id="list_claim_steps",
    dependencies=HANDLER,
)
def list_claim_steps(claim_id: str) -> list[dict[str, Any]]:
    """List a claim's steps, in the order they happened."""
    return claims.list_steps(claim_id)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(
    claim_id: str, handler: Senior, background: BackgroundTasks
) -> dict[str, Any]:
    """Sign off an over-limit approved claim as the signed-in handler, which pays it.

    The agent is asked to resume the claim once the payment is saved.
    """
    signed = claims.sign_off(claim_id, handler["handler_id"])
    background.add_task(agent_service.resume_claim, claim_id)
    return signed


@app.post("/api/claims/{claim_id}/send-back", operation_id="send_back_claim")
def send_back_claim(
    claim_id: str, body: SendBack, handler: Senior, background: BackgroundTasks
) -> dict[str, Any]:
    """Send an approval waiting for sign-off back to the agent with a note.

    The agent is asked to resume the claim once the send back is saved.
    """
    sent = sent_back.send_back_claim(claim_id, handler, body.note)
    background.add_task(agent_service.resume_claim, claim_id)
    return sent


@app.post("/api/claims/{claim_id}/take", operation_id="take_claim", dependencies=AGENT)
def take_claim(claim_id: str) -> dict[str, Any]:
    """Take a sent-back claim for the agent; whoever asks second gets a 409."""
    return sent_back.take_claim(claim_id)


@app.post(
    "/api/claims/{claim_id}/resume-heard",
    operation_id="hear_resume",
    dependencies=AGENT,
)
def hear_resume(claim_id: str) -> dict[str, str]:
    """Note that the agent is working a resumed claim."""
    claims.hear_resume(claim_id)
    return {"claim_id": claim_id}


@app.post(
    "/api/claims/{claim_id}/hold", operation_id="hold_for_sign_off", dependencies=AGENT
)
def hold_for_sign_off(claim_id: str, hold: Hold) -> dict[str, Any]:
    """Hold an approved claim whose payment the Gateway refused for a sign-off."""
    return claims.hold_for_sign_off(claim_id, hold.reason)


@app.post(
    "/api/claims/{claim_id}/payment", operation_id="pay_claim", dependencies=AGENT
)
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay a claim's approved payout, up to the approval limit; a sign-off pays more."""
    return claims.pay(claim_id, payment.amount)


@app.post(
    "/api/claims/{claim_id}/lease", operation_id="acquire_lease", dependencies=AGENT
)
def acquire_lease(claim_id: str, lease: Lease) -> dict[str, int]:
    """Lease a claim to an agent, or renew its lease; refused while another holds it."""
    return {"lease_seconds": claims.acquire_lease(claim_id, lease.owner)}


@app.post(
    "/api/claims/{claim_id}/lease/release",
    operation_id="release_lease",
    dependencies=AGENT,
)
def release_lease(claim_id: str, lease: Lease) -> dict[str, str]:
    """Give up a claim's lease, if the agent still holds it."""
    claims.release_lease(claim_id, lease.owner)
    return {"claim_id": claim_id}


@app.post(
    "/api/claims/{claim_id}/model-calls",
    operation_id="record_model_call",
    dependencies=AGENT,
)
def record_model_call(claim_id: str, call: usage.ModelCall) -> dict[str, Any]:
    """Record one model call's tokens and cost, with its run if it has one."""
    return usage.record_model_call(claim_id, call)


@app.post(
    "/api/claims/{claim_id}/work-segments",
    operation_id="record_work_segment",
    dependencies=AGENT,
)
def record_work_segment(claim_id: str, segment: WorkSegment) -> dict[str, Any]:
    """Record one stretch of the agent working on a claim, with its run if any."""
    return usage.record_work_segment(claim_id, **segment.model_dump())


@app.post("/api/claims/{claim_id}/run", operation_id="run_agent")
def run_agent(claim_id: str, _: SignedIn) -> dict[str, Any]:
    """Start the UnderCover Agent on a waiting claim."""
    return claims.start_work(claim_id, agent_process.start)


@app.post(
    "/api/claims/{claim_id}/requeue", operation_id="requeue_claim", dependencies=AGENT
)
def requeue_claim(claim_id: str) -> dict[str, Any]:
    """Put a stuck claim back in the queue as waiting."""
    return claims.requeue(claim_id)


@app.post("/api/dispatches", operation_id="start_dispatch", status_code=202)
def start_dispatch(start: StartDispatch, _: SignedIn) -> dict[str, int]:
    """Start a dispatch with N claim agents at once, and have the agent work it."""
    return {"run_id": starts.start_dispatch(start.concurrency)}


@app.get("/api/evaluations", operation_id="list_evaluations", dependencies=HANDLER)
def list_evaluations() -> list[dict[str, Any]]:
    """List the evaluations, newest first, with their measures."""
    return evaluations.list_evaluations()


@app.get(
    "/api/evaluations/{run_id}", operation_id="get_evaluation", dependencies=HANDLER
)
def get_evaluation(run_id: int) -> dict[str, Any]:
    """Return one evaluation with each claim's answer beside the handler's."""
    return evaluations.get_evaluation(run_id)


@app.post("/api/evaluations", operation_id="start_evaluation", status_code=202)
def start_evaluation(start: StartEvaluation, _: SignedIn) -> dict[str, int]:
    """Start an evaluation on one of the labelled sets, and have the agent work it."""
    return {"run_id": starts.start_evaluation(**start.model_dump())}


@app.get("/api/runs/current", operation_id="get_current_run", dependencies=HANDLER)
def get_current_run() -> dict[str, Any] | None:
    """Return the most recently started run, with its claims and totals, or null."""
    return runs.get_current_run()


@app.get("/api/runs/{run_id}", operation_id="get_run", dependencies=SHARED)
def get_run(run_id: int) -> dict[str, Any]:
    """Return one run with its claims and its model cost and working time."""
    return runs.get_run(run_id)


@app.post(
    "/api/runs/{run_id}/claims/{claim_id}",
    operation_id="update_run_claim",
    dependencies=AGENT,
)
def update_run_claim(
    run_id: int, claim_id: str, update: RunClaimUpdate
) -> dict[str, Any]:
    """Update the status and note of one claim of a run."""
    return runs.update_run_claim(run_id, claim_id, update.status, update.note)


@app.post("/api/runs/{run_id}/finish", operation_id="finish_run", dependencies=AGENT)
def finish_run(run_id: int) -> dict[str, Any]:
    """Finish a run."""
    return runs.finish_run(run_id)


@app.post("/api/runs/{run_id}/stop", operation_id="stop_run", dependencies=AGENT)
def stop_run(run_id: int, stop: RunStop) -> dict[str, int]:
    """Stop one run, and a round's evaluation with it, giving the reason."""
    runs.stop_run(run_id, stop.reason)
    return {"run_id": run_id}


@app.post("/api/runs/{run_id}/heard", operation_id="hear_run", dependencies=AGENT)
def hear_run(run_id: int) -> dict[str, int]:
    """Note that the agent is working a run or a round's stretch."""
    runs.hear_from_run(run_id)
    return {"run_id": run_id}


@app.get("/api/rounds", operation_id="list_rounds", dependencies=HANDLER)
def list_rounds() -> list[dict[str, Any]]:
    """List the improvement rounds, newest first, with their proposals and cost."""
    return round_view.list_rounds()


@app.get("/api/rounds/{round_id}", operation_id="get_round", dependencies=SHARED)
def get_round(round_id: int) -> dict[str, Any]:
    """Return one improvement round with its proposals and what it has cost."""
    return round_view.get_round(round_id)


@app.get(
    "/api/proposals/{proposal_id}", operation_id="get_proposal", dependencies=SHARED
)
def get_proposal(proposal_id: int) -> dict[str, Any]:
    """Return one proposal with what it would change."""
    return proposals.get_proposal(proposal_id)


@app.post("/api/rounds", operation_id="start_round", status_code=202)
def start_round(handler: Senior) -> dict[str, int]:
    """Start an improvement round as the signed-in handler; the agent works it."""
    return {"round_id": starts.start_round(handler["handler_id"])}


@app.post("/api/rounds/{round_id}/stop", operation_id="stop_round")
def stop_round(round_id: int, _: Senior) -> dict[str, Any]:
    """Stop an open round; the app refuses what the agent records for it from now on."""
    rounds.stop_round(round_id)
    return round_view.get_round(round_id)


@app.post(
    "/api/proposals/{proposal_id}/decision",
    operation_id="decide_proposal",
    status_code=202,
)
def decide_proposal(
    proposal_id: int, decision: ProposalDecision, handler: Senior
) -> dict[str, int]:
    """Approve or reject a proposal as the signed-in handler, through the agent."""
    proposals.get_proposal(proposal_id)
    if decision.decision == "reject" and not decision.reason.strip():
        raise Invalid("Say why you are rejecting it, so the improver can try again")
    starts.decide_proposal(
        proposal_id, decision.decision, handler["handler_id"], decision.reason
    )
    return {"proposal_id": proposal_id}


@app.get(
    "/api/improver/rounds/{round_id}/stretch",
    operation_id="get_round_stretch",
    dependencies=AGENT,
)
def get_round_stretch(round_id: int) -> dict[str, int]:
    """Return the run that holds an open round's stretch of work; 409 if none does."""
    return rounds.working_stretch(round_id)


@app.get(
    "/api/improver/rounds/{round_id}/view",
    operation_id="get_improver_view",
    dependencies=AGENT,
)
def get_improver_view(round_id: int) -> dict[str, Any]:
    """Return what the improver may read: the held-out set's scores only."""
    return improver_view.get_view(round_id)


@app.get(
    "/api/improver/rounds/{round_id}/first-evaluations",
    operation_id="get_first_evaluations",
    dependencies=AGENT,
)
def get_first_evaluations(round_id: int) -> list[str]:
    """List the evaluations the current version still lacks, as the sets to run."""
    return rounds.missing_first_evaluations(round_id)


@app.post(
    "/api/improver/rounds/{round_id}/calls",
    operation_id="record_improver_call",
    dependencies=AGENT,
)
def record_improver_call(round_id: int, call: rounds.ImproverCall) -> dict[str, Any]:
    """Record one of the improver's model calls with its round."""
    return rounds.record_call(round_id, call)


@app.post(
    "/api/improver/rounds/{round_id}/stage",
    operation_id="record_round_stage",
    dependencies=AGENT,
)
def record_round_stage(round_id: int, update: RoundStage) -> dict[str, Any]:
    """Record where an open round has got to."""
    return rounds.record_stage(round_id, update.stage, update.progress)


@app.post(
    "/api/improver/rounds/{round_id}/proposals",
    operation_id="record_proposal",
    dependencies=AGENT,
)
def record_proposal(round_id: int, proposal: NewProposal) -> dict[str, Any]:
    """Record a proposal as waiting for a handler; one outside the models is refused."""
    return proposals.record_proposal(
        round_id, proposal.kind, proposal.content, proposal.reason
    )


@app.post(
    "/api/improver/rounds/{round_id}/evaluations",
    operation_id="create_round_evaluation",
    dependencies=AGENT,
)
def create_round_evaluation(round_id: int, new: RoundEvaluation) -> dict[str, Any]:
    """Start a whole-set evaluation for a round, inside its stretch of work."""
    return rounds.start_evaluation(
        round_id, new.parent_run_id, new.eval_set, new, new.check_spending
    )


@app.post(
    "/api/improver/rounds/{round_id}/verdict",
    operation_id="record_verdict",
    dependencies=AGENT,
)
def record_verdict(round_id: int) -> dict[str, Any]:
    """Keep or roll back the round's version by the round's own settings."""
    return rounds.record_verdict(round_id)


@app.get(
    "/api/runs/{run_id}/may-start-claim",
    operation_id="may_start_claim",
    dependencies=AGENT,
)
def may_start_claim(run_id: int) -> dict[str, bool]:
    """Say whether a run may start a claim: its round is open and within its limit."""
    return {"may_start": spending.may_start_claim(run_id)}


dashboard_files.serve(app, dashboard_files.BUILD)

handler = Mangum(app, lifespan="off")
