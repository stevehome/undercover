"""The reads a handler, and so the Copilot, asks for: customers, policies and counts."""

from typing import Any

from fastapi import APIRouter, Depends

from backend import customers, needs_a_handler, over_limit
from backend.auth import signed_in_handler

router = APIRouter(prefix="/api", dependencies=[Depends(signed_in_handler)])


@router.get("/customers", operation_id="find_customers")
def find_customers(name: str) -> list[dict[str, Any]]:
    """List the customers whose name holds this text, in any case."""
    return customers.find(name)


@router.get("/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str) -> dict[str, Any]:
    """Return a customer with their policies, earlier claims and claims in the queue."""
    return customers.get(customer_id)


@router.get("/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Return a policy with the limits of its plan."""
    return customers.policy(policy_id)


@router.get("/payments/over-limit", operation_id="list_payments_over_the_limit")
def list_payments_over_the_limit() -> dict[str, Any]:
    """Return the claims paid over the approval limit and how many carry a sign-off."""
    return over_limit.get()


@router.get("/queue/needs-a-handler", operation_id="get_what_needs_a_handler")
def get_what_needs_a_handler() -> dict[str, list[dict[str, Any]]]:
    """Return the payouts held for sign-off, the referred claims and the sent-back."""
    return needs_a_handler.get()
