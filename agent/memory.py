"""The agent's memory of each customer, in AgentCore Memory.

After a claim is decided the agent saves what happened as two events, with the
customer as the actor and the claim as the session, and AgentCore turns them into
memories in the background. The agent searches only under its own claim's customer,
so one customer's memories never reach another's claim (claims manual section 11).
The story and the documents are never saved: a story is where a customer's text could
try to instruct us, and the documents hold whole medical records.
"""

import logging
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from langchain_core.messages import AIMessage, HumanMessage
from langgraph_checkpoint_aws import AgentCoreMemoryStore

from agent import endpoints
from agent.refusals import BY_MEMORY, Refusal

AWS_ERRORS = (BotoCoreError, ClientError)
CUSTOMERS = "customers"
SEARCH_LIMIT = 5
logger = logging.getLogger(__name__)


class MemoryStore(Protocol):
    """What the agent uses of a memory store: AgentCore's, or a stand-in for tests."""

    def put(
        self, namespace: tuple[str, ...], key: str, value: Mapping[str, Any]
    ) -> None: ...

    def search(
        self,
        namespace_prefix: tuple[str, ...],
        /,
        *,
        query: str | None = None,
        limit: int = 10,
    ) -> Sequence[Any]: ...


def _claim_text(claim: dict[str, Any]) -> str:
    """The claim as the customer's message: its summary, benefit, date, place, items."""
    items = "; ".join(f"{i['description']} (${i['amount']})" for i in claim["items"])
    return (
        f"Claim {claim['claim_id']}: {claim['summary']}. "
        f"Benefit claimed: {claim['claim_type']}. "
        f"Incident on {claim['incident_date']} in {claim['incident_location']}. "
        f"Items claimed: {items}."
    )


def _decision_text(claim: dict[str, Any]) -> str:
    """The decision as the agent's message: it, its payout, section and reason."""
    payout = f", payout ${claim['payout']}" if claim["decision"] == "approve" else ""
    return (
        f"Decision on {claim['claim_id']}: {claim['decision']}{payout}. "
        f"Section: {claim['policy_reference']}. Reason: {claim['reason']}"
    )


class CustomerMemory:
    """Saves a decided claim to a customer's memory and searches it."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def save_claim(self, claim: dict[str, Any]) -> bool:
        """Save the claim and its decision, and say whether it was saved.

        A claim keeps its decision when AgentCore can't be reached: the memory only
        adds what happened on a customer's earlier claims, so a failed save is
        logged and the work goes on. This is the one place besides the dispatcher
        where a failure is let go, and only for AWS's own errors.
        """
        namespace = (claim["customer_id"], claim["claim_id"])
        try:
            self.store.put(
                namespace, "claim", {"message": HumanMessage(_claim_text(claim))}
            )
            self.store.put(
                namespace, "decision", {"message": AIMessage(_decision_text(claim))}
            )
        except AWS_ERRORS:
            logger.warning(
                "Could not save %s to the memory", claim["claim_id"], exc_info=True
            )
            return False
        return True

    def search(self, customer_id: str, query: str, claim_id: str) -> list[str]:
        """Return what we remember about the customer, leaving out the claim in hand.

        A claim worked again would otherwise find its own summary.
        """
        try:
            found = self.store.search(
                (CUSTOMERS, customer_id), query=query, limit=SEARCH_LIMIT
            )
        except AWS_ERRORS as error:
            raise Refusal(BY_MEMORY, str(error)) from error
        return [
            item.value["content"] for item in found if claim_id not in item.namespace
        ]


def open_store(memory_id: str) -> MemoryStore:
    """Open the AgentCore Memory in the region the AWS CLI uses."""
    return AgentCoreMemoryStore(
        memory_id=memory_id, region_name=boto3.Session().region_name
    )


def open_for(claim: dict[str, Any]) -> CustomerMemory | None:
    """Return the memory a claim's work uses, or None.

    There is none when no memory is set, and none for an evaluation's copy of a
    claim, so evaluations and their scores don't depend on memory.
    """
    memory_id = endpoints.memory_id()
    if memory_id is None or claim["evaluation_run_id"] is not None:
        return None
    return CustomerMemory(open_store(memory_id))
