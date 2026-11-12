"""What the improver may read: its round's numbers, never the held-out set's claims.

From the evaluation set it sees the wrong claims and the five right ones explained
least well, with the handlers' decisions and reasons. From the held-out set it sees
scores only.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import select

from backend import (
    db,
    evaluations,
    platform_settings,
    rounds,
    spending,
    tables,
    version_scores,
    versions,
)
from backend.statuses import RunKind, RunStatus

LEAST_WELL_EXPLAINED = 5
RULE = (
    "A new version is kept when it meets the objectives on the held-out set, at "
    "least one measure improves by more than its noise and none gets worse by more "
    "than its tolerance. Accuracy and the grade are compared as differences; cost "
    "and time as fractions of the old value. A version with no grade is rolled back."
)


def _latest_evaluation_run(version: int) -> int | None:
    runs = tables.runs.c
    with db.connection() as conn:
        return conn.execute(
            select(runs.run_id)
            .where(
                runs.configuration_version == version,
                runs.kind == RunKind.EVALUATION,
                runs.eval_set == evaluations.EVALUATION_SET,
                runs.tiny.is_(False),
                runs.status == RunStatus.FINISHED,
            )
            .order_by(runs.run_id.desc())
            .limit(1)
        ).scalar_one_or_none()


def _explanations(run_id: int) -> dict[str, dict[str, Any]]:
    """The claim, the handler's reason and the agent's, for each claim of a run."""
    in_run, claims, key = tables.run_claims.c, tables.claims.c, tables.answer_key.c
    with db.connection() as conn:
        rows = conn.execute(
            select(
                in_run.claim_id,
                claims.summary,
                claims.story,
                claims.reason.label("agent_reason"),
                claims.policy_reference.label("agent_section"),
                key.reason.label("handler_reason"),
                key.reference.label("handler_reference"),
            )
            .join(tables.claims, claims.claim_id == in_run.claim_id)
            .join(
                tables.answer_key,
                (key.eval_set == evaluations.EVALUATION_SET)
                & (key.claim_id == in_run.source_claim_id),
            )
            .where(in_run.run_id == run_id)
        )
        return {row.claim_id: dict(row._mapping) for row in rows}


def _claim_view(claim: dict[str, Any], text: dict[str, Any]) -> dict[str, Any]:
    grade = claim["grade"]
    return {
        "claim_id": claim["source_claim_id"],
        "summary": text["summary"],
        "story": text["story"],
        "right": claim["right"],
        "handler": {
            "decision": claim["handler_decision"],
            "payout": claim["handler_payout"],
            "reason": text["handler_reason"],
            "reference": text["handler_reference"],
        },
        "agent": {
            "decision": claim["agent_decision"],
            "payout": claim["agent_payout"],
            "reason": text["agent_reason"],
            "section": text["agent_section"],
        },
        "grade": None
        if grade is None
        else {
            "letter": grade["letter"],
            "score": grade["score"],
            "same_grounds": grade["same_grounds_matched"],
            "same_section": grade["same_section_matched"],
        },
    }


def _evaluation_claims(version: int) -> dict[str, list[dict[str, Any]]]:
    run_id = _latest_evaluation_run(version)
    if run_id is None:
        return {"wrong": [], "right_but_explained_least_well": []}
    claims = evaluations.get_evaluation(run_id)["claims"]
    text = _explanations(run_id)
    wrong = [c for c in claims if not c["right"]]
    right = sorted(
        (c for c in claims if c["right"]),
        key=lambda c: c["grade"]["score"] if c["grade"] else Decimal(-1),
    )
    return {
        "wrong": [_claim_view(c, text[c["claim_id"]]) for c in wrong],
        "right_but_explained_least_well": [
            _claim_view(c, text[c["claim_id"]]) for c in right[:LEAST_WELL_EXPLAINED]
        ],
    }


def _earlier_rounds(round_id: int) -> list[dict[str, Any]]:
    columns = tables.rounds.c
    with db.connection() as conn:
        found = conn.execute(
            select(
                columns.round_id,
                columns.configuration_version,
                columns.improver_reason,
                columns.held_out_before,
                columns.held_out_after,
                columns.verdict,
                columns.verdict_reason,
            )
            .where(columns.round_id != round_id)
            .order_by(columns.round_id)
        )
        return [dict(row._mapping) for row in found]


def _group(settings: dict[str, Any], prefix: str) -> dict[str, Decimal]:
    return {
        key.removeprefix(f"{prefix}_"): Decimal(str(value))
        for key, value in settings.items()
        if key.startswith(f"{prefix}_")
    }


def get_view(round_id: int) -> dict[str, Any]:
    """Return what the improver reads for an open round."""
    row = rounds.require_open(round_id)
    current = versions.current_configuration()
    settings = row["settings"]
    return {
        "current_version": {
            key: current[key]
            for key in ("version", "instructions", "model", "reasoning_effort")
        },
        "scores": version_scores.scores(current["version"]),
        "evaluation_set_claims": _evaluation_claims(current["version"]),
        "earlier_rounds": _earlier_rounds(round_id),
        "objectives_on_the_held_out_set": _group(settings, "objective"),
        "noise": _group(settings, "noise"),
        "tolerance": _group(settings, "tolerance"),
        "rule": RULE,
        "spending": {
            "limit": spending.limit(settings),
            "spent": spending.spent(round_id),
            "left": spending.left(round_id, settings),
        },
        "models_allowed": platform_settings.models(),
    }
