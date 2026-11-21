"""The starting records: reads `data/` into rows for the tables."""

import importlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Table

from backend import money, tables
from backend.statuses import ClaimStatus, Verdict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DOCUMENTS = ("policy_wording", "claims_manual")


def _load_json(name: str) -> Any:
    text = (DATA_DIR / name).read_text()
    return money.convert(json.loads(text, parse_float=Decimal))


def _with_security(name: str) -> Any:
    """A file's records, and the security claim's beside them.

    `security/decisions.json` is never read, so CLM-1901 has no decision in the
    answer key and is in neither evaluation set.
    """
    return [*_load_json(name), *_load_json(f"security/{name}")]


def _context_files() -> Any:
    """The context layer's file readers.

    The app needs `context/` only while seeding, and its Lambda package has none, so
    this is loaded when seeding and not when the app is imported.
    """
    return importlib.import_module("context.files")


def _plans() -> Any:
    """The plans and add-ons from the context layer's file, in `Decimal` dollars."""
    return money.convert(_context_files().read_data("plans.yaml").content)


def _document_rows() -> list[dict[str, Any]]:
    """The policy wording and the claims manual, each with its version."""
    documents = [_context_files().read_document(name) for name in DOCUMENTS]
    return [
        {"document": doc.name, "version": doc.version, "text": doc.body}
        for doc in documents
    ]


def _claim_row(claim: dict[str, Any]) -> dict[str, Any]:
    row = money.cents_columns({k: v for k, v in claim.items() if k != "status"})
    return {**row, "status": ClaimStatus.WAITING}


def _held_out_row(claim: dict[str, Any]) -> dict[str, Any]:
    return money.cents_columns({k: v for k, v in claim.items() if k != "status"})


def _answer_key_rows() -> list[dict[str, Any]]:
    """The handlers' decisions on the two labelled sets, which only scoring reads."""
    files = {
        "evaluation": "evals/decisions.json",
        "held_out": "evals/held_out_decisions.json",
    }
    return [
        {
            "eval_set": eval_set,
            "claim_id": answer["claim_id"],
            "tiny": answer["tiny"],
            "decision": answer["decision"],
            "payout_cents": money.to_cents(answer["payout"]),
            "reason": answer["reason"],
            "reference": answer["reference"],
        }
        for eval_set, filename in files.items()
        for answer in _load_json(filename)
    ]


def _model_rows() -> list[dict[str, Any]]:
    """The models allowed, in file order, with prices as plain numbers."""
    models = json.loads((DATA_DIR / "models.json").read_text())
    return [{**model, "position": position} for position, model in enumerate(models)]


def _first_version(**content: str) -> dict[str, Any]:
    """Version 1 of the configuration or the recipe: kept, from the starting files."""
    return {
        "version": 1,
        "reason": "The starting version",
        "proposed_by": "seed",
        "verdict": Verdict.KEPT,
        "verdict_reason": "The starting version",
        "created_on": datetime.now(UTC).isoformat(),
        **content,
    }


def records() -> dict[Table, list[dict[str, Any]]]:
    """Return every table's starting rows."""
    plan_data = _plans()
    return {
        tables.settings: [
            {"key": key, "value": value}
            for name in ("company.json", "improvement.json")
            for key, value in _load_json(name).items()
        ],
        tables.models: _model_rows(),
        tables.configurations: [
            _first_version(
                instructions=(DATA_DIR / "claim_instructions.md").read_text(),
                model="openai/gpt-6-luna",
                reasoning_effort="low",
            )
        ],
        tables.recipes: [
            _first_version(text=(DATA_DIR / "improver_recipe.md").read_text())
        ],
        tables.plans: [money.cents_columns(plan) for plan in plan_data["plans"]],
        tables.add_ons: [
            {"electronics_per_item_limit_cents": None, **money.cents_columns(add_on)}
            for add_on in plan_data["add_ons"]
        ],
        tables.deductible_benefits: [
            {"benefit": benefit} for benefit in plan_data["deductible_applies_to"]
        ],
        tables.policies: _with_security("policies.json"),
        tables.customers: _with_security("customers.json"),
        tables.handlers: _load_json("handlers.json"),
        tables.documents: _document_rows(),
        tables.claims: [_claim_row(claim) for claim in _with_security("claims.json")],
        tables.held_out_claims: [
            _held_out_row(claim) for claim in _load_json("evals/held_out_claims.json")
        ],
        tables.answer_key: _answer_key_rows(),
    }
