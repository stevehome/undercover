"""The three success criteria we agreed, worked out in code from our records.

Money and shares are `Decimal`, and every figure the Copilot reports comes from here,
never from the model. The first two come from a whole held-out evaluation's measures,
the second's target from our settings; the third from our app's count of payments over
the approval limit and the sign-offs behind them.
"""

from decimal import Decimal
from typing import Any

STRAIGHT_THROUGH_TARGET = Decimal("0.70")
PERCENT = Decimal(100)
ONE_PLACE = Decimal("0.1")


def _percent(share: Decimal) -> str:
    return f"{(share * PERCENT).quantize(ONE_PLACE)}%"


def _criterion(
    name: str, target: str, figure: str | None, met: bool | None, note: str
) -> dict[str, Any]:
    return {
        "criterion": name,
        "target": target,
        "figure": figure,
        "met": met,
        "note": note,
    }


def _measured(
    name: str, target: Decimal, measure: str, measures: dict[str, Any] | None, why: str
) -> dict[str, Any]:
    """A criterion that is a measure at or above a target; unknown with no figures."""
    said = f"at least {_percent(target)}"
    if measures is None:
        return _criterion(name, said, None, None, why)
    share = Decimal(str(measures[measure]))
    return _criterion(name, said, _percent(share), share >= target, "")


def over_the_limit(paid: dict[str, Any]) -> dict[str, Any]:
    """Every claim paid over the approval limit has a handler's sign-off."""
    count, signed = paid["paid_over_the_limit"], paid["with_a_sign_off"]
    target = "every payout over the approval limit approved by a person"
    if count == 0:
        note = "No claim has been paid over the approval limit yet."
    else:
        note = f"{signed} of {count} claims paid over the limit have a sign-off."
    return _criterion(
        "Over the limit", target, f"{signed} of {count}", signed == count, note
    )


def check(
    measures: dict[str, Any] | None,
    why_not: str,
    objective_accuracy: Decimal,
    paid: dict[str, Any],
) -> dict[str, Any]:
    """The three criteria, and whether all are met (unknown while a figure is)."""
    criteria = [
        _measured(
            "Straight through",
            STRAIGHT_THROUGH_TARGET,
            "straight_through",
            measures,
            why_not,
        ),
        _measured("Accuracy", objective_accuracy, "accuracy", measures, why_not),
        over_the_limit(paid),
    ]
    met = [c["met"] for c in criteria]
    all_met = False if False in met else (None if None in met else True)
    return {"criteria": criteria, "all_met": all_met}
