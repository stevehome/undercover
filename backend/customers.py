"""Customers and their policies, for a handler asking about a person."""

from typing import Any

from sqlalchemy import select

from backend import db, money, reference, tables

CUSTOMER_FIELDS = ("customer_id", "name", "email", "phone", "customer_since")


def find(name: str) -> list[dict[str, Any]]:
    """List the customers whose name holds this text, in any case."""
    columns = tables.customers.c
    with db.connection() as conn:
        rows = conn.execute(
            select(*(columns[field] for field in CUSTOMER_FIELDS))
            .where(columns.name.icontains(name, autoescape=True))
            .order_by(columns.name, columns.customer_id)
        )
        return [dict(row._mapping) for row in rows]


def _policies(customer_id: str) -> list[dict[str, Any]]:
    columns = tables.policies.c
    with db.connection() as conn:
        rows = conn.execute(
            select(
                columns.policy_id,
                columns.plan,
                columns.status,
                columns.purchased_on,
                columns.add_ons,
            )
            .where(columns.customer_id == customer_id)
            .order_by(columns.policy_id)
        )
        return [dict(row._mapping) for row in rows]


def _claims_in_queue(customer_id: str) -> list[dict[str, Any]]:
    columns = tables.claims.c
    with db.connection() as conn:
        rows = conn.execute(
            select(
                columns.claim_id,
                columns.claim_type,
                columns.summary,
                columns.amount_claimed_cents,
                columns.status,
                columns.decision,
            )
            .where(
                columns.customer_id == customer_id,
                columns.evaluation_run_id.is_(None),
            )
            .order_by(columns.submitted_on, columns.claim_id)
        )
        return [money.dollar_fields(dict(row._mapping)) for row in rows]


def get(customer_id: str) -> dict[str, Any]:
    """Return a customer with their policies, earlier claims and claims in our queue."""
    record = reference.customer(customer_id)
    return {
        **{field: record[field] for field in CUSTOMER_FIELDS},
        "previous_claims": record["previous_claims"],
        "policies": _policies(customer_id),
        "claims_in_queue": _claims_in_queue(customer_id),
    }


def policy(policy_id: str) -> dict[str, Any]:
    """Return a policy with the limits of its plan."""
    record = reference.policy(policy_id)
    return {**record, "plan_limits": reference.plan(record["plan"])}
