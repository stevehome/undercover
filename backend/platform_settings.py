"""The platform's settings, who changed them and when, and the models allowed."""

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import insert, select, update

from backend import db, money, tables
from backend.errors import Invalid

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Definition:
    """One setting a handler can see: what it is, its unit and its range."""

    key: str
    label: str
    group: str
    unit: str
    maximum: Decimal
    whole: bool = False


def _definitions() -> list[Definition]:
    ratio, grade = Decimal(1), Decimal(3)
    fraction = Decimal(10)
    rows = [
        ("payout_approval_limit", "Approval limit", "Payouts", "dollars", 1000000),
        (
            "objective_accuracy",
            "Accuracy",
            "Business objectives",
            "floor, 0 to 1",
            ratio,
        ),
        ("objective_grade", "Grade", "Business objectives", "floor, 0 to 3", grade),
        ("noise_accuracy", "Accuracy", "Noise", "difference, 0 to 1", ratio),
        ("noise_grade", "Grade", "Noise", "difference, 0 to 3", grade),
        (
            "noise_cost_per_claim",
            "Cost per claim",
            "Noise",
            "fraction of the old value",
            fraction,
        ),
        (
            "noise_seconds_per_claim",
            "Time per claim",
            "Noise",
            "fraction of the old value",
            fraction,
        ),
        ("tolerance_accuracy", "Accuracy", "Tolerance", "difference, 0 to 1", ratio),
        ("tolerance_grade", "Grade", "Tolerance", "difference, 0 to 3", grade),
        (
            "tolerance_cost_per_claim",
            "Cost per claim",
            "Tolerance",
            "fraction of the old value",
            fraction,
        ),
        (
            "tolerance_seconds_per_claim",
            "Time per claim",
            "Tolerance",
            "fraction of the old value",
            fraction,
        ),
        (
            "round_spending_limit",
            "Spending limit for each round",
            "Improvement",
            "dollars",
            100,
        ),
    ]
    definitions = [Definition(k, label, g, u, Decimal(m)) for k, label, g, u, m in rows]
    return [
        *definitions,
        Definition(
            "improver_agents_at_once",
            "Claim agents at once",
            "Improvement",
            "agents",
            Decimal(25),
            whole=True,
        ),
    ]


DEFINITIONS = _definitions()
BY_KEY = {definition.key: definition for definition in DEFINITIONS}
IMPROVEMENT_KEYS = [d.key for d in DEFINITIONS if d.group not in ("Payouts",)]


def _raw(key: str) -> Any:
    with db.connection() as conn:
        value = conn.execute(
            select(tables.settings.c.value).where(tables.settings.c.key == key)
        ).scalar_one()
    return money.convert({key: value})[key]


def get(key: str) -> Decimal | int:
    """Return a setting's value: `Decimal`, or a whole number for a count."""
    definition = BY_KEY[key]
    value = _raw(key)
    return int(value) if definition.whole else Decimal(str(value)).quantize(CENT)


def snapshot() -> dict[str, str]:
    """Return the improvement settings as they stand, as text, to keep with a round."""
    return {key: str(get(key)) for key in IMPROVEMENT_KEYS}


def _latest_changes() -> dict[str, dict[str, Any]]:
    handlers = tables.handlers.c
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.setting_changes, handlers.name)
            .join(
                tables.handlers,
                handlers.handler_id == tables.setting_changes.c.changed_by,
            )
            .order_by(tables.setting_changes.c.id)
        )
        return {row.key: dict(row._mapping) for row in rows}


def list_settings() -> list[dict[str, Any]]:
    """List the settings with their values and who last changed each, and when."""
    changes = _latest_changes()
    return [
        {
            "key": d.key,
            "label": d.label,
            "group": d.group,
            "unit": d.unit,
            "value": get(d.key),
            "maximum": d.maximum,
            "changed_by": changes[d.key]["name"] if d.key in changes else None,
            "changed_on": changes[d.key]["changed_on"] if d.key in changes else None,
        }
        for d in DEFINITIONS
    ]


def _checked(definition: Definition, value: Decimal) -> Decimal | int:
    """Return a value in its own kind, or raise Invalid with the reason."""
    if not value.is_finite() or value < 0 or value > definition.maximum:
        raise Invalid(f"{definition.label} must be from 0 to {definition.maximum}")
    if definition.whole:
        if value != value.to_integral_value() or value < 1:
            raise Invalid(f"{definition.label} must be a whole number, 1 or more")
        return int(value)
    if value != value.quantize(CENT):
        raise Invalid(f"{definition.label} must have at most two decimal places")
    return value.quantize(CENT)


def change(key: str, value: Decimal, handler: dict[str, Any]) -> dict[str, Any]:
    """Change a setting as a handler, recording who and when; refuse a bad value."""
    if key not in BY_KEY:
        raise Invalid(f"No setting {key}")
    checked = _checked(BY_KEY[key], value)
    old = get(key)
    with db.connection() as conn:
        conn.execute(
            update(tables.settings)
            .where(tables.settings.c.key == key)
            .values(value=str(checked) if not BY_KEY[key].whole else checked)
        )
        conn.execute(
            insert(tables.setting_changes).values(
                key=key,
                old_value=str(old),
                new_value=str(checked),
                changed_by=handler["handler_id"],
                changed_on=db.now(),
            )
        )
    return next(s for s in list_settings() if s["key"] == key)


def models() -> list[dict[str, Any]]:
    """List the models allowed; with MODEL_NAME set, only that one."""
    name = os.getenv("MODEL_NAME")
    if name:
        return [
            {
                "model": name,
                "reasoning_efforts": ["default"],
                "input_price_per_million": 0.0,
                "output_price_per_million": 0.0,
            }
        ]
    with db.connection() as conn:
        rows = conn.execute(select(tables.models).order_by(tables.models.c.position))
        return [
            {k: v for k, v in row._mapping.items() if k != "position"} for row in rows
        ]
