"""The appeals' routes: record an appeal and its outcome, pay redress, and the reads.

Every route takes a signed-in handler and none takes the agent's key. Paying redress
takes a handler who can sign off a payout over the approval limit. The Copilot reads
through its own two routes, which leave out a marked appeal's text.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend import appeal_figures, appeal_view, appeals, redress
from backend.auth import senior_handler, signed_in_handler

router = APIRouter()

SignedIn = Annotated[dict[str, Any], Depends(signed_in_handler)]
Senior = Annotated[dict[str, Any], Depends(senior_handler)]
HANDLER = [Depends(signed_in_handler)]


@router.post("/api/claims/{claim_id}/appeal", operation_id="record_appeal")
def record_appeal(
    claim_id: str, body: appeals.NewAppeal, handler: SignedIn
) -> dict[str, Any]:
    """Record an appeal to the ombudsman against a claim with a final decision."""
    appeals.record(claim_id, handler, body)
    return appeal_view.dashboard(claim_id)


@router.post(
    "/api/claims/{claim_id}/appeal/outcome", operation_id="record_appeal_outcome"
)
def record_appeal_outcome(
    claim_id: str, body: appeals.Outcome, handler: SignedIn
) -> dict[str, Any]:
    """Record the ombudsman's decision on a claim's appeal, with any redress."""
    appeals.record_outcome(claim_id, handler, body)
    return appeal_view.dashboard(claim_id)


@router.post("/api/claims/{claim_id}/appeal/redress", operation_id="pay_redress")
def pay_redress(claim_id: str, handler: Senior) -> dict[str, Any]:
    """Pay an upheld appeal's redress as the signed-in handler who signs it off."""
    redress.pay(claim_id, handler)
    return appeal_view.dashboard(claim_id)


@router.get(
    "/api/claims/{claim_id}/appeal",
    operation_id="get_claim_appeal",
    dependencies=HANDLER,
)
def get_claim_appeal(claim_id: str) -> dict[str, Any] | None:
    """Return a claim's appeal, or null when it has none."""
    return appeal_view.of_claim(claim_id)


@router.get("/api/appeals", operation_id="list_appeals", dependencies=HANDLER)
def list_appeals() -> list[dict[str, Any]]:
    """List every appeal, newest received first."""
    return appeal_view.dashboard_list()


@router.get(
    "/api/appeals/figures", operation_id="get_appeal_figures", dependencies=HANDLER
)
def get_appeal_figures() -> dict[str, Any]:
    """Return how many appeals are open, upheld and not upheld, and the redress."""
    return appeal_figures.get()


@router.get(
    "/api/copilot/appeals",
    operation_id="list_appeals_for_the_copilot",
    dependencies=HANDLER,
)
def list_appeals_for_the_copilot() -> list[dict[str, Any]]:
    """List every appeal for the Copilot: a marked appeal has no text."""
    return appeal_view.list_for_model()


@router.get(
    "/api/copilot/appeals/{claim_id}",
    operation_id="get_appeal_for_the_copilot",
    dependencies=HANDLER,
)
def get_appeal_for_the_copilot(claim_id: str) -> dict[str, Any]:
    """Return a claim's appeal for the Copilot: a marked appeal has no text."""
    return appeal_view.for_model(claim_id)
