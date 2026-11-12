"""A version's scores: averages over the whole-set evaluations its rounds ran.

An evaluation started on the Scoreboard, and a tiny one, count for nothing here.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import select

from backend import db, evaluations, tables
from backend.statuses import RunKind, RunStatus

NEEDED_RUNS = {"evaluation": 1, "held_out": 2}


def _run_ids(version: int, eval_set: str) -> list[int]:
    runs = tables.runs.c
    with db.connection() as conn:
        found = conn.execute(
            select(runs.run_id)
            .where(
                runs.configuration_version == version,
                runs.round_id.is_not(None),
                runs.kind == RunKind.EVALUATION,
                runs.tiny.is_(False),
                runs.eval_set == eval_set,
                runs.status == RunStatus.FINISHED,
            )
            .order_by(runs.run_id)
        )
        return [run_id for (run_id,) in found]


def _average(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal(0)) / len(values) if values else None


def _measures(run_id: int) -> dict[str, Any]:
    measures = evaluations.get_evaluation(run_id)["measures"]
    return {
        "accuracy": measures["accuracy"],
        "grade": measures["grade"],
        "cost_per_claim": measures["model_cost_per_claim"],
        "seconds_per_claim": measures["seconds_per_claim"],
    }


def scores_on(version: int, eval_set: str) -> dict[str, Any]:
    """Return the averages of a version's runs on a set, and how many runs there are.

    A measure with no value in any run, such as the grade of ungraded runs, is None.
    """
    runs = [_measures(run_id) for run_id in _run_ids(version, eval_set)]
    names = ("accuracy", "grade", "cost_per_claim", "seconds_per_claim")
    return {
        "runs": len(runs),
        **{
            name: _average([r[name] for r in runs if r[name] is not None])
            for name in names
        },
    }


def scores(version: int) -> dict[str, Any]:
    """Return a version's scores on both sets."""
    return {eval_set: scores_on(version, eval_set) for eval_set in NEEDED_RUNS}


def missing_runs(version: int) -> list[str]:
    """List the evaluations a version still lacks, by set: 1 evaluation, 2 held out."""
    return [
        eval_set
        for eval_set, needed in NEEDED_RUNS.items()
        for _ in range(max(0, needed - len(_run_ids(version, eval_set))))
    ]
