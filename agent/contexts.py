"""What a claim run knows, handed to its tools and nodes."""

from dataclasses import dataclass


@dataclass
class ClaimContext:
    """The claim an agent is deciding, and the run it is worked in, if any."""

    claim_id: str
    run_id: int | None


@dataclass
class ImproverContext:
    """The round the improver is working for, and the stretch of work it is in."""

    round_id: int
    run_id: int
