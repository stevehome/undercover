"""The improver's proposals: a change or a recipe that changes nothing until approved.

A proposal is a record. Approving it, by a handler, is what makes a version.
"""

from typing import Any

from sqlalchemy import Connection, insert, select, update

from backend import (
    db,
    diffs,
    platform_settings,
    reference,
    rounds,
    stopwatch,
    tables,
    versions,
)
from backend.errors import Conflict, Invalid, NotFound
from backend.statuses import ProposalKind, ProposalStatus, RunKind, RunStatus, Stage


def _checked_change(content: dict[str, Any]) -> None:
    """Raise Invalid unless a change names a model and effort that are allowed."""
    allowed = {m["model"]: m["reasoning_efforts"] for m in platform_settings.models()}
    if content["model"] not in allowed:
        raise Invalid(
            f"{content['model']} is not an allowed model; "
            f"use one of {', '.join(allowed)}"
        )
    if content["reasoning_effort"] not in allowed[content["model"]]:
        efforts = ", ".join(allowed[content["model"]])
        raise Invalid(
            f"{content['reasoning_effort']} is not an allowed reasoning effort for "
            f"{content['model']}; use one of {efforts}"
        )
    if not content["instructions"].strip():
        raise Invalid("The instructions are empty")


def record_proposal(
    round_id: int, kind: ProposalKind, content: dict[str, Any], reason: str
) -> dict[str, Any]:
    """Record a proposal as pending, and the round as waiting for a handler.

    A proposal outside the models allowed is refused, so it never reaches a handler.
    """
    rounds.require_open(round_id)
    if kind == ProposalKind.CHANGE:
        _checked_change(content)
        content = {
            **content,
            "base_version": versions.current_configuration()["version"],
        }
        waiting = Stage.CHANGE_WAITING
    else:
        if not content["recipe"].strip():
            raise Invalid("The recipe is empty")
        content = {**content, "base_version": versions.current_recipe()["version"]}
        waiting = Stage.RECIPE_WAITING
    with db.connection() as conn:
        proposal_id = conn.execute(
            insert(tables.proposals)
            .values(
                round_id=round_id,
                kind=kind,
                content=content,
                reason=reason,
                status=ProposalStatus.PENDING,
                created_on=db.now(),
            )
            .returning(tables.proposals.c.proposal_id)
        ).scalar_one()
        conn.execute(
            update(tables.rounds)
            .where(tables.rounds.c.round_id == round_id)
            .values(stage=waiting, progress=0)
        )
    return get_proposal(proposal_id)


def _row(proposal_id: int) -> dict[str, Any]:
    with db.connection() as conn:
        row = conn.execute(
            select(tables.proposals).where(
                tables.proposals.c.proposal_id == proposal_id
            )
        ).one_or_none()
    if row is None:
        raise NotFound(f"No proposal {proposal_id}")
    return dict(row._mapping)


