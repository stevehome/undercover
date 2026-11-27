"""The starting appeals: eight earlier claims, decided, with their appeals.

Made from the files in `data/appeals/`, which `seed_data.py` reads. The claims were
decided and paid before the pilot, so a dispatch never works them, and each has the
decision record section 14 of the claims manual asks for.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import Table

from backend import money, tables
from backend.statuses import AppealStatus, ClaimStatus


def _calculation(steps: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if steps is None:
        return None
    return [{"step": s["step"], "amount": money.dollars(s["amount"])} for s in steps]


def _claim_row(claim: dict[str, Any]) -> dict[str, Any]:
    decision = claim["decision"]
    paid = decision.get("paid_on")
    payout = money.to_cents(money.dollars(decision["payout"]))
    content = {k: v for k, v in claim.items() if k != "decision"}
    return {
        **money.cents_columns(content),
        "status": ClaimStatus.DECIDED,
        "decision": decision["decision"],
        "payout_cents": payout,
        "reason": decision["reason"],
        "policy_reference": decision["policy_reference"],
        "decided_on": decision["decided_on"],
        "decided_by": decision["decided_by"],
        "calculation": _calculation(decision.get("calculation")),
        "manual_version": decision["manual_version"],
        "over_approval_limit": int(decision.get("over_approval_limit", False)),
        "signed_off_by": decision.get("signed_off_by"),
        "signed_off_on": decision.get("signed_off_on"),
        "paid_cents": payout if paid else None,
        "paid_on": paid,
    }


def _appeal_row(appeal: dict[str, Any]) -> dict[str, Any]:
    amounts = {
        f"{name}_cents": money.to_cents(money.dollars(appeal[name]))
        for name in ("claim_amount", "compensation", "interest")
        if name in appeal
    }
    kept = {
        k: v
        for k, v in appeal.items()
        if k not in ("claim_amount", "compensation", "interest")
        and not k.startswith("redress_")
    }
    return {**kept, **amounts, "status": AppealStatus(appeal["status"])}


def _redress_row(appeal: dict[str, Any]) -> dict[str, Any]:
    total = sum(
        (
            money.dollars(appeal[n])
            for n in ("claim_amount", "compensation", "interest")
        ),
        Decimal(0),
    )
    return {
        "claim_id": appeal["claim_id"],
        "amount_cents": money.to_cents(total),
        "signed_off_by": appeal["redress_signed_off_by"],
        "paid_on": appeal["redress_paid_on"],
    }


def records(
    claims: list[dict[str, Any]],
    policies: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    appeals: list[dict[str, Any]],
) -> dict[Table, list[dict[str, Any]]]:
    """Return the rows the eight earlier claims and their appeals add."""
    return {
        tables.claims: [_claim_row(c) for c in claims],
        tables.policies: policies,
        tables.customers: customers,
        tables.appeals: [_appeal_row(a) for a in appeals],
        tables.redress_payments: [
            _redress_row(a) for a in appeals if "redress_paid_on" in a
        ],
    }
