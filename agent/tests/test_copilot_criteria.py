from decimal import Decimal

import pytest

from agent import copilot_criteria

OBJECTIVE = Decimal("0.80")
NONE_PAID = {"paid_over_the_limit": 0, "with_a_sign_off": 0}


def measures(straight="0.7200", accuracy="0.8400"):
    return {"straight_through": Decimal(straight), "accuracy": Decimal(accuracy)}


def check(measured=None, why="", paid=NONE_PAID, objective=OBJECTIVE):
    return copilot_criteria.check(measured, why, objective, paid)


def by_name(result):
    return {c["criterion"]: c for c in result["criteria"]}


def test_all_three_are_met():
    result = check(measures(), paid={"paid_over_the_limit": 2, "with_a_sign_off": 2})

    assert result["all_met"] is True
    found = by_name(result)
    assert found["Straight through"] == {
        "criterion": "Straight through",
        "target": "at least 70.0%",
        "figure": "72.0%",
        "met": True,
        "note": "",
    }
    assert (found["Accuracy"]["target"], found["Accuracy"]["figure"]) == (
        "at least 80.0%",
        "84.0%",
    )
    assert found["Over the limit"]["figure"] == "2 of 2"


@pytest.mark.parametrize(
    ("measured", "paid", "failing"),
    [
        (measures(straight="0.6900"), NONE_PAID, "Straight through"),
        (measures(accuracy="0.7900"), NONE_PAID, "Accuracy"),
        (
            measures(),
            {"paid_over_the_limit": 2, "with_a_sign_off": 1},
            "Over the limit",
        ),
    ],
)
def test_each_criterion_can_fail_in_turn(measured, paid, failing):
    result = check(measured, paid=paid)

    assert result["all_met"] is False
    assert [c["criterion"] for c in result["criteria"] if c["met"] is False] == [
        failing
    ]


def test_the_targets_are_met_exactly_at_the_line():
    result = check(measures(straight="0.7000", accuracy="0.8000"))

    assert by_name(result)["Straight through"]["met"] is True
    assert by_name(result)["Accuracy"]["met"] is True


def test_with_no_claim_paid_over_the_limit_the_third_is_met_and_says_why():
    third = by_name(check(measures()))["Over the limit"]

    assert third["met"] is True
    assert "No claim has been paid over the approval limit yet" in third["note"]


def test_a_payment_over_the_limit_with_no_sign_off_fails_the_third():
    third = by_name(
        check(measures(), paid={"paid_over_the_limit": 1, "with_a_sign_off": 0})
    )["Over the limit"]

    assert (third["met"], third["figure"]) == (False, "0 of 1")


def test_a_failed_evaluation_gives_no_first_two_figures_but_the_third():
    result = check(
        None,
        "The evaluation stopped: The agent stopped answering",
        paid={"paid_over_the_limit": 1, "with_a_sign_off": 1},
    )

    found = by_name(result)
    for name in ("Straight through", "Accuracy"):
        assert (found[name]["figure"], found[name]["met"]) == (None, None)
        assert "stopped" in found[name]["note"]
    assert found["Over the limit"]["met"] is True
    assert result["all_met"] is None


def test_an_unmet_criterion_is_not_met_even_when_another_is_unknown():
    result = check(
        None, "stopped", paid={"paid_over_the_limit": 1, "with_a_sign_off": 0}
    )

    assert result["all_met"] is False
