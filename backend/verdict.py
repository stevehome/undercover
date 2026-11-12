"""The rule that keeps or rolls back a new version: pure `Decimal` functions.

A version is kept when it meets the objectives, at least one measure improves by
more than its noise, and none gets worse by more than its tolerance. Accuracy and
the grade are compared as differences; cost and time as fractions of the old value.
"""

from decimal import Decimal
from typing import Any

DIFFERENCES = ("accuracy", "grade")
FRACTIONS = ("cost_per_claim", "seconds_per_claim")


def compare(
    new: dict[str, Any],
    old: dict[str, Any],
    noise: dict[str, Decimal],
    tolerance: dict[str, Decimal],
) -> tuple[list[str], list[str]]:
    """Return the measures that improved by more than the noise, and those that
    got worse by more than the tolerance."""
    better: list[str] = []
    worse: list[str] = []
    for name in DIFFERENCES:
        if new[name] is None or old[name] is None:
            continue
        if new[name] > old[name] + noise[name]:
            better.append(name)
        if new[name] < old[name] - tolerance[name]:
            worse.append(name)
    for name in FRACTIONS:
        if new[name] < old[name] * (1 - noise[name]):
            better.append(name)
        if new[name] > old[name] * (1 + tolerance[name]):
            worse.append(name)
    return better, worse


def decide(
    new: dict[str, Any],
    old: dict[str, Any],
    objectives: dict[str, Decimal],
    noise: dict[str, Decimal],
    tolerance: dict[str, Decimal],
) -> tuple[bool, str]:
    """Decide whether to keep a new version, from its held-out averages and the
    current version's, and say why."""
    if new["grade"] is None:
        return False, "it has no grade, since no claim was graded"
    missed = [name for name, floor in objectives.items() if new[name] < floor]
    if missed:
        return False, f"it missed the objectives on {', '.join(missed)}"
    better, worse = compare(new, old, noise, tolerance)
    if worse:
        return False, f"{', '.join(worse)} got worse"
    if not better:
        return False, "no measure improved by more than the noise"
    return True, f"{', '.join(better)} improved"
