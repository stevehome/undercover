"""Appeals to the ombudsman: recording an appeal and its outcome, and reading them.

The one home of an appeal's state in the database. An appeal's identity is its claim's
id, since a claim has at most one. Nothing here changes the claim: its decision and
its own payment stay as they were.
"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Select, insert, select, update
from sqlalchemy.exc import IntegrityError

from backend import appeal_check, db, money, tables
from backend.errors import Conflict, Invalid, NotFound
from backend.money import Amount
from backend.statuses import AppealStatus, ClaimStatus

MAX_TEXT_LENGTH = 2000
MAX_REFERENCE_LENGTH = 100
ALREADY_APPEALED = "This claim already has an appeal"


class NewAppeal(BaseModel):
    """An appeal as a handler records it, from the ombudsman's letter."""

    ombudsman_reference: str
    received_on: str
    grounds: str


class Outcome(BaseModel):
    """The ombudsman's decision as a handler records it, with the redress's three
    amounts, which are all zero when the appeal isn't upheld."""

    outcome: Literal["upheld", "not upheld"]
    decided_on: str
    reason: str
    claim_amount: Amount
    compensation: Amount
    interest: Amount


def _text(value: str, what: str, limit: int) -> str:
    value = value.strip()
    if not value:
        raise Invalid(f"{what} is needed")
    if len(value) > limit:
        raise Invalid(f"{what} can be at most {limit} characters")
    return value


