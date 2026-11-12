from decimal import Decimal as D

import pytest

from backend import verdict

OBJECTIVES = {"accuracy": D("0.6"), "grade": D("1.0")}
NOISE = {
    "accuracy": D("0.1"),
    "grade": D("0.15"),
    "cost_per_claim": D("0.15"),
    "seconds_per_claim": D("0.15"),
}
TOLERANCE = {
    "accuracy": D("0.1"),
    "grade": D("0.15"),
    "cost_per_claim": D("1.0"),
    "seconds_per_claim": D("0.25"),
}
OLD = {
    "accuracy": D("0.80"),
    "grade": D("1.50"),
    "cost_per_claim": D("0.0010"),
    "seconds_per_claim": D("10"),
}


def decide(**new):
    return verdict.decide({**OLD, **new}, OLD, OBJECTIVES, NOISE, TOLERANCE)


def test_accuracy_up_by_more_than_the_noise_is_kept():
    # 0.80 to 0.92 is a difference of 0.12, more than the noise of 0.10.
    assert decide(accuracy=D("0.92")) == (True, "accuracy improved")


def test_accuracy_up_by_exactly_the_noise_is_not_enough():
    assert decide(accuracy=D("0.90")) == (
        False,
        "no measure improved by more than the noise",
    )


def test_cost_and_time_are_fractions_of_the_old_value():
    # Cost 0.0010 to 0.0008 is 20% less (more than 15%); time 10 to 8.6 is 14% less.
    kept, why = decide(cost_per_claim=D("0.0008"), seconds_per_claim=D("8.6"))
    assert (kept, why) == (True, "cost_per_claim improved")


def test_cost_may_double_but_not_more():
    # Tolerance 1.0 on cost: double is allowed, so a gain in accuracy is still kept.
    assert decide(accuracy=D("0.95"), cost_per_claim=D("0.0020"))[0] is True
    assert decide(accuracy=D("0.95"), cost_per_claim=D("0.0021")) == (
        False,
        "cost_per_claim got worse",
    )


def test_time_worse_by_more_than_the_tolerance_rolls_back():
    # Tolerance 0.25: 10 to 12.6 is 26% slower.
    assert decide(accuracy=D("0.95"), seconds_per_claim=D("12.6")) == (
        False,
        "seconds_per_claim got worse",
    )


def test_a_grade_that_drops_by_more_than_the_tolerance_rolls_back():
    assert decide(accuracy=D("0.95"), grade=D("1.30")) == (
        False,
        "grade got worse",
    )


def test_missing_an_objective_rolls_back_whatever_else_improved():
    assert decide(accuracy=D("0.55"), seconds_per_claim=D("1")) == (
        False,
        "it missed the objectives on accuracy",
    )
    old_below = {**OLD, "accuracy": D("0.2")}
    assert verdict.decide(
        {**old_below, "accuracy": D("0.5")}, old_below, OBJECTIVES, NOISE, TOLERANCE
    ) == (False, "it missed the objectives on accuracy")


def test_a_version_with_no_grade_is_rolled_back():
    assert decide(grade=None, accuracy=D("0.99")) == (
        False,
        "it has no grade, since no claim was graded",
    )


def test_an_old_version_with_no_grade_is_compared_on_the_rest():
    old = {**OLD, "grade": None}
    new = {**OLD, "grade": D("2.0"), "accuracy": D("0.95")}

    assert verdict.decide(new, old, OBJECTIVES, NOISE, TOLERANCE) == (
        True,
        "accuracy improved",
    )


@pytest.mark.parametrize("measure", ["accuracy", "grade"])
def test_improvements_are_listed_together(measure):
    better, worse = verdict.compare(
        {**OLD, "accuracy": D("0.95"), "grade": D("2.0")}, OLD, NOISE, TOLERANCE
    )
    assert measure in better
    assert worse == []
