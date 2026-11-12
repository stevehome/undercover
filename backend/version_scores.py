"""A version's scores: averages over the whole-set evaluations its rounds ran.

An evaluation started on the Scoreboard, and a tiny one, count for nothing here.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import select

from backend import db, evaluations, tables
from backend.statuses import RunKind, RunStatus

NEEDED_RUNS = {"evaluation": 1, "held_out": 2}


def _run_ids_by_version(versions: list[int], eval_set: str) -> dict[int, list[int]]:
    """Each version's finished whole-set evaluations by its rounds, oldest first."""
    runs = tables.runs.c
    found: dict[int, list[int]] = {version: [] for version in versions}
    with db.connection() as conn:
        rows = conn.execute(
            select(runs.run_id, runs.configuration_version)
            .where(
                runs.configuration_version.in_(versions),
                runs.round_id.is_not(None),
                runs.kind == RunKind.EVALUATION,
                runs.tiny.is_(False),
                runs.eval_set == eval_set,
                runs.status == RunStatus.FINISHED,
            )
            .order_by(runs.run_id)
        )
        for run_id, version in rows:
            found[version].append(run_id)
    return found


def _run_ids(version: int, eval_set: str) -> list[int]:
    return _run_ids_by_version([version], eval_set)[version]


def _average(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal(0)) / len(values) if values else None


def _measures(evaluation: dict[str, Any]) -> dict[str, Any]:
    measures = evaluation["measures"]
    return {
        "accuracy": measures["accuracy"],
        "grade": measures["grade"],
        "cost_per_claim": measures["model_cost_per_claim"],
        "seconds_per_claim": measures["seconds_per_claim"],
    }


def scores_for(versions: list[int], eval_set: str) -> dict[int, dict[str, Any]]:
    """Return each version's averages on a set, and how many runs there are.

    A measure with no value in any run, such as the grade of ungraded runs, is None.
    """
    by_version = _run_ids_by_version(versions, eval_set)
    every_run = [run_id for run_ids in by_version.values() for run_id in run_ids]
    measured = {
        e["run_id"]: _measures(e) for e in evaluations.get_evaluations(every_run)
    }
    names = ("accuracy", "grade", "cost_per_claim", "seconds_per_claim")
    return {
        version: {
            "runs": len(run_ids),
            **{
                name: _average(
                    [
                        measured[run_id][name]
                        for run_id in run_ids
                        if measured[run_id][name] is not None
                    ]
                )
                for name in names
            },
        }
        for version, run_ids in by_version.items()
    }


def scores_on(version: int, eval_set: str) -> dict[str, Any]:
    """Return the averages of a version's runs on a set, and how many runs there are."""
    return scores_for([version], eval_set)[version]


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
