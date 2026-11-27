"""An appeal as a handler reads it on the dashboard, and as a model reads it.

The customer's grounds and the ombudsman's reason come from outside the company. The
dashboard shows both to handlers whatever the check found. A model, the Copilot,
is never shown either text of an appeal the check marked: it sees that the appeal is
marked and why, and nothing else of the texts.
"""

from typing import Any

from backend import appeals, claims, money, reference
from backend.statuses import AppealStatus


def label(row: dict[str, Any]) -> str:
    """The label an appeal gives its claim, from where it and its redress stand."""
    if row["status"] == AppealStatus.WITH_THE_OMBUDSMAN:
        return "appeal open"
    if row["status"] == AppealStatus.NOT_UPHELD:
        return "appeal not upheld"
    paid = "redress paid" if row["paid_on"] else "redress waiting"
    return f"appeal upheld, {paid}"


def _dollars(cents: int | None) -> Any:
    return None if cents is None else money.from_cents(cents)


def _redress(row: dict[str, Any]) -> dict[str, Any] | None:
    if row["claim_amount_cents"] is None:
        return None
    return {
        "claim_amount": _dollars(row["claim_amount_cents"]),
        "compensation": _dollars(row["compensation_cents"]),
        "interest": _dollars(row["interest_cents"]),
        "total": _dollars(appeals.redress_cents(row)),
    }


def _payment(row: dict[str, Any], names: dict[str, str]) -> dict[str, Any] | None:
    if row["paid_on"] is None:
        return None
    return {
        "amount": _dollars(row["paid_cents"]),
        "signed_off_by": names[row["paid_by"]],
        "paid_on": row["paid_on"],
    }


def _present(
    row: dict[str, Any], names: dict[str, str], withhold_text: bool
) -> dict[str, Any]:
    hide = withhold_text and row["flagged"]
    return {
        "claim_id": row["claim_id"],
        "status": row["status"],
        "label": label(row),
        "ombudsman_reference": row["ombudsman_reference"],
        "received_on": row["received_on"],
        "recorded_by": names[row["recorded_by"]],
        "recorded_on": row["recorded_on"],
        "decided_on": row["decided_on"],
        "outcome_recorded_by": names.get(row["outcome_recorded_by"]),
        "outcome_recorded_on": row["outcome_recorded_on"],
        "grounds": None if hide else row["grounds"],
        "ombudsman_reason": None if hide else row["ombudsman_reason"],
        "text_withheld": bool(hide),
        "flagged": row["flagged"],
        "flag_reason": row["flag_reason"],
        "check_cost": money.from_nanos(row["check_cost_nanos"]),
        "redress": _redress(row),
        "redress_payment": _payment(row, names),
        "claim": {
            "summary": row["claim_summary"],
            "claim_type": row["claim_type"],
            "decision": row["claim_decision"],
            "payout": _dollars(row["claim_payout_cents"]),
            "plan": row["plan"],
            "customer": {
                "customer_id": row["customer_id"],
                "name": row["customer_name"],
            },
        },
    }


def _names() -> dict[str, str]:
    return {h["handler_id"]: h["name"] for h in reference.handlers()}


def dashboard(claim_id: str) -> dict[str, Any]:
    """One appeal with both texts, as the dashboard shows it to a handler."""
    row = appeals.get_detail(claim_id)
    return _present(row, _names(), withhold_text=False)


def of_claim(claim_id: str) -> dict[str, Any] | None:
    """A claim's appeal as the dashboard shows it, or None when it has none."""
    claims.get_row(claim_id)
    if appeals.find(claim_id) is None:
        return None
    return dashboard(claim_id)


def dashboard_list() -> list[dict[str, Any]]:
    """Every appeal with both texts, newest received first."""
    names = _names()
    return [_present(r, names, withhold_text=False) for r in appeals.list_rows()]


def for_model(claim_id: str) -> dict[str, Any]:
    """One appeal as a model reads it: a marked appeal has no text."""
    row = appeals.get_detail(claim_id)
    return _present(row, _names(), withhold_text=True)


def list_for_model() -> list[dict[str, Any]]:
    """Every appeal as a model reads it, newest received first."""
    names = _names()
    return [_present(r, names, withhold_text=True) for r in appeals.list_rows()]
