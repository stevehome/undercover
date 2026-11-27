"""The figures on the Appeals page, worked out from the appeals' records."""

from decimal import Decimal
from typing import Any

from backend import appeals, money
from backend.statuses import AppealStatus


def get() -> dict[str, Any]:
    """Return how many appeals are open, upheld and not upheld, and the redress.

    The upheld share is of the appeals decided, and None while none is decided.
    """
    rows = appeals.list_rows()
    count = {status: 0 for status in AppealStatus}
    for row in rows:
        count[row["status"]] += 1
    decided = count[AppealStatus.UPHELD] + count[AppealStatus.NOT_UPHELD]
    upheld = [r for r in rows if r["status"] == AppealStatus.UPHELD]
    paid = sum(appeals.redress_cents(r) for r in upheld if r["paid_on"])
    waiting = sum(appeals.redress_cents(r) for r in upheld if not r["paid_on"])
    share = None
    if decided:
        share = (Decimal(count[AppealStatus.UPHELD]) / decided).quantize(
            Decimal("0.0001")
        )
    return {
        "open": count[AppealStatus.WITH_THE_OMBUDSMAN],
        "upheld": count[AppealStatus.UPHELD],
        "not_upheld": count[AppealStatus.NOT_UPHELD],
        "upheld_share": share,
        "redress_paid": money.from_cents(paid),
        "redress_waiting": money.from_cents(waiting),
    }
