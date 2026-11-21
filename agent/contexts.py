"""What a claim run knows, handed to its tools and nodes."""

from dataclasses import dataclass

from agent.tool_route import ToolRoute


@dataclass
class ClaimContext:
    """The claim an agent is deciding, its policy, the run it is worked in if any, and
    the route its tools take. The model acts only on this claim."""

    claim_id: str
    run_id: int | None
    policy_id: str
    route: ToolRoute


@dataclass
class ImproverContext:
    """The round the improver is working for, and the stretch of work it is in."""

    round_id: int
    run_id: int
