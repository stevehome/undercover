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


def spent_by(round_ids: list[int]) -> dict[int, Decimal]:
    """Return what each round has spent, in dollars to the billionth."""
    calls, model, grades, runs = (
        tables.improver_calls.c,
        tables.model_calls.c,
        tables.claim_grades.c,
        tables.runs.c,
    )
    queries = (
        select(calls.round_id, func.sum(calls.cost_nanos))
        .where(calls.round_id.in_(round_ids))
        .group_by(calls.round_id),
        select(runs.round_id, func.sum(model.cost_nanos))
        .join_from(tables.runs, tables.model_calls, runs.run_id == model.run_id)
        .where(runs.round_id.in_(round_ids))
        .group_by(runs.round_id),
        select(runs.round_id, func.sum(grades.cost_nanos))
        .join_from(tables.runs, tables.claim_grades, runs.run_id == grades.run_id)
        .where(runs.round_id.in_(round_ids))
        .group_by(runs.round_id),
    )
    nanos = dict.fromkeys(round_ids, 0)
    with db.connection() as conn:
        for query in queries:
            for round_id, total in conn.execute(query):
                nanos[round_id] += int(total)
    return {round_id: money.from_nanos(total) for round_id, total in nanos.items()}


def spent(round_id: int) -> Decimal:
    """Return what a round has spent, in dollars to the billionth."""
    return spent_by([round_id])[round_id]


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
    for evaluation in evaluations.get_evaluations(ids):
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
