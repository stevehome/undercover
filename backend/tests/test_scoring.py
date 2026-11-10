from decimal import Decimal

from backend import scoring


def row(key, key_payout, decision, payout=None):
    return {
        "key_decision": key,
        "key_payout": Decimal(key_payout),
        "decision": decision,
        "payout": None if payout is None else Decimal(payout),
    }


ROWS = [
    row("approve", "100", "approve", "100.50"),  # right, off by 50 cents
    row("approve", "200", "decline", "0"),  # wrongful decline
    row("decline", "0", "approve", "300"),  # wrongful approval
    row("approve", "400", "refer", "0"),  # needless referral
    row("approve", "500", None),  # never decided: a referral
    row("approve", "600", "approve", "650"),  # right decision, wrong amount
]


def test_the_measures_match_ones_worked_out_by_hand():
    measures = scoring.measures(ROWS, Decimal("0.006"), 12000, 30000)

    assert measures["decision_accuracy"] == Decimal("0.3333")
    assert measures["accuracy"] == Decimal("0.1667")
    assert measures["cost_of_mistakes"] == Decimal("1950.50")
    assert measures["straight_through"] == Decimal("0.6667")
    assert measures["model_cost_per_claim"] == Decimal("0.001")
    assert measures["seconds_per_claim"] == Decimal("2")
    assert measures["run_seconds"] == Decimal("30")


def test_each_kind_of_mistake_has_its_cost():
    costs = [scoring.mistake_cost(r) for r in ROWS]

    assert costs == [
        Decimal("0.50"),
        Decimal(1500),
        Decimal(300),
        Decimal(50),
        Decimal(50),
        Decimal(50),
    ]


def test_a_payout_within_a_dollar_is_right():
    assert scoring.is_right(ROWS[0])
    assert not scoring.is_right(ROWS[5])
    assert not scoring.is_right(ROWS[4])


def test_a_run_still_going_has_no_run_time_and_no_claims_scores_zero():
    assert scoring.measures([], Decimal(0), 0, None)["run_seconds"] is None
    assert scoring.measures([], Decimal(0), 0, None)["accuracy"] == Decimal(0)