def _change_view(
    content: dict[str, Any], configurations: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    base = configurations[content["base_version"]]
    return {
        "from_version": base["version"],
        "lines": diffs.diff_lines(base["instructions"], content["instructions"]),
        "model_before": base["model"],
        "model_after": content["model"],
        "reasoning_effort_before": base["reasoning_effort"],
        "reasoning_effort_after": content["reasoning_effort"],
    }


def _recipe_view(
    content: dict[str, Any], recipes: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    base = recipes[content["base_version"]]
    return {
        "from_version": base["version"],
        "lines": diffs.diff_lines(base["text"], content["recipe"]),
    }


def _views(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Proposals with what each would change and who decided it, in a few queries."""
    names = {h["handler_id"]: h["name"] for h in reference.handlers()}
    configurations = {c["version"]: c for c in versions.list_configurations()}
    recipes = {r["version"]: r for r in versions.list_recipes()}
    return [
        {
            **row,
            "decided_by": names.get(row["decided_by"]),
            **(
                _change_view(row["content"], configurations)
                if row["kind"] == ProposalKind.CHANGE
                else _recipe_view(row["content"], recipes)
            ),
        }
        for row in rows
    ]


def get_proposal(proposal_id: int) -> dict[str, Any]:
    """Return a proposal with what it would change and who decided it."""
    return _views([_row(proposal_id)])[0]


def for_rounds(round_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Return each round's proposals in order, in a fixed number of queries."""
    columns = tables.proposals.c
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.proposals)
            .where(columns.round_id.in_(round_ids))
            .order_by(columns.proposal_id)
        )
        found = [dict(row._mapping) for row in rows]
    by_round: dict[int, list[dict[str, Any]]] = {round_id: [] for round_id in round_ids}
    for proposal in _views(found):
        by_round[proposal["round_id"]].append(proposal)
    return by_round


def _running_stretch(round_id: int) -> int | None:
    """The round's improver stretch that is going, or None."""
    runs = tables.runs.c
    with db.connection() as conn:
        return conn.execute(
            select(runs.run_id)
            .where(
                runs.round_id == round_id,
                runs.kind == RunKind.IMPROVER,
                runs.status == RunStatus.RUNNING,
            )
            .order_by(runs.run_id.desc())
            .limit(1)
        ).scalar_one_or_none()


def _decided_since(row: dict[str, Any]) -> bool:
    """Say whether a later proposal of the proposal's round has been decided."""
    columns = tables.proposals.c
    with db.connection() as conn:
        return (
            conn.execute(
                select(columns.proposal_id)
                .where(
                    columns.round_id == row["round_id"],
                    columns.proposal_id > row["proposal_id"],
                    columns.status != ProposalStatus.PENDING,
                )
                .limit(1)
            ).first()
            is not None
        )


def _replay(row: dict[str, Any], decided: ProposalStatus) -> dict[str, Any] | None:
    """Answer a repeat of the decision already made, while its stretch is going."""
    if row["status"] != decided or _decided_since(row):
        return None
    run_id = _running_stretch(row["round_id"])
    if run_id is None:
        return None
    return {"run_id": run_id, "version": row["version"], "round_id": row["round_id"]}


def _record(
    row: dict[str, Any],
    decided: ProposalStatus,
    handler_id: str,
    rejection_reason: str,
    stretch_model: tuple[str, str],
) -> dict[str, Any]:
    """Record the decision, its stretch and its version in one transaction."""
    approved = decided == ProposalStatus.APPROVED
    watch = stopwatch.Stopwatch(
        f"Recording the decision on proposal {row['proposal_id']}"
    )
    try:
        with db.connection() as conn:
            run_id = rounds.begin_stretch(conn, row["round_id"], *stretch_model)
            watch.lap("begin the stretch")
            version = _add_version(conn, row, handler_id) if approved else None
            watch.lap("add the version")
            conn.execute(
                update(tables.proposals)
                .where(tables.proposals.c.proposal_id == row["proposal_id"])
                .values(
                    status=decided,
                    decided_by=handler_id,
                    decided_on=db.now(),
                    rejection_reason=None if approved else rejection_reason,
                    version=version,
                )
            )
            watch.lap("update the proposal")
            conn.execute(
                update(tables.rounds)
                .where(tables.rounds.c.round_id == row["round_id"])
                .values(**_round_after(row, approved, version))
            )
            watch.lap("update the round")
        watch.lap("commit")
        return {"run_id": run_id, "version": version, "round_id": row["round_id"]}
    finally:
        watch.log()


def record_decision(
    proposal_id: int,
    approved: bool,
    handler_id: str,
    rejection_reason: str,
    stretch_model: tuple[str, str],
) -> dict[str, Any]:
    """Record a handler's decision, and begin the stretch of work that follows.

    Asked again for the same decision while its stretch is still going, as when
    the first reply was lost, it answers as it did. Raises RunAlreadyGoing before
    anything is recorded if something else is running.
    """
    row = _row(proposal_id)
    rounds.require_open(row["round_id"])
    decided = ProposalStatus.APPROVED if approved else ProposalStatus.REJECTED
    if (replayed := _replay(row, decided)) is not None:
        return replayed
    if row["status"] != ProposalStatus.PENDING:
        raise Conflict(f"Proposal {proposal_id} is already {row['status']}")
    return _record(row, decided, handler_id, rejection_reason, stretch_model)


def _add_version(conn: Connection, row: dict[str, Any], handler_id: str) -> int:
    common = {
        "reason": row["reason"],
        "proposed_by": "improver",
        "approved_by": handler_id,
        "approved_on": db.now(),
        "round_id": row["round_id"],
    }
    if row["kind"] == ProposalKind.CHANGE:
        content = row["content"]
        return versions.add_version(
            conn,
            tables.configurations,
            instructions=content["instructions"],
            model=content["model"],
            reasoning_effort=content["reasoning_effort"],
            **common,
        )
    return versions.add_version(
        conn,
        tables.recipes,
        text=row["content"]["recipe"],
        verdict="kept",
        verdict_reason="Approved by a handler",
        **common,
    )


def _round_after(
    row: dict[str, Any], approved: bool, version: int | None
) -> dict[str, Any]:
    if row["kind"] == ProposalKind.CHANGE and approved:
        return {
            "stage": Stage.EVALUATIONS,
            "progress": 0,
            "configuration_version": version,
            "improver_reason": row["reason"],
        }
    return {"stage": Stage.IMPROVER_WORKING, "progress": 0}