def _day(value: str, what: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise Invalid(f"{what} must be a date, such as 2026-11-27") from error
    return value


def get_row(claim_id: str) -> dict[str, Any]:
    """Return a claim's appeal as the table holds it, or raise NotFound."""
    row = find(claim_id)
    if row is None:
        raise NotFound(f"No appeal on claim {claim_id}")
    return row


def find(claim_id: str) -> dict[str, Any] | None:
    """Return a claim's appeal as the table holds it, or None."""
    with db.connection() as conn:
        row = conn.execute(
            select(tables.appeals).where(tables.appeals.c.claim_id == claim_id)
        ).one_or_none()
    return None if row is None else dict(row._mapping)


def _joined() -> Select[Any]:
    """Appeals with their claim, customer, plan and redress payment."""
    appeal, claim = tables.appeals.c, tables.claims.c
    paid = tables.redress_payments.c
    return (
        select(
            tables.appeals,
            claim.summary.label("claim_summary"),
            claim.claim_type,
            claim.decision.label("claim_decision"),
            claim.payout_cents.label("claim_payout_cents"),
            claim.customer_id,
            tables.customers.c.name.label("customer_name"),
            tables.policies.c.plan,
            paid.amount_cents.label("paid_cents"),
            paid.signed_off_by.label("paid_by"),
            paid.paid_on,
        )
        .join(tables.claims, claim.claim_id == appeal.claim_id)
        .join(tables.customers, tables.customers.c.customer_id == claim.customer_id)
        .join(tables.policies, tables.policies.c.policy_id == claim.policy_id)
        .outerjoin(tables.redress_payments, paid.claim_id == appeal.claim_id)
    )


def list_rows() -> list[dict[str, Any]]:
    """List every appeal with what the Appeals page shows, newest received first."""
    columns = tables.appeals.c
    with db.connection() as conn:
        rows = conn.execute(
            _joined().order_by(columns.received_on.desc(), columns.claim_id)
        )
        return [dict(row._mapping) for row in rows]


def get_detail(claim_id: str) -> dict[str, Any]:
    """Return one appeal with its claim, customer, plan and redress payment."""
    with db.connection() as conn:
        row = conn.execute(
            _joined().where(tables.appeals.c.claim_id == claim_id)
        ).one_or_none()
    if row is None:
        raise NotFound(f"No appeal on claim {claim_id}")
    return dict(row._mapping)


def redress_cents(row: dict[str, Any]) -> int:
    """The three parts of an upheld appeal's redress, together, in cents."""
    return sum(
        row[f"{part}_cents"] for part in ("claim_amount", "compensation", "interest")
    )


def _require_final_decision(claim_id: str) -> None:
    """Refuse an appeal on a claim that has no final decision."""
    columns = tables.claims.c
    with db.connection() as conn:
        claim = conn.execute(
            select(
                columns.status,
                columns.decision,
                columns.paid_cents,
                columns.evaluation_run_id,
            ).where(columns.claim_id == claim_id)
        ).one_or_none()
    if claim is None:
        raise NotFound(f"No claim {claim_id}")
    if claim.evaluation_run_id is not None:
        raise Conflict("An evaluation's claim can't be appealed")
    declined = claim.decision == "decline" and claim.status == ClaimStatus.DECIDED
    paid = claim.decision == "approve" and claim.paid_cents is not None
    if not (declined or paid):
        state = "referred to a handler" if claim.decision == "refer" else claim.status
        raise Conflict(f"{claim_id} has no final decision to appeal: it is {state}")


def record(claim_id: str, handler: dict[str, Any], appeal: NewAppeal) -> dict[str, Any]:
    """Record an appeal against a claim with a final decision, once the text is checked.

    The check runs before anything is written and holds no connection. An appeal
    whose text has an instruction in it is recorded all the same, and marked.
    """
    reference = _text(appeal.ombudsman_reference, "The reference", MAX_REFERENCE_LENGTH)
    received_on = _day(appeal.received_on, "The date it reached us")
    grounds = _text(appeal.grounds, "The grounds", MAX_TEXT_LENGTH)
    _require_final_decision(claim_id)
    if find(claim_id) is not None:
        raise Conflict(ALREADY_APPEALED)
    found = appeal_check.check(grounds)
    try:
        with db.connection() as conn:
            conn.execute(
                insert(tables.appeals).values(
                    claim_id=claim_id,
                    ombudsman_reference=reference,
                    received_on=received_on,
                    grounds=grounds,
                    recorded_by=handler["handler_id"],
                    recorded_on=db.now(),
                    status=AppealStatus.WITH_THE_OMBUDSMAN,
                    flagged=found.instructions_found,
                    flag_reason=found.reason if found.instructions_found else None,
                    check_cost_nanos=money.to_nanos(found.cost),
                )
            )
    except IntegrityError as error:
        raise Conflict(ALREADY_APPEALED) from error
    return get_row(claim_id)


def _check_redress(outcome: AppealStatus, amounts: tuple[Any, ...]) -> None:
    if outcome == AppealStatus.UPHELD and sum(amounts) <= 0:
        raise Invalid(
            "An upheld appeal needs redress: the three amounts must come to more "
            "than zero"
        )
    if outcome == AppealStatus.NOT_UPHELD and any(amounts):
        raise Invalid("An appeal that isn't upheld has no redress")


def record_outcome(
    claim_id: str, handler: dict[str, Any], decision: Outcome
) -> dict[str, Any]:
    """Record the ombudsman's decision on an appeal that is with the ombudsman.

    An upheld appeal takes its redress as three amounts, and one that isn't upheld
    takes none. The ombudsman's reason is checked as the grounds were.
    """
    outcome = AppealStatus(decision.outcome)
    amounts = (decision.claim_amount, decision.compensation, decision.interest)
    _check_redress(outcome, amounts)
    decided_on = _day(decision.decided_on, "The date of the decision")
    reason = _text(decision.reason, "The ombudsman's reason", MAX_TEXT_LENGTH)
    existing = get_row(claim_id)
    if existing["status"] != AppealStatus.WITH_THE_OMBUDSMAN:
        raise Conflict("This appeal has its outcome already")
    found = appeal_check.check(reason)
    upheld = outcome == AppealStatus.UPHELD
    cents = [money.to_cents(amount) if upheld else None for amount in amounts]
    columns = tables.appeals.c
    with db.connection() as conn:
        recorded = conn.execute(
            update(tables.appeals)
            .where(
                columns.claim_id == claim_id,
                columns.status == AppealStatus.WITH_THE_OMBUDSMAN,
            )
            .values(
                status=outcome,
                decided_on=decided_on,
                ombudsman_reason=reason,
                outcome_recorded_by=handler["handler_id"],
                outcome_recorded_on=db.now(),
                claim_amount_cents=cents[0],
                compensation_cents=cents[1],
                interest_cents=cents[2],
                flagged=existing["flagged"] or found.instructions_found,
                flag_reason=_flag_reason(existing["flag_reason"], found),
                check_cost_nanos=columns.check_cost_nanos + money.to_nanos(found.cost),
            )
        )
    if recorded.rowcount == 0:
        raise Conflict("This appeal has its outcome already")
    return get_row(claim_id)


def _flag_reason(kept: str | None, found: appeal_check.Check) -> str | None:
    if not found.instructions_found:
        return kept
    return found.reason if kept is None else f"{kept} {found.reason}"


def history_lines(customer_id: str) -> list[dict[str, Any]]:
    """One line for each appeal on a customer's claims: the claim, outcome and date.

    This is all the claim agent ever reads of an appeal.
    """
    appeal, claim = tables.appeals.c, tables.claims.c
    with db.connection() as conn:
        rows = conn.execute(
            select(appeal.claim_id, appeal.status, appeal.decided_on)
            .join(tables.claims, claim.claim_id == appeal.claim_id)
            .where(claim.customer_id == customer_id)
            .order_by(appeal.received_on, appeal.claim_id)
        )
        return [
            {"claim_id": r.claim_id, "outcome": r.status, "decided_on": r.decided_on}
            for r in rows
        ]


def waiting_for_outcome() -> list[dict[str, Any]]:
    """The appeals still with the ombudsman, oldest received first."""
    rows = [r for r in list_rows() if r["status"] == AppealStatus.WITH_THE_OMBUDSMAN]
    return sorted(rows, key=lambda r: (r["received_on"], r["claim_id"]))


def redress_waiting() -> list[dict[str, Any]]:
    """The upheld appeals whose redress is not paid yet, oldest decided first."""
    rows = [
        r
        for r in list_rows()
        if r["status"] == AppealStatus.UPHELD and r["paid_on"] is None
    ]
    return sorted(rows, key=lambda r: (r["decided_on"], r["claim_id"]))
