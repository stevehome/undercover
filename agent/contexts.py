"""What a claim run knows, handed to its tools and nodes."""

from dataclasses import dataclass

from agent.memory import CustomerMemory
from agent.tool_route import ToolRoute


@dataclass
class ClaimContext:
    """The claim an agent is deciding, its customer, the run it is worked in if any,
    who decides it, the route its tools take, its memory if it has one, and whether it
    is an evaluation's copy. The model acts only on this claim."""

    claim_id: str
    customer_id: str
    run_id: int | None
    decided_by: str
    route: ToolRoute
    memory: CustomerMemory | None
    evaluation: bool = False


@dataclass
class ImproverContext:
    """The round the improver is working for, and the stretch of work it is in."""

    round_id: int
    run_id: int
