"""Scoring an evaluation: pure functions on the agent's answers and the handlers'.

A claim the agent didn't decide counts as a referral with no payout.
"""

from decimal import Decimal
from typing import Any

WRONGFUL_DECLINE = Decimal(1500)
NEEDLESS_REFERRAL = Decimal(50)
PAYOUT_TOLERANCE = Decimal(1)
RATIO = Decimal("0.0001")
SECONDS = Decimal("0.001")


def _answer(row: dict[str, Any]) -> tuple[str, Decimal]:
    """Return the agent's decision and payout; no decision counts as a referral."""
    if row["decision"] is None:
        return "refer", Decimal(0)
    return row["decision"], row["payout"]


def mistake_cost(row: dict[str, Any]) -> Decimal:
    """What the agent's answer costs UnderCover against the handler's decision."""
    decision, payout = _answer(row)
    if decision == row["key_decision"]:
        return abs(payout - row["key_payout"]) if decision == "approve" else Decimal(0)
    if decision == "decline":
        return WRONGFUL_DECLINE
    if decision == "approve":
        return payout
    return NEEDLESS_REFERRAL


def is_right(row: dict[str, Any]) -> bool:
    """Say whether the decision matches and the payout is within a dollar."""
    decision, payout = _answer(row)
    return (
        decision == row["key_decision"]
        and abs(payout - row["key_payout"]) <= PAYOUT_TOLERANCE
    )


def _share(count: int, total: int) -> Decimal:
    return (Decimal(count) / total).quantize(RATIO) if total else Decimal(0)


def measures(
    rows: list[dict[str, Any]], cost: Decimal, work_ms: int, run_ms: int | None
) -> dict[str, Any]:
    """Return an evaluation's measures from its claims' answers, cost and times."""
    total = len(rows)
    return {
        "decision_accuracy": _share(
            sum(_answer(row)[0] == row["key_decision"] for row in rows), total
        ),
        "accuracy": _share(sum(is_right(row) for row in rows), total),
        "cost_of_mistakes": sum((mistake_cost(row) for row in rows), Decimal(0)),
        "straight_through": _share(
            sum(_answer(row)[0] != "refer" for row in rows), total
        ),
        "model_cost_per_claim": (cost / total if total else Decimal(0)).quantize(
            Decimal("0.000000001")
        ),
        "seconds_per_claim": (
            (Decimal(work_ms) / 1000 / total if total else Decimal(0)).quantize(SECONDS)
        ),
        "run_seconds": None
        if run_ms is None
        else (Decimal(run_ms) / 1000).quantize(SECONDS),
    }
