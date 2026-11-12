"""A round's spending: what it has spent, what is left, and what an evaluation may cost.

A round's spending covers the improver's own model calls, all of the round's
evaluations (the first ones included) and the judge. Claims already started when
the limit is reached finish, so a round can overshoot by what those cost.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from backend import db, evaluations, money, platform_settings, tables
from backend.statuses import RunKind, RunStatus, Stage


def _sum(column: Any, *conditions: Any) -> int:
    with db.connection() as conn:
        total = conn.execute(select(func.sum(column)).where(*conditions)).scalar()
    return int(total or 0)


def spent(round_id: int) -> Decimal:
    """Return what a round has spent, in dollars to the billionth."""
    round_runs = select(tables.runs.c.run_id).where(tables.runs.c.round_id == round_id)
    nanos = (
        _sum(
            tables.improver_calls.c.cost_nanos,
            tables.improver_calls.c.round_id == round_id,
        )
        + _sum(
            tables.model_calls.c.cost_nanos, tables.model_calls.c.run_id.in_(round_runs)
        )
        + _sum(
            tables.claim_grades.c.cost_nanos,
            tables.claim_grades.c.run_id.in_(round_runs),
        )
    )
    return money.from_nanos(nanos)


def limit(round_settings: dict[str, Any]) -> Decimal:
    """Return the spending limit a round started with, in dollars."""
    return Decimal(str(round_settings["round_spending_limit"]))


def left(round_id: int, round_settings: dict[str, Any]) -> Decimal:
    """Return what is left of a round's limit; never below zero."""
    return max(Decimal(0), limit(round_settings) - spent(round_id))


def _cost_per_claim(model: str) -> Decimal | None:
    """The highest cost per claim, model and judge, an evaluation on a model had."""
    runs = tables.runs.c
    with db.connection() as conn:
        ids = [
            run_id
            for (run_id,) in conn.execute(
                select(runs.run_id).where(
                    runs.kind == RunKind.EVALUATION,
                    runs.model == model,
                    runs.status == RunStatus.FINISHED,
                )
            )
        ]
    per_claim = []
    for run_id in ids:
        evaluation = evaluations.get_evaluation(run_id)
        measures, claims = evaluation["measures"], len(evaluation["claims"])
        if claims:
            per_claim.append(
                measures["model_cost_per_claim"] + measures["judge_cost"] / claims
            )
    return max(per_claim) if per_claim else None


def _price_ratio(new_model: str, current_model: str) -> Decimal:
    """The larger of the ratios of two models' input and output prices."""
    prices = {m["model"]: m for m in platform_settings.models()}
    new, current = prices.get(new_model), prices.get(current_model)
    if new is None or current is None:
        return Decimal(1)
    ratios = [
        Decimal(str(new[key])) / Decimal(str(current[key]))
        for key in ("input_price_per_million", "output_price_per_million")
        if current[key]
    ]
    return max(ratios, default=Decimal(1))


def estimate(eval_set: str, model: str, current_model: str) -> Decimal | None:
    """Estimate what an evaluation on a set will cost on a model, or None if unknown.

    Its claims times the highest cost per claim seen for the model. For a model with
    no runs yet, the current model's cost scaled by the larger price ratio.
    """
    per_claim = _cost_per_claim(model)
    if per_claim is None:
        known = _cost_per_claim(current_model)
        if known is None:
            return None
        per_claim = known * _price_ratio(model, current_model)
    return per_claim * evaluations.set_size(eval_set)


def may_start_claim(run_id: int) -> bool:
    """Say whether a run may start a claim: its round is open and within its limit."""
    runs, rounds = tables.runs.c, tables.rounds.c
    with db.connection() as conn:
        found = conn.execute(
            select(rounds.round_id, rounds.stage, rounds.settings)
            .join(tables.runs, runs.round_id == rounds.round_id)
            .where(runs.run_id == run_id)
        ).one_or_none()
    if found is None:
        return True
    return found.stage != Stage.STOPPED and left(found.round_id, found.settings) > 0
