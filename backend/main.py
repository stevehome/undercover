"""The UnderCover backend: the HTTP routes, each a thin call into the logic modules."""

from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field, WithJsonSchema, model_validator

from backend import (
    agent_api,
    agent_process,
    agent_service,
    claims,
    dashboard_files,
    evaluations,
    improver_view,
    payouts,
    platform_settings,
    proposals,
    reference,
    round_view,
    rounds,
    runs,
    spending,
    usage,
    versions,
)
from backend.access import key_or_handler
from backend.api_key import require_api_key
from backend.auth import senior_handler, signed_in_handler
from backend.errors import (
    Conflict,
    Forbidden,
    Invalid,
    NotFound,
    ServiceUnavailable,
    Unauthorized,
)
from backend.money import Amount
from backend.payouts import Benefit, Line
from backend.runs import RunSettings
from backend.statuses import ItemStatus, ProposalKind, Stage

app = FastAPI(title="UnderCover")


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


AGENT = [Depends(require_api_key)]
SHARED = [Depends(key_or_handler)]
HANDLER = [Depends(signed_in_handler)]

SignedIn = Annotated[dict[str, Any], Depends(signed_in_handler)]
Senior = Annotated[dict[str, Any], Depends(senior_handler)]

MAX_CONCURRENCY = 25
Concurrency = Annotated[int, Field(ge=1, le=MAX_CONCURRENCY)]


DecisionKind = Annotated[
    Literal["approve", "decline", "refer"],
    WithJsonSchema(
        {"type": "string", "description": "approve, decline or refer"},
        mode="validation",
    ),
]
"""The Gateway makes an enum its own Cedar type, which a policy can't compare with a
string; the document says `string`, and the check still allows only the three."""


class Decision(BaseModel):
    decision: DecisionKind
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


EvalSet = Literal["evaluation", "held_out"]


class StartEvaluation(BaseModel):
    concurrency: Concurrency
    eval_set: EvalSet
    tiny: bool


class NewEvaluation(RunSettings):
    concurrency: Concurrency
    eval_set: EvalSet
    tiny: bool


class NewDispatch(RunSettings):
    concurrency: Concurrency


class AgentConfiguration(BaseModel):
    """What the claim agent is given of a version: no scores, no reasons."""

    version: int
    instructions: str
    model: str
    reasoning_effort: str
    round_id: int | None = None


class SettingChange(BaseModel):
    value: Decimal


class NewRound(BaseModel):
    handler_id: str
    model: str
    reasoning_effort: str


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


class RecordedDecision(BaseModel):
    approved: bool
    handler_id: str
    rejection_reason: str
    model: str
    reasoning_effort: str


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
    "/api/documents/{document}/sections",
    operation_id="list_sections",
    dependencies=AGENT,
)
def list_sections(document: str) -> list[str]:
    """List a document's section headings, in order."""
    return list(reference.sections(document))


@app.get(
    "/api/documents/{document}/section", operation_id="get_section", dependencies=AGENT
)
def get_section(document: str, heading: str) -> dict[str, str]:
    """Return the text of one section of a document."""
    return {"text": reference.section(document, heading)}


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


@app.post("/api/payouts", operation_id="calculate_payout", dependencies=AGENT)
def calculate_payout(request: PayoutRequest) -> dict[str, Any]:
    """Work out the payout on an approved claim with UnderCover's payout rules."""
    return payouts.work_out_payout(
        request.policy_id, request.benefit, request.lines, request.paid_by_others
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
    return claims.decide(claim_id, **decision.model_dump())


@app.post(
    "/api/claims/{claim_id}/steps", operation_id="record_step", dependencies=AGENT
)
def record_step(claim_id: str, step: Step) -> dict[str, Any]:
    """Record one step of the agent's work on a claim."""
    claims.record_step(claim_id, step.text)
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
def sign_off_claim(claim_id: str, handler: Senior) -> dict[str, Any]:
    """Sign off an over-limit approved claim as the signed-in handler, which pays it."""
    return claims.sign_off(claim_id, handler["handler_id"])


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
    """Have the agent's service start a dispatch with N claim agents at once."""
    return {"run_id": agent_service.start_dispatch(start.concurrency)}


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
    """Have the agent's service start an evaluation on one of the labelled sets."""
    run_id = agent_service.start_evaluation(**start.model_dump())
    return {"run_id": run_id}


@app.post("/api/runs/evaluation", operation_id="create_evaluation", dependencies=AGENT)
def create_evaluation(evaluation: NewEvaluation) -> dict[str, Any]:
    """Start an evaluation on a labelled set, working copies of its claims."""
    return evaluations.start_evaluation(
        evaluation.eval_set, evaluation.tiny, evaluation.concurrency, evaluation
    )


@app.post("/api/runs/dispatch", operation_id="create_dispatch", dependencies=AGENT)
def create_dispatch(dispatch: NewDispatch) -> dict[str, Any]:
    """Start a dispatch of the claims in progress and the waiting ones."""
    return runs.create_dispatch(dispatch.concurrency, dispatch)


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


@app.post(
    "/api/runs/stop-unfinished", operation_id="stop_unfinished_runs", dependencies=AGENT
)
def stop_unfinished_runs() -> dict[str, int]:
    """Mark every run still running as stopped, as the agent's service does on start."""
    return {"stopped": runs.stop_unfinished_runs()}


@app.get("/api/rounds", operation_id="list_rounds", dependencies=HANDLER)
def list_rounds() -> list[dict[str, Any]]:
    """List the improvement rounds, newest first, with their proposals and cost."""
    return round_view.list_rounds()


@app.get("/api/rounds/{round_id}", operation_id="get_round", dependencies=SHARED)
def get_round(round_id: int) -> dict[str, Any]:
    """Return one improvement round with its proposals and what it has cost."""
    return round_view.get_round(round_id)


@app.get(
    "/api/proposals/{proposal_id}", operation_id="get_proposal", dependencies=HANDLER
)
def get_proposal(proposal_id: int) -> dict[str, Any]:
    """Return one proposal with what it would change."""
    return proposals.get_proposal(proposal_id)


@app.post("/api/rounds", operation_id="start_round", status_code=202)
def start_round(handler: Senior) -> dict[str, int]:
    """Have the agent's service start an improvement round as the signed-in handler."""
    return {"round_id": agent_service.start_round(handler["handler_id"])}


@app.post("/api/rounds/{round_id}/stop", operation_id="stop_round")
def stop_round(round_id: int, _: Senior, background: BackgroundTasks) -> dict[str, Any]:
    """Stop an open round; the agent's service is told and starts no more work."""
    rounds.stop_round(round_id)
    background.add_task(agent_service.stop_round, round_id)
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
    agent_service.decide_proposal(
        proposal_id, decision.decision, handler["handler_id"], decision.reason
    )
    return {"proposal_id": proposal_id}


@app.post("/api/improver/rounds", operation_id="create_round", dependencies=AGENT)
def create_round(new: NewRound) -> dict[str, int]:
    """Start a round and its first stretch of work; refused while a run is going."""
    return rounds.create_round(new.handler_id, new.model, new.reasoning_effort)


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


@app.post(
    "/api/improver/proposals/{proposal_id}/decision",
    operation_id="record_proposal_decision",
    dependencies=AGENT,
)
def record_proposal_decision(
    proposal_id: int, decision: RecordedDecision
) -> dict[str, Any]:
    """Record a handler's decision on a proposal and begin the stretch that follows."""
    return proposals.record_decision(
        proposal_id,
        decision.approved,
        decision.handler_id,
        decision.rejection_reason,
        (decision.model, decision.reasoning_effort),
    )


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
