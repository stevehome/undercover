"""The agent's only way to the UnderCover backend.

One client, and one function for each operation the agents use.
"""

import os
from decimal import Decimal
from http import HTTPStatus
from typing import Annotated, Any, Literal

import httpx
from pydantic import BaseModel, Field

BACKEND_URL = os.environ.get("UNDERCOVER_BACKEND", "http://localhost:8000")

Document = Literal["policy_wording", "claims_manual"]
Decision = Literal["approve", "decline", "refer"]
Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Benefit = Literal[
    "trip_cancellation",
    "trip_interruption",
    "trip_delay",
    "baggage_delay",
    "baggage",
    "passport",
    "emergency_medical",
]
WAITING = "waiting"
WAITING_FOR_SIGN_OFF = "waiting for sign-off"
RunClaimStatus = Literal[
    "to do", "in progress", "done", "left for a handler", "still in progress"
]


class Line(BaseModel):
    """One covered item or expense on a claim."""

    description: str = Field(description="What the item or expense is")
    amount: Amount = Field(
        description="The total claimed for the line in US dollars, before any limits. "
        "For several items, the total for all of them"
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="How many separate items the line holds, such as 3 for three "
        "shirts. A pair or a set is one item",
    )
    kind: Literal[
        "item", "electronics", "cash", "expense", "hotel", "meals_without_receipts"
    ] = Field(
        description="item: a belonging, or a pair or set that counts as one item. "
        "electronics: only a phone, tablet, laptop, camera or its lens, e-reader or "
        "smartwatch; any other device is an item. "
        "cash: cash that was lost or stolen. "
        "expense: any other cost with a receipt, such as a medical bill, a meal, a "
        "taxi, a fee or a prepaid trip cost. "
        "hotel: a hotel during a trip delay. "
        "meals_without_receipts: meals during a trip delay with no receipts."
    )
    nights: int = Field(default=0, description="For a hotel, the number of nights")
    hours: int = Field(
        default=0,
        description="For meals without receipts, the length of the delay in hours",
    )


client = httpx.Client(base_url=BACKEND_URL, timeout=10)


class ApiRefusal(Exception):  # noqa: N818 - a refusal, not a failure
    """The backend refused a request; the message says why, for the model to read."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _call(method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    if response.is_client_error:
        detail = response.json().get("detail", response.text)
        raise ApiRefusal(response.status_code, str(detail))
    response.raise_for_status()
    return response.json()


def claim_instructions() -> str:
    """Return the instructions for deciding one claim."""
    return _call("GET", "/api/claim-instructions")["instructions"]


def list_claims() -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    return _call("GET", "/api/claims")


def get_claim(claim_id: str) -> dict[str, Any]:
    """Return one claim in full, with its policy and the customer's claim history."""
    return _call("GET", f"/api/claims/{claim_id}")


def list_sections(document: Document) -> list[str]:
    """List a document's section headings."""
    return _call("GET", f"/api/documents/{document}/sections")


def get_section(document: Document, heading: str) -> str:
    """Return the text of one section of a document."""
    params = {"heading": heading}
    return _call("GET", f"/api/documents/{document}/section", params=params)["text"]


def record_step(claim_id: str, text: str) -> None:
    """Record one step of the agent's work on a claim."""
    _call("POST", f"/api/claims/{claim_id}/steps", json={"text": text})


def decide_claim(
    claim_id: str,
    decision: Decision,
    payout: Amount,
    reason: str,
    policy_reference: str,
) -> dict[str, Any]:
    """Record the decision on a claim, and return the claim."""
    body = {
        "decision": decision,
        "payout": str(payout),
        "reason": reason,
        "policy_reference": policy_reference,
    }
    return _call("POST", f"/api/claims/{claim_id}/decision", json=body)


def pay_claim(claim_id: str, amount: Amount) -> dict[str, Any]:
    """Pay a claim its approved payout, and return the claim."""
    body = {"amount": str(amount)}
    return _call("POST", f"/api/claims/{claim_id}/payment", json=body)


def record_model_call(
    claim_id: str, run_id: int | None, model: str, usage: dict[str, Any]
) -> None:
    """Record one model call, from the `token_usage` OpenRouter reports with it."""
    body = {
        "run_id": run_id,
        "model": model,
        "input_tokens": usage["prompt_tokens"],
        "output_tokens": usage["completion_tokens"],
        "total_tokens": usage["total_tokens"],
        "cost": format(Decimal(str(usage["cost"])), "f"),
    }
    _call("POST", f"/api/claims/{claim_id}/model-calls", json=body)


def record_work_segment(
    claim_id: str, run_id: int | None, started_on: str, finished_on: str
) -> None:
    """Record one stretch of the agent working on a claim."""
    body = {"run_id": run_id, "started_on": started_on, "finished_on": finished_on}
    _call("POST", f"/api/claims/{claim_id}/work-segments", json=body)


def acquire_lease(claim_id: str, owner: str) -> int | None:
    """Lease a claim, or renew the lease: its length in seconds, or None if held."""
    response = client.post(f"/api/claims/{claim_id}/lease", json={"owner": owner})
    if response.status_code == HTTPStatus.CONFLICT:
        return None
    response.raise_for_status()
    return response.json()["lease_seconds"]


def release_lease(claim_id: str, owner: str) -> None:
    """Give up a claim's lease."""
    _call("POST", f"/api/claims/{claim_id}/lease/release", json={"owner": owner})


def calculate_payout(
    policy_id: str, benefit: Benefit, lines: list[Line], paid_by_others: Amount
) -> dict[str, Any]:
    """Work out a payout with UnderCover's payout rules."""
    body = {
        "policy_id": policy_id,
        "benefit": benefit,
        "lines": [line.model_dump(mode="json") for line in lines],
        "paid_by_others": str(paid_by_others),
    }
    return _call("POST", "/api/payouts", json=body)


def requeue_claim(claim_id: str) -> None:
    """Put a stuck claim back in the queue as waiting."""
    _call("POST", f"/api/claims/{claim_id}/requeue")


def create_dispatch(concurrency: int, model: str, reasoning_effort: str) -> int:
    """Start a dispatch of the claims to work; return the run's id."""
    body = {
        "concurrency": concurrency,
        "model": model,
        "reasoning_effort": reasoning_effort,
    }
    return _call("POST", "/api/runs/dispatch", json=body)["run_id"]


def get_run(run_id: int) -> dict[str, Any]:
    """Return a run with its claims and totals."""
    return _call("GET", f"/api/runs/{run_id}")


def update_run_claim(
    run_id: int, claim_id: str, status: RunClaimStatus, note: str
) -> None:
    """Set the status and note of one claim of a run."""
    body = {"status": status, "note": note}
    _call("POST", f"/api/runs/{run_id}/claims/{claim_id}", json=body)


def finish_run(run_id: int) -> None:
    """Finish a run."""
    _call("POST", f"/api/runs/{run_id}/finish")


def stop_unfinished_runs() -> None:
    """Mark every run still running as stopped."""
    _call("POST", "/api/runs/stop-unfinished")
